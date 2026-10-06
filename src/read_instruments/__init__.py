"""Readers for Aquatic Physics group instruments.

Every reader returns a DataFrame indexed by a UTC ``Datetime`` index with
``Quantity_unit`` column names.
"""

from read_instruments.exo2 import find_exo2_files, read_exo2, read_exo2_file
from read_instruments.gps import find_gps_files, read_gps, read_gps_file
from read_instruments.lgr import find_lgr_files, read_lgr, read_lgr_file
from read_instruments.utils import combine, detect_encoding, merge_nearest

__all__ = [
    "read_exo2",
    "read_exo2_file",
    "find_exo2_files",
    "read_gps",
    "read_gps_file",
    "find_gps_files",
    "read_lgr",
    "read_lgr_file",
    "find_lgr_files",
    "combine",
    "detect_encoding",
    "merge_nearest",
]
