"""Reader for YSI EXO2 sonde exports (KOR software, CSV or Excel).

Older KOR versions write mixed-case headers (``Date (MM/DD/YYYY)``, ``Temp °C``)
with the date first; newer ones write upper-case headers (``TIME (HH:MM:SS)``,
``DATE (MM/DD/YYYY)``, ``TEMP °C``), may use ``;`` with decimal commas, and list
rows newest first. Headers are therefore matched case-insensitively.
"""

import codecs
import io
import logging
import re
from pathlib import Path

import pandas as pd

from read_instruments.utils import (
    Paths,
    StrPath,
    combine,
    detect_encoding,
    resolve_files,
    walk_files,
)

DATE_COL = "DATE (MM/DD/YYYY)"
TIME_COL_PREFIX = "TIME (HH:"
FRACT_COL = "TIME (FRACT. SEC)"
FILE_SUFFIXES = (".csv", ".xls", ".xlsx")
# Multi-part CSV exports of one recording end in _1, _2, ...
PART_SUFFIX = re.compile(r"_\d{1,2}$")

# Metadata columns left out of the output
DROP_COLUMNS = [
    "Site Name",
    "File Name",
    "User ID",
    "Fault Code",
    "Date (MM/DD/YYYY)",
    "Time (HH:mm:ss)",
    "Time (Fract. Sec)",
    # With sep=".", this header and its values (0.0) are split in two
    "Time (Fract",
    "Sec)",
    "Cable Pwr V",
]
# KOR header -> output name; unlisted columns keep their KOR header
COLUMN_NAMES = {
    "Altitude m": "Alt_m",
    "Baro mmHg": "Baro_mmHg",
    "Barometer mmHg": "Baro_mmHg",
    "Battery V": "Battery_V",
    "BGA PC RFU": "BGAPC_RFU",
    "BGA PC ug/L": "BGAPC_ugL",
    "BGA PE RFU": "BGAPE_RFU",
    "BGA PE ug/L": "BGAPE_ugL",
    "Chlorophyll RFU": "Chl_RFU",
    "Chlorophyll ug/L": "Chl_ugL",
    "Cond µS/cm": "Cond_uScm",
    # Depth from the non-vented pressure sensor, as computed by KOR
    "Depth m": "Depth_m",
    "fDOM QSU": "fDOM_QSU",
    "GPS Latitude °": "Lat_deg",
    "GPS Longitude °": "Lon_deg",
    "fDOM RFU": "fDOM_RFU",
    "nLF Cond µS/cm": "nLFCond_uScm",
    "ODO % CB": "ODO_pctCB",
    "ODO % EU": "ODO_pctEU",
    "ODO % local": "ODO_pctlocal",
    "ODO % sat": "ODO_pctsat",
    "ODO mg/L": "ODO_mgL",
    "ORP mV": "ORP_mV",
    "ORP raw mV": "ORPraw_mV",
    "pH": "pH",
    "pH mV": "pH_mV",
    "Press bar a": "Press_bara",
    "Pressure psi a": "Press_psia",
    "Sal psu": "Sal_psu",
    "SpCond µS/cm": "SpCond_uScm",
    "TDS mg/L": "TDS_mgL",
    "Temp °C": "Temp_C",
    "Temp C": "Temp_C",
    "TSS mg/L": "TSS_mgL",
    "Turbidity FNU": "Turb_FNU",
    "Vertical Position m": "VPos_m",
}

_DROP = {c.upper() for c in DROP_COLUMNS}
_RENAME = {k.upper(): v for k, v in COLUMN_NAMES.items()}


