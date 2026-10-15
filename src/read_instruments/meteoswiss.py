"""Reader for MeteoSwiss open data (OGD) station files.

The files come from MeteoSwiss (https://opendatadocs.meteoswiss.ch), one per
station, granularity and update period, e.g. ``ogd-smn_ego_t_historical_2010-2019.csv``:
network (``smn`` = SwissMetNet), station abbreviation, granularity (``t``
10-min, ``h`` hourly, ``d`` daily, ``m`` monthly, ``y`` yearly), and
``historical`` (up to the end of last year), ``recent`` (this year) or ``now``
(the last day, not yet checked).

They are ``;``-separated, Windows-1252, with a ``station_abbr`` column, a
``reference_timestamp`` (``dd.mm.yyyy HH:MM``, UTC) and one column per
parameter short name (``tre200s0`` = air temperature 2 m above ground, current
value). Missing values are empty fields; parameters not measured at the
station are empty columns. ``ogd-smn_meta_parameters.csv`` describes every
parameter.

Timestamps are kept as published. For 10-min and hourly files they mark the
end of the interval (``16:00`` = 15:50:01-16:00:00 for 10-min means and
totals; current values are taken at that time); for daily, monthly and yearly
files they mark the start.
"""

import logging
import re
from pathlib import Path

import pandas as pd

from read_instruments.utils import Paths, StrPath, check_one_logger, combine, resolve_files, walk_files

# ogd-<network>_<station>_<granularity>_<period>[_<years>].csv
FILE_NAME = re.compile(r"ogd-[a-z]+_([a-z0-9]+)_([tdhmy])_(historical|recent|now)([_-].*)?\.csv$", re.I)
TIME_FORMAT = "%d.%m.%Y %H:%M"
ENCODING = "cp1252"
# Parameter short name -> output name (10-min parameters); others keep their short name
COLUMN_NAMES = {
    "tre200s0": "Tair_C",  # 2 m above ground
    "tre005s0": "Tair5cm_C",  # 5 cm above grass
    "tresurs0": "Tsurf_C",
    "xchills0": "Tchill_C",
    "tde200s0": "Tdew_C",
    "ure200s0": "RH_pct",
    "pva200s0": "VapPress_hPa",
    "prestas0": "Press_hPa",  # QFE, at the station
    "pp0qnhs0": "PressQNH_hPa",
    "pp0qffs0": "PressQFF_hPa",
    "ppz850s0": "Z850_gpm",
    "ppz700s0": "Z700_gpm",
    "fkl010z0": "WS_ms",  # scalar 10-min mean, 10 m
    "fve010z0": "WSvec_ms",  # vector 10-min mean
    "dkl010z0": "WD_deg",
    "fkl010z1": "Gust1s_ms",
    "fkl010z3": "Gust3s_ms",
    "fu3010z0": "WS_kmh",
    "fu3010z1": "Gust1s_kmh",
    "fu3010z3": "Gust3s_kmh",
    "wcc006s0": "Foehn_code",
    "rre150z0": "Precip_mm",  # 10-min total
    "htoauts0": "Snow_cm",
    "gre000z0": "SWin_Wm2",  # global radiation
    "ods000z0": "SWdiff_Wm2",
    "osr000z0": "SWout_Wm2",
    "oli000z0": "LWin_Wm2",
    "olo000z0": "LWout_Wm2",
    "sre000z0": "Sunshine_min",  # 10-min total
    "tso005s0": "Tsoil5cm_C",
    "tso010s0": "Tsoil10cm_C",
    "tso020s0": "Tsoil20cm_C",
}


def read_meteoswiss(
    paths: Paths,
    station: str | None = None,
    granularity: str = "t",
    resample: str | None = None,
) -> pd.DataFrame:
    """Read MeteoSwiss station data of one station.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_meteoswiss_files`), a
        single file, or a list of files.
    station : str or None
        Station abbreviation (e.g. ``"EGO"``). Needed when the files come from
        several stations.
    granularity : str
        When searching a directory, the files to read: ``t`` (10-min), ``h``,
        ``d``, ``m`` or ``y``.
    resample : str or None
        Frequency to average to; None keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        One column per parameter (see `COLUMN_NAMES`), indexed by UTC
        ``Datetime`` as published (end of the interval for 10-min and hourly
        values); empty if no files were found.
    """
    logging.info("Reading MeteoSwiss data")
    files = resolve_files(paths, lambda d: find_meteoswiss_files(d, granularity))
    files = check_one_logger(files, meteoswiss_station, station and station.upper())
    if not files:
        logging.warning("No MeteoSwiss files found in: %s", paths)
    return combine([read_meteoswiss_file(f) for f in files], resample)


def find_meteoswiss_files(directory: StrPath, granularity: str = "t") -> list[Path]:
    """List MeteoSwiss data files of one granularity below a directory.

    The parameter, station and data-inventory metadata files are not listed.
    Folders whose name starts with ``_`` are skipped.
    """
    return [
        f
        for f in walk_files(directory)
        if (match := FILE_NAME.match(f.name)) and match.group(2).lower() == granularity.lower()
    ]


def meteoswiss_station(path: StrPath) -> str:
    """Station abbreviation of a MeteoSwiss file, from its name or first row."""
    match = FILE_NAME.match(Path(path).name)
    if match:
        return match.group(1).upper()
    with open(path, encoding=ENCODING) as fh:
        fh.readline()
        return fh.readline().split(";", 1)[0].strip().upper()


def read_meteoswiss_file(path: StrPath) -> pd.DataFrame:
    """Read one MeteoSwiss station file at native resolution.

    Columns empty over the whole file (parameters not measured at the station)
    are dropped.
    """
    logging.info("Reading file: %s", path)
    data = pd.read_csv(path, sep=";", encoding=ENCODING, dtype={"station_abbr": str})
    times = pd.to_datetime(data.pop("reference_timestamp"), format=TIME_FORMAT)
    data = data.drop(columns="station_abbr").apply(pd.to_numeric).astype(float).dropna(axis=1, how="all")
    data.index = pd.DatetimeIndex(times).tz_localize("UTC").rename("Datetime")
    return data.rename(columns=COLUMN_NAMES)
