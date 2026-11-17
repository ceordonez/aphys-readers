"""Reader for Solinst Levelogger (water level) and Barologger (air pressure) files.

Both the Levelogger software's ``.xle`` files (XML) and their ``.csv`` exports
are read. Neither states the time zone of the logger clock, so a UTC offset
must be given.
"""

import io
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from aphys_readers.utils import (
    Paths,
    StrPath,
    UtcOffset,
    check_one_logger,
    combine,
    resolve_files,
    to_utc,
    walk_files,
)

# Files made by barometric compensation; Solinst names them "...Compensated..."
COMPENSATED_NAME = re.compile(r"compensat|corrected", re.I)
SERIAL_NUMBER = re.compile(r"<Serial_number>\s*(\d+)|^Serial_number:[,\s]*(\d+)", re.M)
FIRST_UNIT = re.compile(r"<Unit>([^<]*)</Unit>|^UNIT:\s*([^,\r\n]*)", re.M)
# Channel identification -> output column, by unit
CHANNELS = {("LEVEL", "m"): "Level_m", ("LEVEL", "kPa"): "Pressure_kPa", ("TEMPERATURE", "C"): "Temp_C"}
DATE_FORMATS = ["%Y/%m/%d", "%d.%m.%Y", "%m/%d/%y", "%d/%m/%y", "%m/%d/%Y"]


def read_solinst(
    paths: Paths,
    serial: str | int | None = None,
    utc_offset: UtcOffset = None,
    compensated: bool = True,
    resample: str | None = "1min",
) -> pd.DataFrame:
    """Read Levelogger or Barologger data of one logger.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_solinst_files`), a single
        file, or a list of files.
    serial : str, int or None
        Logger to read. Needed when the files come from several loggers (a
        folder usually holds a Levelogger and its Barologger).
    utc_offset : str, float or None
        Logger clock offset (e.g. ``"UTC+02:00"``); required, as the files
        state no time zone.
    compensated : bool
        When searching a directory, read the barometrically compensated
        Levelogger files (True) or the raw ones (False).
    resample : str or None
        Frequency to average to; None keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        ``Level_m`` (Levelogger) or ``Pressure_kPa`` (Barologger), and
        ``Temp_C``, indexed by UTC ``Datetime``; empty if no files were found.
    """
    logging.info("Reading Solinst data")
    files = resolve_files(paths, lambda d: find_solinst_files(d, compensated))
    files = check_one_logger(files, solinst_serial, serial)
    if not files:
        logging.warning("No Solinst files found in: %s", paths)
    return combine([read_solinst_file(f, utc_offset) for f in files], resample)


def find_solinst_files(directory: StrPath, compensated: bool = True) -> list[Path]:
    """List Solinst ``.xle`` and ``.csv`` files below a directory.

    A folder often holds the same recording several times: raw and
    barometrically compensated, each as ``.xle`` and ``.csv``. Levelogger
    files are kept when their compensation matches `compensated`; Barologger
    files are always kept. Within a folder, ``.xle`` files are dropped when a
    ``.csv`` of the same logger and kind is present. Folders whose name starts
    with ``_`` are skipped.
    """
    candidates = []
    for f in walk_files(directory):
        if f.suffix.lower() not in (".xle", ".csv") or not is_solinst(f):
            continue
        barologger = is_barologger(f)
        if not barologger and is_compensated(f) != compensated:
            continue
        candidates.append((f, solinst_serial(f), barologger or is_compensated(f)))
    csv_kinds = {(f.parent, s, k) for f, s, k in candidates if f.suffix.lower() == ".csv"}
    return [
        f
        for f, s, k in candidates
        if f.suffix.lower() == ".csv" or (f.parent, s, k) not in csv_kinds
    ]


def head(path: StrPath, size: int = 3000) -> str:
    """Start of a file as text."""
    with open(path, "rb") as fh:
        return fh.read(size).decode("utf-8", errors="replace")


def is_solinst(path: StrPath) -> bool:
    """Whether a file is a Solinst ``.xle`` or a ``.csv`` export of one."""
    text = head(path)
    return "<Body_xle>" in text or text.lstrip("﻿").startswith("Serial_number:")