def read_exo2(paths: Paths, resample: str | None = "1min") -> pd.DataFrame:
    """Read EXO2 data.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_exo2_files`), a single
        file, or a list of files.
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
    """List KOR exports anywhere below a directory, one format per recording.

    KOR often exports the same recording several times: ``rec.xls``,
    ``rec.csv`` and/or ``rec_1.csv``, ``rec_2.csv``. Files are grouped by
    recording (folder and name without the part suffix); the CSV files of a
    recording are used when there are any, otherwise its Excel file. Rows
    repeated between a full CSV and its parts are removed by `combine`.
    Folders whose name starts with ``_`` (e.g. ``_superseded``) are skipped.
    """
    recordings: dict[tuple[Path, str], list[Path]] = {}
    for f in walk_files(directory):
        if f.suffix.lower() in FILE_SUFFIXES:
            key = (f.parent, PART_SUFFIX.sub("", f.stem))
            recordings.setdefault(key, []).append(f)
    files = []
    for group in recordings.values():
        csvs = [f for f in group if f.suffix.lower() == ".csv"]
        files += csvs or group
    return sorted(files)


def read_exo2_file(path: StrPath) -> pd.DataFrame:
    """Read one KOR export (CSV or Excel) at native resolution."""
    path = Path(path)
    logging.info("Reading file: %s", path)
    if path.suffix.lower() == ".csv":
        data, created = read_kor_csv(path)
    else:
        sheet, rows = kor_sheet(path)
        skiprows = header_rows(rows, path)[0]
        created = file_created(rows[:skiprows])
        data = pd.read_excel(path, sheet_name=sheet, skiprows=skiprows)
        data.columns = [normalise_header(c) for c in data.columns]

    time_col = next(c for c in data.columns if c.startswith(TIME_COL_PREFIX))
    # Summary lines (MEAN VALUE, SENSOR SERIAL NUMBER) and repeated headers
    # have no date
    data = data.dropna(subset=[DATE_COL])
    data = data[data[DATE_COL].astype(str).str.strip().str.upper() != DATE_COL]

    dates = parse_dates(data[DATE_COL], path, date_formats(created))
    data.index = pd.DatetimeIndex(
        pd.to_datetime(
            dates.dt.strftime("%Y-%m-%d") + " " + data[time_col].astype(str).str.strip(),
            format="%Y-%m-%d %H:%M:%S",
        ),
        name="Datetime",
    ).tz_localize("UTC")
    # Sampling faster than 1 Hz puts the sub-second part in its own column
    if FRACT_COL in data:
        fraction = to_number(data[FRACT_COL]).fillna(0.0).to_numpy()
        data.index = (data.index + pd.to_timedelta(fraction, unit="s")).rename("Datetime")

    # UNNAMED: columns come from blank header cells
    data = data.drop(columns=[c for c in data.columns if c in _DROP or c.startswith("UNNAMED:")])
    data = data.rename(columns=lambda c: _RENAME.get(c, c))
    return data.apply(to_number)


def read_kor_csv(path: Path) -> tuple[pd.DataFrame, str | None]:
    """Parse a KOR CSV export into text columns with upper-case headers.

    The separator is declared on the first line (``sep=,``). A file may hold
    several exports one after another, each with its own summary lines,
    header row and columns; each section runs from its header to the next
    blank line, is parsed separately, and the sections are concatenated.
    Also returns the ``FILE CREATED`` stamp.
    """
    lines = decode(path).splitlines()
    sep = separator(lines, path)
    rows = [line.split(sep) for line in lines]
    starts = header_rows(rows, path)
    sections = []
    for start in starts:
        end = next((i for i in range(start + 1, len(lines)) if not lines[i].strip()), len(lines))
        section = pd.read_csv(io.StringIO("\n".join(lines[start:end])), sep=sep, dtype=str)
        section.columns = [normalise_header(c) for c in section.columns]
        sections.append(section)
    return pd.concat(sections, ignore_index=True), file_created(rows[: starts[0]])


def decode(path: Path) -> str:
    """Text of a CSV export.

    KOR writes UTF-16 or UTF-8; copies re-saved by Excel are often Windows
    Latin-1, which chardet can mistake for an East Asian encoding (garbling
    ``°`` and ``µ`` in the headers). So: UTF-16 when there is a BOM or chardet
    says so, else UTF-8 if the bytes are valid, else cp1252.
    """
    data = path.read_bytes()
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    encoding = detect_encoding(path)
    if encoding and encoding.lower().startswith("utf-16"):
        return data.decode(encoding)
    return data.decode("cp1252", errors="replace")


def separator(lines: list[str], path: StrPath) -> str:
    """CSV separator: declared on a ``sep=`` first line, else read off the header row.

    Older KOR exports have no ``sep=`` line, nor do copies re-saved by Excel.
    """
    if lines and lines[0].startswith("sep="):
        return lines[0].split("=", 1)[1]
    header = next((line for line in lines if DATE_COL in line.upper()), None)
    if header is None:
        raise ValueError(f"No '{DATE_COL}' header row in {path}")
    return max((";", ",", "\t"), key=header.count)


def normalise_header(column: object) -> str:
    """Upper-case header with the degree sign repaired.

    Files decoded in the wrong encoding show ``°`` as ``Â°`` or a replacement
    character.
    """
    text = str(column).strip().replace("Â°", "°").replace("�", "°")
    return text.upper()


def kor_sheet(path: Path) -> tuple[str | int, list[list[str]]]:
    """The sheet of an Excel export holding the KOR export, and its cells as text.

    Users sometimes add edited copies of the data as further sheets, which can
    come first (e.g. ``Sheet1 (2)`` before ``Sheet1``). The sheet starting
    with ``KOR Export File`` is used when there is one, otherwise the first
    sheet with a date header.
    """
    sheets = pd.read_excel(path, sheet_name=None, header=None)
    candidates = []
    for name, raw in sheets.items():
        rows = [["" if pd.isna(c) else str(c) for c in row] for row in raw.values.tolist()]
        if not any(c.strip().upper() == DATE_COL for row in rows for c in row):
            continue
        if rows and rows[0] and rows[0][0].strip().upper().startswith("KOR EXPORT"):
            return name, rows
        candidates.append((name, rows))
    if not candidates:
        raise ValueError(f"No '{DATE_COL}' header row in {path}")
    return candidates[0]


def to_number(column: pd.Series) -> pd.Series:
    """Convert a column to float; a comma in a value is a decimal comma.

    KOR writes no thousands separators, and a comma can only appear inside a
    value when it is not the separator.
    """
    if not pd.api.types.is_numeric_dtype(column):
        column = column.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(column, errors="coerce").astype(float)


def parse_dates(dates: pd.Series, path: StrPath, formats: tuple[str, ...]) -> pd.Series:
    """Parse the date column with the first of `formats` that fits every row.

    ``dd.mm.yyyy``, written by copies re-saved with a European locale, is
    tried last.
    """
    for fmt in (*formats, "%d.%m.%Y"):
        try:
            return pd.to_datetime(dates, format=fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format in {path}")


def date_formats(created: str | None) -> tuple[str, ...]:
    """Date formats to try, in order, given the ``FILE CREATED`` stamp.

    KOR labels the date column MM/DD/YYYY but writes dates in the exporting
    computer's locale, as it does the file creation stamp. The stamp decides
    the order: a day or month above 12 settles it; otherwise a 12-hour clock
    (``7/29/2020 1:36:35 PM``) means month-first and a 24-hour clock
    (``06/08/2023 20:44:08``) day-first. Without a stamp, month-first is tried
    first, as the header says.
    """
    day_first, month_first = ("%d/%m/%Y", "%m/%d/%Y"), ("%m/%d/%Y", "%d/%m/%Y")
    match = re.match(r"\s*(\d{1,2})/(\d{1,2})/\d{4}", created or "")
    if not match:
        return month_first
    if int(match[1]) > 12:
        return day_first
    if int(match[2]) > 12:
        return month_first
    return month_first if re.search(r"\b[AP]M\b", created or "", re.IGNORECASE) else day_first


def file_created(rows: list[list[str]]) -> str | None:
    """Value next to the ``FILE CREATED:`` label in the metadata rows, if any."""
    for row in rows:
        cells = [c.strip() for c in row]
        if not cells or not cells[0].upper().startswith("FILE CREATED:"):
            continue
        # Label and value in separate cells, or in one ("File Created:7/11/2018 ...")
        value = cells[0][len("FILE CREATED:") :].strip()
        if value:
            return value
        if len(cells) > 1:
            return cells[1]
    return None


def header_rows(rows: list[list[str]], path: StrPath) -> list[int]:
    """Indices of the rows with a ``DATE (MM/DD/YYYY)`` cell (any case)."""
    found = [
        idx for idx, row in enumerate(rows) if any(c.strip().upper() == DATE_COL for c in row)
    ]
    if not found:
        raise ValueError(f"No '{DATE_COL}' header row in {path}")
    return found
