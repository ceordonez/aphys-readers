"""Reader for Sea-Bird CTD casts converted to text (``.cnv``, SBE Data Processing).

Tested on SBE 19plus V2 casts uploaded with SeaTerm and converted with
DatCnv. A ``.cnv`` has a ``*`` header (instrument, ``* cast`` line), a ``#``
header (``# name i = <short name>: <description>``, ``# start_time``,
``# interval``, ``# bad_flag``, processing history), ``*END*``, and then
whitespace-separated columns in the order of the ``# name`` lines.

SeaTerm can also save the same conversion split in two: a ``.hdr`` with the
header and an ``.asc`` with a line of column titles and the data. Such a pair
is read like a ``.cnv`` when there is no ``.cnv`` of the same name.

Sample times are ``start_time`` plus the elapsed time: the ``timeS`` or
``scan`` column when DatCnv wrote one, otherwise row number x ``interval``.
That only holds for files whose rows are consecutive scans, so files that went
through Bin Average are rejected.

When the file has no salinity column but has conductivity, temperature and
pressure, ``Sal_psu`` is computed with PSS-78 (``seawater.salinity_pss78``).

The pressure is sea pressure: the instrument subtracts a standard sea-level
atmosphere (10.1325 dbar), so on a lake above sea level it reads below zero at
the surface, and the depth columns computed from it are offset too. The
instrument clock is set from the computer that set it up and the files do not
state its time zone, so `utc_offset` must be given.
"""

import logging
import re
from pathlib import Path

import pandas as pd

from aphys_readers.seawater import salinity_pss78
from aphys_readers.utils import Paths, StrPath, UtcOffset, combine, resolve_files, to_utc, walk_files

NAME = re.compile(r"#\s*name\s+\d+\s*=\s*([^:]+):")
START_TIME = re.compile(r"#\s*start_time\s*=\s*(\w{3} \d{1,2} \d{4} \d{2}:\d{2}:\d{2})")
INTERVAL = re.compile(r"#\s*interval\s*=\s*seconds:\s*([\d.eE+-]+)")
BAD_FLAG = re.compile(r"#\s*bad_flag\s*=\s*([\d.eE+-]+)")
SERIAL = re.compile(r"SerialNumber='(\d+)'")
# Columns used for the time axis, dropped from the output
TIME_COLUMNS = ("timeS", "timeJ", "timeQ", "scan")
# SBE short name -> output name; unlisted columns keep their SBE name
COLUMN_NAMES = {
    "prdM": "Press_dbar",
    "prDM": "Press_dbar",
    "depFM": "Depth_m",  # fresh water
    "depSM": "Depth_m",  # salt water
    "t090C": "Temp_C",
    "tv290C": "Temp_C",
    "t190C": "Temp2_C",
    "potemp090C": "PotTemp_C",
    "c0uS/cm": "Cond_uScm",
    "c0mS/cm": "Cond_mScm",
    "c0S/m": "Cond_Sm",
    "specc": "SpCond_uScm",
    "sal00": "Sal_psu",
    "density00": "Density_kgm3",
    "sigma-t00": "SigmaT_kgm3",
    "dz/dtM": "DescentRate_ms",
    "sbeox0Mm/L": "DO_umolL",
    "sbeox0ML/L": "DO_mlL",
    "sbeox0Mg/L": "DO_mgL",
    "sbeox0PS": "DO_pctsat",
    "sbeox0V": "DO_V",
    "ph": "pH",
    "flECO-AFL": "Chl_mgm3",
    "turbWETntu0": "Turb_NTU",
    "par": "PAR",
    "flag": "Flag",
}


def read_seabird(
    paths: Paths, utc_offset: UtcOffset = None, resample: str | None = None
) -> pd.DataFrame:
    """Read Sea-Bird ``.cnv`` casts.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_seabird_files`), a single
        file, or a list of files.
    utc_offset : str, float or None
        Offset of the instrument clock (e.g. ``"UTC"``, ``"UTC+01:00"``).
        Required: the files do not state it.
    resample : str or None
        Frequency to average to; None (the default) keeps every scan, which is
        what a profile needs.

    Returns
    -------
    pandas.DataFrame
        Indexed by UTC ``Datetime``; empty if no files were found. Identical
        copies of a cast (e.g. re-exported under another name) are kept once.
    """
    logging.info("Reading Sea-Bird data")
    files = resolve_files(paths, find_seabird_files)
    if not files:
        logging.warning("No Sea-Bird files found in: %s", paths)
    return combine([read_seabird_file(f, utc_offset) for f in files], resample)


