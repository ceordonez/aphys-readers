"""Reader for Vemco Minilog-II-T temperature loggers (LoggerVUE ``.csv`` exports)."""

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

# e.g. Minilog-II-T_357451_20170828_1.csv (the .vld next to it is the binary original)
FILE_NAME = re.compile(r"Minilog-II-T_(\d+)_.*\.csv", re.I)
SERIAL = re.compile(r"Source Device:\s*Minilog-II-T-(\d+)")
# "Minilog Initialized: 2017-05-22 20:33:54 (UTC+2)": the clock's offset from UTC
TIME_ZONE = re.compile(r"\((UTC[+-]?\d*(?::\d\d)?)\)")
# Data rows: "2017-05-22,20:34:00,18.05" or "2017-08-28 20:32:00,19.64"
ROW = re.compile(r"(\d{4}-\d\d-\d\d)[ ,](\d\d:\d\d:\d\d),([-\d.]+)")


def read_vemco(
    paths: Paths,
    serial: str | int | None = None,
    utc_offset: UtcOffset = None,
    resample: str | None = "1min",
) -> pd.DataFrame:
    """Read Vemco Minilog-II-T data of one logger.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_vemco_files`), a single
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
        ``Temp_C`` indexed by UTC ``Datetime``; empty if no files were found.
    """
    logging.info("Reading Vemco data")
    files = check_one_logger(resolve_files(paths, find_vemco_files), vemco_serial, serial)
    if not files:
        logging.warning("No Vemco files found in: %s", paths)
    return combine([read_vemco_file(f, utc_offset) for f in files], resample)


def find_vemco_files(directory: StrPath) -> list[Path]:
    """List Vemco exports (``Minilog-II-T_<serial>_*.csv``) below a directory.

    Folders whose name starts with ``_`` are skipped.
    """
    return [f for f in walk_files(directory) if FILE_NAME.fullmatch(f.name)]


def vemco_serial(path: StrPath) -> str:
    """Serial number of the logger that wrote a Vemco export (from its header)."""
    with open(path, encoding="latin-1") as fh:
        for _, line in zip(range(20), fh):
            if match := SERIAL.search(line):
                return match.group(1)
    match = FILE_NAME.fullmatch(Path(path).name)
    if not match:
        raise ValueError(f"{path}: no Vemco serial number found")
    return match.group(1)


def read_vemco_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Read one Vemco export at native resolution.

    The clock offset is taken from the ``Minilog Initialized ... (UTC+2)``
    header line unless `utc_offset` is given.
    """
    path = Path(path)
    logging.info("Reading file: %s", path)
    text = path.read_text(encoding="latin-1")
    if utc_offset is None and (match := TIME_ZONE.search(text[:2000])):
        utc_offset = match.group(1)
    rows = ROW.findall(text)
    return pd.DataFrame(
        {"Temp_C": pd.to_numeric([r[2] for r in rows])},
        index=to_utc(
            pd.to_datetime([f"{d} {t}" for d, t, _ in rows], format="%Y-%m-%d %H:%M:%S"),
            utc_offset,
            path,
        ),
    )
