import os
from collections.abc import Callable, Iterable
from pathlib import Path

import chardet
import pandas as pd

# A single path, and what readers accept: a path or several paths
StrPath = str | os.PathLike[str]
Paths = StrPath | Iterable[StrPath]


def detect_encoding(file_path: StrPath, sample_size: int = 10000) -> str | None:
    """
    Detects the text encoding of a file using chardet.
    Reads up to `sample_size` bytes from the file.
    """
    with open(file_path, "rb") as f:
        raw_data = f.read(sample_size)
    result = chardet.detect(raw_data)
    return result["encoding"]


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
