"""Reader for Kestrel weather meters (Kestrel LiNK ``.csv`` exports).

Tested on a Kestrel 5500 (LiNK 1.02) and a 5500L (LiNK 1.04). An export starts
with a ``Device Information:`` block (name, model, serial, firmware...), then
a blank line, the column names, one row of units, and the data. ``***`` marks
values the meter did not compute (e.g. wind direction without the vane).

Units follow the meter's settings and are spelled differently between LiNK
versions (``Celsius`` or ``Deg. C``), so output names take their unit from the
units row rather than assuming one.

The meter clock is set by the user and the export does not state its time
zone, so `utc_offset` must be given. Each export holds the whole meter memory,
so successive downloads overlap; identical rows are kept once.
"""

import csv
import logging
import re
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

SERIAL = re.compile(r"^Serial:,\s*(\S+)", re.M)
# Column name -> quantity; unlisted columns keep their name (without dots or spaces)
QUANTITIES = {
    "Temp": "Tair",
    "Wet Bulb Temp.": "Twet",
    "Rel. Hum.": "RH",
    # Barometric pressure is reduced to sea level; station pressure is absolute
    "Baro.": "Baro",
    "Station P.": "Press",
    "Altitude": "Alt",
    "Wind Speed": "WS",
    "Heat Index": "HeatIndex",
    "Dew Point": "Tdew",
    "Dens. Alt.": "DensAlt",
    "Crosswind": "Crosswind",
    "Headwind": "Headwind",
    "Mag. Dir.": "WDmag",
    "True Dir.": "WD",
    "Wind Chill": "WindChill",
}
# Unit as written by LiNK -> unit in the output name
UNITS = {
    "Celsius": "C",
    "Deg. C": "C",
    "Fahrenheit": "F",
    "Deg. F": "F",
    "%": "pct",
    "mb": "hPa",
    "hPa": "hPa",
    "inHg": "inHg",
    "psi": "psi",
    "Meters": "m",
    "m": "m",
    "Feet": "ft",
    "ft": "ft",
    "m/s": "ms",
    "km/h": "kmh",
    "mph": "mph",
    "kt": "kt",
    "Degrees": "deg",
}
MISSING = "***"


def read_kestrel(
    paths: Paths,
    utc_offset: UtcOffset = None,
    serial: str | int | None = None,
    resample: str | None = "1min",
) -> pd.DataFrame:
    """Read Kestrel weather data of one meter.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_kestrel_files`), a single
        file, or a list of files.
    utc_offset : str, float or None
        Meter clock offset (e.g. ``"UTC+02:00"``); required, as the exports
        state no time zone.
    serial : str, int or None
        Meter to read. Needed when the files come from several meters.
    resample : str or None
        Frequency to average to; None keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        One column per measured quantity (``Tair_C``, ``RH_pct``,
        ``Press_hPa``, ``WS_ms``, ...; see `QUANTITIES`), indexed by UTC
        ``Datetime``; empty if no files were found.
    """
    logging.info("Reading Kestrel data")
    files = check_one_logger(resolve_files(paths, find_kestrel_files), kestrel_serial, serial)
    if not files:
        logging.warning("No Kestrel files found in: %s", paths)
    return combine([read_kestrel_file(f, utc_offset) for f in files], resample)


def find_kestrel_files(directory: StrPath) -> list[Path]:
    """List Kestrel LiNK ``.csv`` exports below a directory.

    Recognised by their ``Device Information:`` first line. Folders whose
    name starts with ``_`` are skipped.
    """
    return [f for f in walk_files(directory) if f.suffix.lower() == ".csv" and is_kestrel(f)]


def is_kestrel(path: StrPath) -> bool:
    """Whether a file is a Kestrel LiNK export."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.readline().startswith("Device Information:")


def kestrel_serial(path: StrPath) -> str:
    """Serial number of the meter that wrote a Kestrel export."""
    match = SERIAL.search(Path(path).read_text(encoding="utf-8-sig", errors="replace")[:1000])
    if match is None:
        raise ValueError(f"{path}: not a Kestrel export")
    return match.group(1)


def column_name(name: str, unit: str) -> str:
    """Output name ``Quantity_unit`` for a LiNK column and its unit."""
    quantity = QUANTITIES.get(name, re.sub(r"[.\s]", "", name))
    unit = UNITS.get(unit, re.sub(r"[^\w%]", "", unit))
    return f"{quantity}_{unit}" if unit else quantity


def read_kestrel_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Read one Kestrel export at native resolution.

    Raises ValueError without `utc_offset`, since the exports state no time zone.
    """
    path = Path(path)
    logging.info("Reading file: %s", path)
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    head = next((i for i, line in enumerate(lines) if line.startswith("Time,")), None)
    if head is None:
        raise ValueError(f"{path}: no column header")
    names, units = csv.reader(lines[head : head + 2])
    # Rows end with a comma, leaving an empty last column
    names = [n for n in names if n]
    rows = [r[: len(names)] for r in csv.reader(lines[head + 2 :]) if any(r)]
    raw = pd.DataFrame(rows, columns=names)
    times = pd.to_datetime(raw.pop("Time"), format="%Y-%m-%d %H:%M:%S")
    data = raw.replace(MISSING, None).apply(pd.to_numeric).astype(float)
    data.columns = [column_name(n, u) for n, u in zip(names[1:], units[1:])]
    data.index = to_utc(times, utc_offset, path)
    return data
