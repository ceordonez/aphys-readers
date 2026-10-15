"""Reader for Campbell Scientific data logger tables (``TOA5`` text files).

Tested on a METER ATMOS 41 weather station logged by a CR200 (table
``Atmos41_10min``). A ``TOA5`` file has four header lines: the environment
(``"TOA5"``, station name, logger model, logger serial, OS version, program,
program signature, table name), the field names, their units and their
processing (``Avg``, ``Smp``, ``Tot``, ``Min``...), then one quoted
``TIMESTAMP`` and the values per row. ``NAN`` marks missing values.

A logger writes one file per table (e.g. 10-min and daily), and each download
repeats everything still in its memory, so files overlap.

Timestamps are written by the logger clock, whose time zone the file does not
state, so `utc_offset` must be given. For averages and totals the timestamp is
the end of the interval; it is kept as recorded.
"""

import csv
import logging
from pathlib import Path

import pandas as pd

from read_instruments.utils import Paths, StrPath, UtcOffset, combine, resolve_files, to_utc, walk_files

# Field name -> output name (METER ATMOS 41 program); others keep their field name
COLUMN_NAMES = {
    "Rad_Avg": "SWin_Wm2",
    "AirTemp_Avg": "Tair_C",
    "AirPress_Avg": "Press_kPa",
    "VaporPress_Avg": "VapPress_kPa",
    "RH_Avg": "RH_pct",
    "WDirection_Avg": "WD_deg",
    "WSpeed_Avg": "WS_ms",
    "WDirection": "WDsmp_deg",
    "WSpeed": "WSsmp_ms",
    "gWSpeed_Tot": "Gust_ms",
    "Pp_Tot": "Precip_mm",
    "batt_volt_Min": "Battery_V",
}
DROP_COLUMNS = ("RECORD",)


def read_campbell(
    paths: Paths,
    utc_offset: UtcOffset = None,
    table: str | None = None,
    resample: str | None = None,
) -> pd.DataFrame:
    """Read Campbell ``TOA5`` tables of one logger table.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_campbell_files`), a single
        file, or a list of files.
    utc_offset : str, float or None
        Logger clock offset (e.g. ``"UTC+01:00"``); required, as the files
        state no time zone.
    table : str or None
        Table to read (e.g. ``"Atmos41_10min"``). Needed when the files hold
        several tables.
    resample : str or None
        Frequency to average to; None (default) keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        One column per field (see `COLUMN_NAMES`), indexed by UTC
        ``Datetime`` (end of the interval for averages and totals); empty if
        no files were found.
    """
    logging.info("Reading Campbell data")
    files = resolve_files(paths, find_campbell_files)
    tables = {f: campbell_table(f) for f in files}
    if table is not None:
        files = [f for f in files if tables[f] == table]
    elif len(set(tables.values())) > 1:
        raise ValueError(f"Files from several tables ({', '.join(sorted(set(tables.values())))}); pass table=")
    if not files:
        logging.warning("No Campbell files found in: %s", paths)
    return combine([read_campbell_file(f, utc_offset) for f in files], resample)


def find_campbell_files(directory: StrPath) -> list[Path]:
    """List ``TOA5`` files below a directory, whatever their extension.

    Folders whose name starts with ``_`` are skipped.
    """
    return [f for f in walk_files(directory) if is_toa5(f)]


def is_toa5(path: StrPath) -> bool:
    """Whether a file is a Campbell ``TOA5`` table."""
    with open(path, "rb") as fh:
        return fh.read(6) == b'"TOA5"'


def environment(path: StrPath) -> list[str]:
    """Fields of the first header line: TOA5, station, model, serial, OS, program, signature, table."""
    with open(path, encoding="latin-1", newline="") as fh:
        return next(csv.reader(fh))


def campbell_table(path: StrPath) -> str:
    """Table name of a ``TOA5`` file (e.g. ``Atmos41_10min``)."""
    return environment(path)[7]


def read_campbell_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Read one ``TOA5`` file at native resolution.

    Raises ValueError without `utc_offset`, since the files state no time zone.
    """
    logging.info("Reading file: %s", path)
    data = pd.read_csv(path, skiprows=[0, 2, 3], na_values=["NAN", "INF", "-INF"], encoding="latin-1")
    times = pd.to_datetime(data.pop("TIMESTAMP"), format="ISO8601")
    data = data.drop(columns=[c for c in DROP_COLUMNS if c in data]).apply(pd.to_numeric).astype(float)
    data.index = to_utc(times, utc_offset, path)
    return data.rename(columns=COLUMN_NAMES)
