"""Reader for LGR greenhouse gas analyser files."""

import io
import logging
import re
import zipfile
from pathlib import Path

import pandas as pd

from aphys_readers.utils import Paths, StrPath, combine, resolve_files, walk_files

# Raw column position -> output name
COLUMNS = {
    0: "Datetime",
    3: "H2O_ppm",
    7: "CH4d_ppm",
    9: "CO2d_ppm",
    11: "GasP_torr",
    13: "GasT_C",
    17: "RD0_us",
    19: "RD1_us",
}
# Data files, plain or zipped, e.g. fgga_2020-07-16_f0000.txt(.zip)
FILE_NAME = re.compile(r".+_f\d{4}\.txt(\.zip)?")


def read_lgr(paths: Paths, resample: str | None = "1min") -> pd.DataFrame:
    """Read LGR data.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_lgr_files`), a single
        file, or a list of files.
    resample : str or None
        Frequency to average to; None keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        Indexed by UTC ``Datetime``; empty if no files were found.
    """
    logging.info("Reading LGR data")
    files = resolve_files(paths, find_lgr_files)
    if not files:
        logging.warning("No LGR files found in: %s", paths)
    return combine([read_lgr_file(f) for f in files], resample)


def find_lgr_files(directory: StrPath) -> list[Path]:
    """List LGR data files anywhere below a directory.

    Picks up non-empty files named like ``fgga_2020-07-16_f0000.txt``, plain or
    zipped (``.txt.zip``). Folders whose name starts with ``_`` (e.g.
    ``_superseded``) are skipped, and a plain file is skipped when its zipped
    copy is also present.
    """
    return [
        f
        for f in walk_files(directory)
        if FILE_NAME.fullmatch(f.name) and not f.with_name(f.name + ".zip").exists()
    ]


def read_lgr_file(path: StrPath) -> pd.DataFrame:
    """Read one LGR file (plain text or zipped) at native resolution."""
    path = Path(path)
    logging.info("Reading file: %s", path)
    is_zip = zipfile.is_zipfile(path)
    data = pd.read_csv(
        path,
        sep=",",
        header=1,
        skipfooter=footer_pos(path),
        compression="zip" if is_zip else None,
        skipinitialspace=True,
        parse_dates=[0],
        index_col=[0],
        date_format="%m/%d/%Y %H:%M:%S.%f",
        usecols=list(COLUMNS),
        names=list(COLUMNS.values()),
        engine="python",
    )
    data.index = pd.DatetimeIndex(data.index).tz_localize("UTC")
    return data


def footer_pos(lgr_file: StrPath) -> int:
    """Number of lines in the footer (starting with ``-----B``) of an LGR file.

    Closed daily files end with a PGP signature block; files still being
    written, or older plain-text files, may have none.
    """
    lgr_file = Path(lgr_file)
    if zipfile.is_zipfile(lgr_file):
        with zipfile.ZipFile(lgr_file) as zipf:
            content = zipf.read(zipf.namelist()[0])
    else:
        content = lgr_file.read_bytes()
    lines = io.BytesIO(content).readlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(b"-----B")]
    return len(lines) - starts[-1] if starts else 0
