"""Reader for Onset HOBO Pendant temperature/light loggers (HOBOware ``.csv`` exports)."""

import csv
import io
import logging
import re
from pathlib import Path

import pandas as pd

from read_instruments.utils import (
    Paths,
    StrPath,
    UtcOffset,
    check_one_logger,
    combine,
    resolve_files,
    to_utc,
    walk_files,
)

SERIAL = re.compile(r"LGR S/N: (\d+)")
# Date column header, e.g. "Date Time, GMT+02:00" or "Fecha Tiempo, GMT+02:00"
TIME_ZONE = re.compile(r"GMT([+-]\d\d:\d\d)")
# HOBOware writes month-first dates with a 12-hour clock in English and Spanish exports
DATE_FORMAT = "%m/%d/%y %I:%M:%S %p"


def read_hobo(
    paths: Paths,
    serial: str | int | None = None,
    utc_offset: UtcOffset = None,
    resample: str | None = "1min",
) -> pd.DataFrame:
    """Read HOBO Pendant data of one logger.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_hobo_files`), a single
        file, or a list of files.
    serial : str, int or None
        Logger to read. Needed when the files come from several loggers.
    utc_offset : str, float or None
        Clock offset (e.g. ``"UTC+02:00"``) overriding the one in the headers.
    resample : str or None
        Frequency to average to; None keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        ``Temp_C`` and ``Light_lux`` indexed by UTC ``Datetime``; empty if no
        files were found.
    """
    logging.info("Reading HOBO data")
    files = check_one_logger(resolve_files(paths, find_hobo_files), hobo_serial, serial)
    if not files:
        logging.warning("No HOBO files found in: %s", paths)
    return combine([read_hobo_file(f, utc_offset) for f in files], resample)


def find_hobo_files(directory: StrPath) -> list[Path]:
    """List HOBOware ``.csv`` exports below a directory.

    Recognised by the ``LGR S/N`` logger serial in their header. Folders whose
    name starts with ``_`` are skipped.
    """
    return [
        f for f in walk_files(directory) if f.suffix.lower() == ".csv" and header(f) is not None
    ]


def header(path: StrPath) -> str | None:
    """Column header line of a HOBOware export, or None for other files."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for _, line in zip(range(3), fh):
            if SERIAL.search(line):
                return line
    return None


def hobo_serial(path: StrPath) -> str:
    """Serial number of the logger that wrote a HOBOware export."""
    match = SERIAL.search(header(path) or "")
    if match is None:
        raise ValueError(f"{path}: not a HOBOware export")
    return match.group(1)


def read_hobo_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Read one HOBOware export at native resolution.

    The clock offset is taken from the date column header (``GMT+02:00``)
    unless `utc_offset` is given. Rows holding only logger events (coupler
    attached, end of file, ...) are dropped.
    """
    path = Path(path)
    logging.info("Reading file: %s", path)
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    head = next(i for i, line in enumerate(lines[:3]) if SERIAL.search(line))
    columns = next(csv.reader([lines[head]]))
    if utc_offset is None and (match := TIME_ZONE.search(columns[1])):
        utc_offset = match.group(1)
    temp = next(i for i, c in enumerate(columns) if c.startswith("Temp"))
    light = next((i for i, c in enumerate(columns) if re.match(r"Intens", c, re.I)), None)
    raw = pd.read_csv(io.StringIO("\n".join(lines[head + 1 :])), header=None, dtype=str)
    names = {1: "Datetime", temp: "Temp_C"} | ({light: "Light_lux"} if light is not None else {})
    raw = raw[list(names)].rename(columns=names)
    raw = raw.dropna(subset=[c for c in raw.columns if c != "Datetime"], how="all")
    times = pd.to_datetime(raw.pop("Datetime"), format=DATE_FORMAT)
    data = raw.apply(pd.to_numeric)
    data.index = to_utc(times, utc_offset, path)
    return data
