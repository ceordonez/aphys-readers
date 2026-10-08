import os
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import chardet
import pandas as pd

# A single path, and what readers accept: a path or several paths
StrPath = str | os.PathLike[str]
Paths = StrPath | Iterable[StrPath]
# A clock offset from UTC: "UTC+02:00", "GMT+2", "+02:00", "UTC", or hours
UtcOffset = str | float | None
OFFSET = re.compile(r"\s*(?:UTC|GMT)?\s*(?:([+-])\s*(\d{1,2})(?::?(\d\d))?)?\s*", re.I)


def detect_encoding(file_path: StrPath, sample_size: int = 10000) -> str | None:
    """
    Detects the text encoding of a file using chardet.
    Reads up to `sample_size` bytes from the file.
    """
    with open(file_path, "rb") as f:
        raw_data = f.read(sample_size)
    result = chardet.detect(raw_data)
    return result["encoding"]


def walk_files(directory: StrPath) -> list[Path]:
    """All non-empty files below a directory, sorted.

    Folders whose name starts with ``_`` (e.g. ``_superseded``, holding earlier
    copies of a file) are skipped.
    """
    root = Path(directory)
    return [
        f
        for f in sorted(root.rglob("*"))
        if f.is_file()
        and not any(part.startswith("_") for part in f.relative_to(root).parts[:-1])
        and f.stat().st_size > 0
    ]


def resolve_files(paths: Paths, find_files: Callable[[Path], list[Path]]) -> list[Path]:
    """Turn a directory, a single file, or a list of files into a list of files.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory is searched with `find_files`; a file is read as is.
    find_files : callable
        Instrument-specific function returning the data files in a directory.

    Returns
    -------
    list of pathlib.Path
    """
    if isinstance(paths, (str, os.PathLike)):
        path = Path(paths)
        return find_files(path) if path.is_dir() else [path]
    return [Path(p) for p in paths]


def combine(frames: list[pd.DataFrame], resample: str | None = "1min") -> pd.DataFrame:
    """Concatenate per-file DataFrames into one time-sorted DataFrame.

    Parameters
    ----------
    frames : list of pandas.DataFrame
        DataFrames indexed by a UTC ``Datetime`` index.
    resample : str or None
        Pandas frequency to average to (e.g. ``"1min"``); None keeps the
        native instrument resolution.

    Returns
    -------
    pandas.DataFrame
        Empty when `frames` is empty.
    """
    if not frames:
        return pd.DataFrame([])
    data = pd.concat(frames).sort_index()
    # Overlapping exports repeat rows; keep only one copy of identical rows
    data = data[~data.reset_index().duplicated().to_numpy()]
    if resample:
        data = data.resample(resample).mean()
    return data


def offset_hours(offset: UtcOffset) -> float | None:
    """Hours east of UTC for an offset like ``"UTC+02:00"``, ``"GMT+1"`` or 2.

    Returns None for None; raises ValueError for text that is not an offset.
    """
    if offset is None or isinstance(offset, (int, float)):
        return offset
    match = OFFSET.fullmatch(offset)
    if not match or not offset.strip():
        raise ValueError(f"Not a UTC offset: {offset!r}")
    sign, hours, minutes = match.groups()
    if sign is None:
        return 0.0
    value = int(hours) + int(minutes or 0) / 60
    return -value if sign == "-" else value


def to_utc(times: pd.Series | pd.Index, offset: UtcOffset, path: StrPath) -> pd.DatetimeIndex:
    """UTC index from naive logger clock times and the logger's offset from UTC.

    Raises ValueError when the offset is unknown (the file states none and the
    caller gave none), rather than guessing.
    """
    hours = offset_hours(offset)
    if hours is None:
        raise ValueError(
            f"{path}: the file does not state its time zone; pass utc_offset "
            "(e.g. 'UTC+02:00')"
        )
    index = pd.DatetimeIndex(times) - pd.Timedelta(hours=hours)
    return index.tz_localize("UTC").rename("Datetime")


def check_one_logger(
    files: list[Path], serial_of: Callable[[Path], str], serial: str | int | None
) -> list[Path]:
    """Keep the files of one logger.

    Mooring folders hold many loggers of the same type; combining them would
    average different depths into one series. With `serial` given, only that
    logger's files are kept (serials are compared without leading zeros);
    otherwise all files must come from the same logger.
    """
    serials = {f: serial_of(f).lstrip("0") for f in files}
    if serial is not None:
        return [f for f in files if serials[f] == str(serial).lstrip("0")]
    found = sorted(set(serials.values()))
    if len(found) > 1:
        raise ValueError(f"Files from several loggers ({', '.join(found)}); pass serial=")
    return files


def merge_nearest(
    left: pd.DataFrame,
    right: pd.DataFrame,
    tolerance: str | pd.Timedelta | None = "1min",
) -> pd.DataFrame:
    """Add to each row of `left` the nearest-in-time row of `right`.

    Works for instruments with different sampling (e.g. 1 Hz LGR and sparse
    GPS fixes), so data need not be resampled to a common grid first.

    Parameters
    ----------
    left, right : pandas.DataFrame
        Reader outputs, indexed by a UTC ``Datetime`` index. Columns present
        in both get ``_x`` / ``_y`` suffixes. All-NaN rows of `right` (empty
        bins after resampling) are ignored.
    tolerance : str, pandas.Timedelta or None
        Largest time gap to match across (e.g. ``"1min"``); rows of `left`
        with no `right` row that close get NaN. None matches any gap.

    Returns
    -------
    pandas.DataFrame
        One row per row of `left`, same index.
    """
    left = left.sort_index()
    # Resampled frames have all-NaN rows for empty bins; never match those
    right = right.dropna(how="all").sort_index()
    # merge_asof needs both indexes in the same time unit (us vs ns)
    right.index = pd.DatetimeIndex(right.index).as_unit(pd.DatetimeIndex(left.index).unit)
    return pd.merge_asof(
        left,
        right,
        left_index=True,
        right_index=True,
        direction="nearest",
        tolerance=pd.Timedelta(tolerance) if tolerance is not None else None,
    )
