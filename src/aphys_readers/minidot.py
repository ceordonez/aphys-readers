"""Reader for PME miniDOT dissolved oxygen and temperature loggers."""

import io
import logging
import re
from pathlib import Path

import pandas as pd

from aphys_readers.utils import Paths, StrPath, check_one_logger, combine, resolve_files, walk_files

# Concatenated files written by miniDOTConcatenate (Cat.TXT), and the daily
# files they are built from, named by their start time in hex (e.g. 57A8BF40.txt)
CAT_FILE = re.compile(r"cat\w*\.txt", re.I)
DAILY_FILE = re.compile(r"[0-9A-F]{8}\.txt", re.I)
# "Sensor:  6881-1159" in Cat files; "6881-1159" on the first line of daily files
SERIAL = re.compile(r"^(?:Sensor:)?\s*\d+-(\d+)\s*$", re.M)
# Header text (Cat or daily file) -> output column
COLUMNS = {
    "unix timestamp": "Datetime",
    "time (sec)": "Datetime",
    "battery": "Battery_V",
    "bv (volts)": "Battery_V",
    "temperature": "Temp_C",
    "t (deg c)": "Temp_C",
    "dissolved oxygen": "ODO_mgL",
    "do (mg/l)": "ODO_mgL",
    "dissolved oxygen saturation": "ODO_pctsat",
    "q": "Q",
    "q ()": "Q",
}


def read_minidot(
    paths: Paths, serial: str | int | None = None, resample: str | None = "1min"
) -> pd.DataFrame:
    """Read miniDOT data of one logger.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_minidot_files`), a single
        file, or a list of files.
    serial : str, int or None
        Logger to read (e.g. ``1159`` for sensor 6881-1159). Needed when the
        files come from several loggers.
    resample : str or None
        Frequency to average to; None keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        ``Temp_C``, ``ODO_mgL``, ``ODO_pctsat`` (Cat files only), ``Q`` and,
        from newer firmware, ``Battery_V``, indexed by UTC ``Datetime``; empty
        if no files were found.
    """
    logging.info("Reading miniDOT data")
    files = check_one_logger(resolve_files(paths, find_minidot_files), minidot_serial, serial)
    if not files:
        logging.warning("No miniDOT files found in: %s", paths)
    return combine([read_minidot_file(f) for f in files], resample)


def find_minidot_files(directory: StrPath) -> list[Path]:
    """List miniDOT files below a directory, one set per folder.

    A folder's concatenated ``Cat*.TXT`` file is used when it has one;
    otherwise its daily files (``<8 hex digits>.txt``). Other text files, such
    as processed copies, are ignored. Folders whose name starts with ``_`` are
    skipped.
    """
    folders: dict[Path, list[Path]] = {}
    for f in walk_files(directory):
        folders.setdefault(f.parent, []).append(f)
    files = []
    for in_folder in folders.values():
        cat = [f for f in in_folder if CAT_FILE.fullmatch(f.name)]
        files += cat or [f for f in in_folder if DAILY_FILE.fullmatch(f.name)]
    return sorted(files)


def minidot_serial(path: StrPath) -> str:
    """Serial number of the logger (``1159`` for sensor ``6881-1159``)."""
    with open(path, encoding="latin-1") as fh:
        head = "".join(line for _, line in zip(range(5), fh))
    match = SERIAL.search(head)
    if not match:
        raise ValueError(f"{path}: no miniDOT serial number found")
    return match.group(1)


def read_minidot_file(path: StrPath) -> pd.DataFrame:
    """Read one miniDOT file (concatenated ``Cat`` file or daily file) at native resolution.

    Times come from the Unix timestamps, which are UTC.
    """
    path = Path(path)
    logging.info("Reading file: %s", path)
    lines = path.read_text(encoding="latin-1").splitlines()
    head = next(
        i for i, line in enumerate(lines) if re.match(r"\s*(Unix Timestamp|Time \(sec\))", line)
    )
    if "," in lines[head]:  # Cat file: comma-separated header, then a units line
        names = [c.strip().lower() for c in lines[head].split(",")]
        first = head + 2
    else:  # daily file: header fields separated by two spaces
        names = [c.strip().lower() for c in re.split(r"\s{2,}", lines[head].strip())]
        first = head + 1
    data = pd.read_csv(
        io.StringIO("\n".join(lines[first:])),
        header=None,
        names=[COLUMNS.get(n, n) for n in names],
        skipinitialspace=True,
    )
    data = data[[c for c in data.columns if c in COLUMNS.values()]]
    data.index = pd.to_datetime(data.pop("Datetime"), unit="s", utc=True).rename("Datetime")
    return data
