"""Reader for YSI EXO2 sonde exports (KOR software, CSV or Excel)."""

import logging
from pathlib import Path

import pandas as pd

from read_instruments.utils import Paths, StrPath, combine, detect_encoding, resolve_files

DATE_COL = "Date (MM/DD/YYYY)"
# KOR writes the date column header as MM/DD/YYYY even when dates are DD/MM/YYYY
DATE_FORMATS = ("%m/%d/%Y", "%d/%m/%Y")
FILE_SUFFIXES = (".csv", ".xls", ".xlsx")

# Metadata and position columns left out of the output
DROP_COLUMNS = [
    "Site Name",
    DATE_COL,
    "Time (HH:mm:ss)",
    "Time (HH:MM:SS)",
    "Time (Fract. Sec)",
    "Depth m",
    "Pressure psi a",
    "Vertical Position m",
    "Cable Pwr V",
]
# KOR header -> output name; unlisted columns keep their KOR header
COLUMN_NAMES = {
    "Battery V": "Battery_V",
    "BGA PC RFU": "BGAPC_RFU",
    "BGA PC ug/L": "BGAPC_ugL",
    "BGA PE RFU": "BGAPE_RFU",
    "BGA PE ug/L": "BGAPE_ugL",
    "Chlorophyll RFU": "Chl_RFU",
    "Chlorophyll ug/L": "Chl_ugL",
    "Cond µS/cm": "Cond_uScm",
    "fDOM QSU": "fDOM_QSU",
    "fDOM RFU": "fDOM_RFU",
    "nLF Cond µS/cm": "nLFCond_uScm",
    "ODO % CB": "ODO_pctCB",
    "ODO % local": "ODO_pctlocal",
    "ODO % sat": "ODO_pctsat",
    "ODO mg/L": "ODO_mgL",
    "pH": "pH",
    "pH mV": "pH_mV",
    "Sal psu": "Sal_psu",
    "SpCond µS/cm": "SpCond_uScm",
    "TDS mg/L": "TDS_mgL",
    "Temp °C": "Temp_C",
    "TSS mg/L": "TSS_mgL",
    "Turbidity FNU": "Turb_FNU",
}


def read_exo2(paths: Paths, resample: str | None = "1min") -> pd.DataFrame:
    """Read EXO2 data.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory of KOR exports, a single file, or a list of files.
    resample : str or None
        Frequency to average to; None keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        Indexed by UTC ``Datetime``; empty if no files were found.
    """
    logging.info("Reading EXO2 data")
    files = resolve_files(paths, find_exo2_files)
    if not files:
        logging.warning("No EXO2 files found in: %s", paths)
    return combine([read_exo2_file(f) for f in files], resample)


def find_exo2_files(directory: StrPath) -> list[Path]:
    """List CSV and Excel files in a directory."""
    return [
        f
        for f in sorted(Path(directory).iterdir())
        if f.is_file() and f.suffix.lower() in FILE_SUFFIXES
    ]


def read_exo2_file(path: StrPath) -> pd.DataFrame:
    """Read one KOR export (CSV or Excel) at native resolution."""
    path = Path(path)
    logging.info("Reading file: %s", path)
    if path.suffix.lower() == ".csv":
        skiprows, encoding, sep = find_header(path)
        data = pd.read_csv(path, sep=sep, skiprows=skiprows, encoding=encoding)
    else:
        raw = pd.read_excel(path)
        skiprows = raw.index[raw[raw.columns[0]] == DATE_COL][0] + 1
        data = pd.read_excel(path, skiprows=skiprows)

    time_col = data.columns[1]
    data = data.dropna(subset=data.columns[:3], how="all")
    # Concatenated exports repeat the header row
    data = data[data[DATE_COL] != DATE_COL]

    dates = parse_dates(data[DATE_COL], path)
    data.index = pd.DatetimeIndex(
        pd.to_datetime(
            dates.dt.strftime("%Y-%m-%d") + " " + data[time_col].astype(str),
            format="%Y-%m-%d %H:%M:%S",
        ),
        name="Datetime",
    ).tz_localize("UTC")

    data = data.drop(columns=[c for c in DROP_COLUMNS if c in data.columns])
    data = data.rename(columns=COLUMN_NAMES)
    return data.apply(pd.to_numeric, errors="coerce").astype(float)


def parse_dates(dates: pd.Series, path: StrPath) -> pd.Series:
    """Parse the date column, trying each of `DATE_FORMATS`."""
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(dates, format=fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format in {path}")


def find_header(path: StrPath) -> tuple[int, str | None, str]:
    """Locate the header row of a KOR CSV export.

    Returns the number of lines before the header, the file encoding, and the
    separator declared on the first line (``sep=,``).
    """
    encoding = detect_encoding(path)
    with open(path, encoding=encoding) as f:
        lines = f.readlines()
    sep = lines[0].split("=")[1].rstrip("\n")
    for idx, line in enumerate(lines):
        if DATE_COL in line.split(sep):
            return idx, encoding, sep
    raise ValueError(f"No '{DATE_COL}' header row in {path}")
