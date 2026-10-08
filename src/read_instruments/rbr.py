"""Reader for RBR loggers (e.g. TR-1060 temperature) exported from Ruskin as text.

Two Ruskin text exports are read:

- the ODV spreadsheet (``//`` comment header, then tab-separated ``Cruise
  Station Type yyyy-mm-ddThh:mm:ss.sss ... Temp [Degrees_C]``), which states no
  time zone;
- the plain export (``Model=...`` key/value header, then ``Date & Time  Temp``
  with ``Z``-suffixed, i.e. UTC, timestamps).
"""

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

# e.g. 020133_20160525_2051.txt (the .hex next to it is the binary original)
FILE_NAME = re.compile(r"(\d{6})_\d{8}_\d{4}\.txt")
SERIAL = re.compile(r"Serial=(\d+)")
# ODV columns that are not measurements
ODV_META = ["Cruise", "Station", "Type", "Longitude", "Latitude", "Bot. Depth", "Depth"]
# Ruskin channel unit -> output unit suffix
UNITS = {"Degrees_C": "C", "dbar": "dbar"}


def read_rbr(
    paths: Paths,
    serial: str | int | None = None,
    utc_offset: UtcOffset = None,
    resample: str | None = "1min",
) -> pd.DataFrame:
    """Read RBR data of one logger.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_rbr_files`), a single
        file, or a list of files.
    serial : str, int or None
        Logger to read. Needed when the files come from several loggers.
    utc_offset : str, float or None
        Logger clock offset (e.g. ``"UTC+02:00"``). Required for ODV exports,
        which state no time zone; overrides the ``Z`` of plain exports.
    resample : str or None
        Frequency to average to; None keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        One column per channel (e.g. ``Temp_C``) indexed by UTC ``Datetime``;
        empty if no files were found.
    """
    logging.info("Reading RBR data")
    files = check_one_logger(resolve_files(paths, find_rbr_files), rbr_serial, serial)
    if not files:
        logging.warning("No RBR files found in: %s", paths)
    return combine([read_rbr_file(f, utc_offset) for f in files], resample)


def find_rbr_files(directory: StrPath) -> list[Path]:
    """List Ruskin text exports (``<serial>_<yyyymmdd>_<hhmm>.txt``) below a directory.

    Folders whose name starts with ``_`` are skipped.
    """
    return [f for f in walk_files(directory) if FILE_NAME.fullmatch(f.name)]


def rbr_serial(path: StrPath) -> str:
    """Serial number of the logger that wrote a Ruskin export."""
    with open(path, encoding="latin-1") as fh:
        for _, line in zip(range(30), fh):
            if match := SERIAL.search(line):
                return match.group(1)
    raise ValueError(f"{path}: no RBR serial number found")


def read_rbr_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Read one Ruskin text export at native resolution."""
    path = Path(path)
    logging.info("Reading file: %s", path)
    with open(path, encoding="latin-1") as fh:
        first = fh.readline()
    if first.startswith("//"):
        return read_odv(path, utc_offset)
    return read_plain(path, utc_offset)


def read_odv(path: Path, utc_offset: UtcOffset) -> pd.DataFrame:
    """Read a Ruskin ODV spreadsheet export; the time zone must be given."""
    n_comments = 0
    with open(path, encoding="latin-1") as fh:
        for line in fh:
            if not line.startswith("//"):
                break
            n_comments += 1
    with open(path, encoding="latin-1") as fh:
        for _ in range(n_comments):
            fh.readline()
        columns = [c for c in fh.readline().rstrip("\r\n").split("\t") if c.strip()]
    channels = [c for c in columns if not c.startswith(("yyyy", *ODV_META))]
    # Data rows leave out one of the depth fields that the header names, so
    # channels are matched from the end of the row (after the trailing tab)
    raw = pd.read_csv(
        path, sep="\t", skiprows=n_comments + 1, header=None, encoding="latin-1", dtype={3: str}
    ).dropna(axis=1, how="all")
    data = raw.iloc[:, -len(channels) :].set_axis(
        [channel_name(c) for c in channels], axis=1
    ).apply(pd.to_numeric)
    data.index = to_utc(pd.to_datetime(raw[3], format="%Y-%m-%dT%H:%M:%S.%f"), utc_offset, path)
    return data


def read_plain(path: Path, utc_offset: UtcOffset) -> pd.DataFrame:
    """Read a Ruskin plain export (``Z`` timestamps, i.e. UTC unless overridden).

    Some of these exports hold uncalibrated thermistor ratios rather than
    degrees (values between 0 and 1); that channel is then named ``Temp_raw``.
    """
    lines = path.read_text(encoding="latin-1").splitlines()
    head = next(i for i, line in enumerate(lines) if line.strip().startswith("Date & Time"))
    names = re.split(r"\s{2,}", lines[head].strip())[1:]
    rows = [line.split() for line in lines[head + 1 :] if line.strip()]
    times = pd.to_datetime([f"{r[0]} {r[1].rstrip('Z')}" for r in rows], format="%Y-%m-%d %H:%M:%S.%f")
    data = pd.DataFrame([r[2:] for r in rows], columns=names).apply(pd.to_numeric)
    renamed = {}
    for name in names:
        values = data[name]
        if name.startswith("Temp") and values.between(0, 1).all():
            logging.warning("%s: %s looks uncalibrated (values 0-1); named Temp_raw", path, name)
            renamed[name] = "Temp_raw"
        else:
            renamed[name] = f"{name}_C" if name.startswith("Temp") else name
    data = data.rename(columns=renamed)
    data.index = to_utc(times, "UTC" if utc_offset is None else utc_offset, path)
    return data


def channel_name(column: str) -> str:
    """``Temp [Degrees_C]`` -> ``Temp_C``; unknown units are kept as written."""
    match = re.fullmatch(r"(\w+)\s*\[(.*)\]", column.strip())
    if not match:
        return column.strip()
    quantity, unit = match.groups()
    return f"{quantity}_{UNITS.get(unit, unit)}"