def find_seabird_files(directory: StrPath) -> list[Path]:
    """List ``.cnv`` files below a directory, and ``.asc`` files that have a
    ``.hdr`` but no ``.cnv`` of the same name; folders starting with ``_`` are
    skipped."""
    files = walk_files(directory)
    found = []
    for f in files:
        suffix = f.suffix.lower()
        if suffix == ".cnv":
            found.append(f)
        elif suffix == ".asc" and not sibling(f, ".cnv") and sibling(f, ".hdr"):
            found.append(f)
    return found


def sibling(path: Path, suffix: str) -> Path | None:
    """The file next to `path` with the same name and `suffix` (any case), if any."""
    for f in path.parent.glob(f"{path.stem}.*"):
        if f.suffix.lower() == suffix:
            return f
    return None


def seabird_serial(path: StrPath) -> str:
    """Serial number of the instrument, from the ``SerialNumber='...'`` header attribute."""
    with open(path, encoding="latin-1") as fh:
        for line in fh:
            if line.startswith("*END*"):
                break
            if match := SERIAL.search(line):
                return match.group(1)
    raise ValueError(f"{path}: no Sea-Bird serial number found")


def read_seabird_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Read one ``.cnv`` file, or an ``.asc`` with its ``.hdr``, at native
    resolution (one row per scan)."""
    path = Path(path)
    logging.info("Reading file: %s", path)
    header, body = split_file(path)

    names = [m.group(1).strip() for line in header if (m := NAME.match(line))]
    start = header_value(header, START_TIME, path, "start_time")
    interval = float(header_value(header, INTERVAL, path, "interval"))
    if any(line.startswith("# binavg_") for line in header):
        raise ValueError(f"{path}: bin-averaged file; rows are not consecutive scans")

    rows = [line.split() for line in body if line.strip()]
    data = pd.DataFrame(rows, columns=names).apply(pd.to_numeric)
    if bad := [m.group(1) for line in header if (m := BAD_FLAG.match(line))]:
        data = data.mask(data == float(bad[0]))

    if "timeS" in data:
        elapsed = pd.to_timedelta(data["timeS"], unit="s")
    elif "scan" in data:
        elapsed = pd.to_timedelta((data["scan"] - data["scan"].iloc[0]) * interval, unit="s")
    else:
        elapsed = pd.to_timedelta(data.index * interval, unit="s")
    times = pd.to_datetime(start, format="%b %d %Y %H:%M:%S") + elapsed
    data.index = to_utc(times, utc_offset, path)

    data = data.drop(columns=[c for c in TIME_COLUMNS if c in data])
    data = data.rename(columns=lambda c: COLUMN_NAMES.get(c, c))
    if "Sal_psu" not in data and {"Temp_C", "Press_dbar"} <= set(data.columns):
        cond = conductivity_mscm(data)
        if cond is not None:
            data["Sal_psu"] = salinity_pss78(cond, data["Temp_C"], data["Press_dbar"])
    return data


def conductivity_mscm(data: pd.DataFrame) -> pd.Series | None:
    """Conductivity in mS/cm from whichever unit the file has, or None."""
    for column, factor in (("Cond_mScm", 1.0), ("Cond_uScm", 1e-3), ("Cond_Sm", 10.0)):
        if column in data:
            return data[column] * factor
    return None


def split_file(path: Path) -> tuple[list[str], list[str]]:
    """Header lines (up to ``*END*``) and data lines of a ``.cnv``, or of an
    ``.asc`` (data after its column-title line) with its ``.hdr``."""
    if path.suffix.lower() == ".asc":
        hdr = sibling(path, ".hdr")
        if hdr is None:
            raise ValueError(f"{path}: no .hdr next to the .asc")
        header = hdr.read_text(encoding="latin-1").splitlines()
        body = path.read_text(encoding="latin-1").splitlines()[1:]
    else:
        lines = path.read_text(encoding="latin-1").splitlines()
        header, body = lines, []
    end = next((i for i, line in enumerate(header) if line.startswith("*END*")), None)
    if end is None:
        raise ValueError(f"{path}: no *END* line in the header")
    if path.suffix.lower() != ".asc":
        body = header[end + 1 :]
    return header[:end], body


def header_value(header: list[str], pattern: re.Pattern[str], path: Path, label: str) -> str:
    """First match of `pattern` in the header lines; raises if there is none."""
    for line in header:
        if match := pattern.match(line):
            return match.group(1)
    raise ValueError(f"{path}: no '# {label}' line")
