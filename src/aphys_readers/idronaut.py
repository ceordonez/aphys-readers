"""Reader for Idronaut Ocean Seven CTD casts exported to text.

Tested on Ocean Seven 316Plus casts exported by REDAS (``BlueMap001.txt``).
The export starts with the instrument lines, then one line per column
(``Col 4 : Temperature [°C]``), the start and end times of the cast
(``29/01/2026 10:20:52``, day first), a blank line, a line of column titles
and comma-separated data. Sample times are the start time plus the
``Time(s)`` column.

The files do not state the clock's time zone, so `utc_offset` must be given.
"""

import logging
import re
from pathlib import Path

import pandas as pd

from aphys_readers.utils import Paths, StrPath, UtcOffset, combine, resolve_files, to_utc, walk_files

COLUMN = re.compile(r"Col\s+(\d+)\s*:\s*(.+?)\s*\[(.*)\]\s*$")
DATE = re.compile(r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$")
# Idronaut column title (without unit) -> output name
COLUMN_NAMES = {
    "Depth": "Depth_m",
    "Pressure": "Press_dbar",
    "Temperature": "Temp_C",
    "Conductivity": "Cond_mScm",
    "Conductivity @25°C": "SpCond_mScm",
    "Salinity": "Sal_psu",
    "Oxygen %": "DO_pctsat",
    "Oxygen mg/L": "DO_mgL",
    "PAR": "PAR",
    "TDS": "TDS_gL",
    "pH": "pH",
    "Turbidity": "Turb_NTU",
    "Chlorophyll": "Chl_ugL",
}


def read_idronaut(paths: Paths, utc_offset: UtcOffset = None, resample: str | None = None) -> pd.DataFrame:
    """Read Idronaut casts (a directory, a file, or a list of files).

    Native resolution by default (``resample=None``): casts last minutes. Each
    row keeps its cast in a ``Cast`` column (the file name).
    """
    files = resolve_files(paths, find_idronaut_files)
    return combine([read_idronaut_file(f, utc_offset) for f in files], resample)


def find_idronaut_files(directory: StrPath) -> list[Path]:
    """List the Idronaut text exports below a directory (``.txt`` files with ``Col 1 :`` lines)."""
    found = []
    for f in walk_files(directory):
        if f.suffix.lower() != ".txt":
            continue
        with open(f, encoding="latin-1") as fh:
            head = [next(fh, "") for _ in range(6)]
        if any(line.startswith("Col 1 :") for line in head):
            found.append(f)
    return found


def read_idronaut_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Read one Idronaut text export at native resolution."""
    path = Path(path)
    logging.info("Reading file: %s", path)
    lines = path.read_text(encoding="latin-1").splitlines()
    titles = {}
    for line in lines:
        if match := COLUMN.match(line):
            titles[int(match.group(1))] = match.group(2).strip()
    dates = [line.strip() for line in lines if DATE.match(line.strip())]
    if not titles or not dates:
        raise ValueError(f"{path}: not an Idronaut text export (no 'Col n :' lines or start time)")
    start = pd.to_datetime(dates[0], format="%d/%m/%Y %H:%M:%S")
    first_row = next(i for i, line in enumerate(lines) if line[:1].isdigit() and "," in line and not DATE.match(line.strip()))
    rows = [line.split(",") for line in lines[first_row:] if line.strip()]
    names = [titles[k + 1] for k in range(len(rows[0]))]
    data = pd.DataFrame(rows, columns=names).apply(pd.to_numeric, errors="coerce")
    elapsed = pd.to_timedelta(data.pop(names[0]), unit="s")  # Time(s)
    data.index = to_utc(start + elapsed, utc_offset, path)
    data = data.rename(columns=lambda c: COLUMN_NAMES.get(c.replace("�", "°"), c))
    data["Cast"] = path.stem
    return data