def is_barologger(path: StrPath) -> bool:
    """Whether a file comes from a Barologger: its first channel is in kPa.

    Compensated Levelogger files also mention kPa, in the embedded Barologger
    header that follows their own channels.
    """
    match = FIRST_UNIT.search(head(path))
    if match is None:
        return False
    return (match.group(1) or match.group(2)).strip() == "kPa"


def is_compensated(path: StrPath) -> bool:
    """Whether a Levelogger file holds barometrically compensated levels.

    Compensated ``.xle`` files embed the Barologger's header (a second serial
    number); ``.csv`` exports only show it in the file name.
    """
    path = Path(path)
    if path.suffix.lower() == ".xle" and len(SERIAL_NUMBER.findall(head(path, 20000))) > 1:
        return True
    return bool(COMPENSATED_NAME.search(path.name))


def solinst_serial(path: StrPath) -> str:
    """Serial number of the logger that wrote a Solinst file."""
    match = SERIAL_NUMBER.search(head(path))
    if not match:
        raise ValueError(f"{path}: no Solinst serial number found")
    return match.group(1) or match.group(2)


def read_solinst_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Read one Solinst ``.xle`` or ``.csv`` file at native resolution.

    Raises ValueError without `utc_offset`, since the files state no time zone.
    """
    path = Path(path)
    logging.info("Reading file: %s", path)
    if path.suffix.lower() == ".xle":
        names, dates, times, values = read_xle(path)
    else:
        names, dates, times, values = read_csv_export(path)
    data = pd.DataFrame(values, columns=names).apply(pd.to_numeric)
    data.index = to_utc(parse_times(dates, times, path), utc_offset, path)
    return data


def read_xle(path: Path) -> tuple[list[str], list[str], list[str], list[list[str]]]:
    """Channel names and (date, time, values) rows of an ``.xle`` file."""
    root = ET.fromstring(path.read_bytes().decode("utf-8", errors="replace"))
    names = []
    for n in (1, 2, 3):
        header = root.find(f"Ch{n}_data_header")
        if header is None:
            break
        names.append(channel(header.findtext("Identification", ""), header.findtext("Unit", "")))
    rows = root.find("Data")
    logs = rows.findall("Log") if rows is not None else []
    dates = [log.findtext("Date", "") for log in logs]
    times = [log.findtext("Time", "") for log in logs]
    values = [[log.findtext(f"ch{n + 1}", "") for n in range(len(names))] for log in logs]
    return names, dates, times, values


def read_csv_export(path: Path) -> tuple[list[str], list[str], list[str], list[list[str]]]:
    """Channel names and (date, time, values) rows of a ``.csv`` export.

    The header lists each channel's name followed by a ``UNIT:`` line, then
    the column header ``Date,Time,ms,LEVEL,TEMPERATURE``.
    """
    lines = [line.rstrip(",") for line in path.read_bytes().decode("utf-8", errors="replace").splitlines()]
    start = next(i for i, line in enumerate(lines) if line.startswith("Date,Time"))
    units = {}
    for prev, line in zip(lines[:start], lines[1:start]):
        if line.startswith("UNIT:"):
            units[prev.strip()] = line.split(":", 1)[1].strip()
    columns = lines[start].split(",")[3:]
    names = [channel(c, units.get(c, "")) for c in columns]
    rows = list(pd.read_csv(io.StringIO("\n".join(lines[start + 1 :])), header=None, dtype=str).itertuples(index=False))
    return names, [r[0] for r in rows], [r[1] for r in rows], [list(r[3 : 3 + len(names)]) for r in rows]


def channel(identification: str, unit: str) -> str:
    """Output column name of a channel, e.g. (``LEVEL``, ``m``) -> ``Level_m``."""
    unit = unit.strip().lstrip("°�Â").strip() or unit
    return CHANNELS.get((identification.strip().upper(), unit), f"{identification.strip().title()}_{unit}")


def parse_times(dates: list[str], times: list[str], path: Path) -> pd.Series:
    """Parse dates in the first of `DATE_FORMATS` that fits every row."""
    stamps = pd.Series([f"{d} {t}" for d, t in zip(dates, times)])
    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(stamps, format=f"{fmt} %H:%M:%S", errors="coerce")
        if parsed.notna().all():
            return parsed
    raise ValueError(f"{path}: unknown date format, e.g. {stamps.iloc[0]!r}")
