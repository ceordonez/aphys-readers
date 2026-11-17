"""Reader for the CH4/CO2 probes ("Roma" probes) used on moorings.

The probes log hourly to text files with one row per sample:
``Probe;Date;CH4(%);CO2(%);AR_CH4;AR_CO2;T_s(°C);T_ext(°C);Vbat(V);Press(Bar)``.
They have no serial number; the probe number in the first column identifies
them. The files state no time zone, so a UTC offset must be given.

Three layouts are read:

- raw logger exports, ``;``-separated with ``dd/mm/yy HH:MM:SS`` dates;
- processed copies, tab-separated with an ``ExcelTime`` column (Excel serial
  days), which some re-timed rows rely on;
- a raw export opened and saved by Excel, tab-separated, whose ``dd/mm/yy``
  dates were read as ``yy/mm/dd`` (``2003-11-16`` for 3 Nov 2016).

When the logger clock resets, it writes dates such as ``00/00/00`` while still
sampling hourly. Those rows have no usable time and are dropped.
"""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
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

# Raw header -> output column
COLUMNS = {
    "CH4(%)": "CH4_pct",
    "CO2(%)": "CO2_pct",
    "AR_CH4": "AR_CH4",
    "AR_CO2": "AR_CO2",
    "T_s": "Tsensor_C",
    "T_ext": "Text_C",
    "Vbat(V)": "Battery_V",
    "Press(Bar)": "Press_bar",
}
# Value the probe writes for a missing temperature reading
ERROR_VALUE = 327.67
EXCEL_EPOCH = datetime(1899, 12, 30)


def read_roma(
    paths: Paths,
    serial: str | int | None = None,
    utc_offset: UtcOffset = None,
    processed: bool = False,
    resample: str | None = None,
) -> pd.DataFrame:
    """Read the data of one CH4/CO2 probe.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_roma_files`), a single
        file, or a list of files.
    serial : str, int or None
        Probe number. Needed when the files come from several probes.
    utc_offset : str, float or None
        Probe clock offset (e.g. ``"UTC+02:00"``); required, as the files
        state no time zone.
    processed : bool
        When searching a directory, read the processed copies (with
        ``ExcelTime``) instead of the raw exports in folders that have both.
    resample : str or None
        Frequency to average to; None (default) keeps the hourly samples.

    Returns
    -------
    pandas.DataFrame
        ``CH4_pct``, ``CO2_pct``, ``AR_CH4``, ``AR_CO2``, ``Tsensor_C``,
        ``Text_C``, ``Battery_V`` and ``Press_bar`` indexed by UTC
        ``Datetime``; empty if no files were found.
    """
    logging.info("Reading CH4/CO2 probe data")
    files = resolve_files(paths, lambda d: find_roma_files(d, processed))
    files = check_one_logger(files, roma_serial, serial)
    if not files:
        logging.warning("No CH4/CO2 probe files found in: %s", paths)
    return combine([read_roma_file(f, utc_offset) for f in files], resample)


def find_roma_files(directory: StrPath, processed: bool = False) -> list[Path]:
    """List CH4/CO2 probe files below a directory.

    Recognised by a header starting with ``Probe``. In a folder holding both
    raw exports and processed copies (``ExcelTime`` column), only one kind is
    kept: the raw exports, or the processed copies with `processed`. Folders
    whose name starts with ``_`` are skipped.
    """
    folders: dict[Path, list[Path]] = {}
    for f in walk_files(directory):
        if f.suffix.lower() in (".csv", ".txt") and header(f)[:1] == ["Probe"]:
            folders.setdefault(f.parent, []).append(f)
    files = []
    for in_folder in folders.values():
        kinds = {f: "ExcelTime" in header(f) for f in in_folder}
        if processed and any(kinds.values()):
            files += [f for f in in_folder if kinds[f]]
        else:
            files += [f for f in in_folder if not kinds[f]] or in_folder
    return sorted(files)


def header(path: StrPath) -> list[str]:
    """Column names on the first line of a file (``;`` or tab separated)."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        line = fh.readline().strip("\r\n")
    return line.split(";" if ";" in line else "\t")


def roma_serial(path: StrPath) -> str:
    """Probe number, from the first data row."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        fh.readline()
        first = fh.readline()
    return re.split(r"[;\t]", first, maxsplit=1)[0].strip()


def read_roma_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Read one CH4/CO2 probe file at native resolution.

    Rows written while the clock was reset are dropped; `ERROR_VALUE`
    temperatures become NaN. Raises ValueError without `utc_offset`.
    """
    path = Path(path)
    logging.info("Reading file: %s", path)
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    sep = ";" if ";" in lines[0] else "\t"
    names = lines[0].split(sep)
    rows = [line.split(sep) for line in lines[1:] if line.strip()]
    columns = {i: out for i, name in enumerate(names) if (out := column_name(name))}
    times = [row_time(r, names) for r in rows]
    keep = [i for i, t in enumerate(times) if t is not None]
    if dropped := len(rows) - len(keep):
        logging.info("%s: dropped %d rows with a reset clock", path, dropped)
    data = pd.DataFrame(
        {out: [rows[k][i] if i < len(rows[k]) else None for k in keep] for i, out in columns.items()}
    ).apply(pd.to_numeric, errors="coerce")
    for col in ("Tsensor_C", "Text_C"):
        if col in data:
            data[col] = data[col].where(~np.isclose(data[col], ERROR_VALUE))
    data.index = to_utc(pd.Series([times[k] for k in keep]), utc_offset, path)
    return data


def column_name(raw: str) -> str | None:
    """Output name of a raw column, or None for columns not kept."""
    raw = raw.strip()
    for prefix, out in COLUMNS.items():
        if raw == prefix or (prefix.startswith("T_") and raw.startswith(prefix + "(")):
            return out
    return None


def row_time(row: list[str], names: list[str]) -> datetime | None:
    """Logger time of one row, or None if the clock was reset."""
    try:
        if "ExcelTime" in names:
            days = float(row[names.index("ExcelTime")])
            return EXCEL_EPOCH + timedelta(minutes=round(days * 1440))
        date = row[1].strip()
        if re.match(r"\d{4}-", date):  # Excel-mangled: 20yy-mm-dd is really dd/mm/yy
            t = datetime.strptime(date[:16], "%Y-%m-%d %H:%M")
            stamp = t.replace(year=2000 + t.day, day=t.year % 100)
        else:
            stamp = datetime.strptime(date[:17], "%d/%m/%y %H:%M:%S")
    except (ValueError, IndexError):
        return None
    # A reset clock writes dates such as 00/00/00, 09/02/00 or 04/03/40; some
    # of them parse, but to years outside the probes' use
    return stamp if 2010 <= stamp.year <= datetime.now().year else None
