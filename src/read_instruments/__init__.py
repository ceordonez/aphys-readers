"""Readers for Aquatic Physics group instruments.

Every reader returns a DataFrame indexed by a UTC ``Datetime`` index with
``Quantity_unit`` column names. Loggers whose clocks are not on UTC are
converted using the offset in their files or the ``utc_offset`` argument.
MeteoSwiss station data (``read_meteoswiss``) are read the same way.
"""

from read_instruments.campbell import find_campbell_files, read_campbell, read_campbell_file
from read_instruments.exo2 import find_exo2_files, read_exo2, read_exo2_file
from read_instruments.gps import find_gps_files, read_gps, read_gps_file
from read_instruments.hobo import find_hobo_files, read_hobo, read_hobo_file
from read_instruments.lgr import find_lgr_files, read_lgr, read_lgr_file
from read_instruments.meteoswiss import find_meteoswiss_files, read_meteoswiss, read_meteoswiss_file
from read_instruments.minidot import find_minidot_files, read_minidot, read_minidot_file
from read_instruments.rbr import find_rbr_files, read_rbr, read_rbr_file
from read_instruments.roma import find_roma_files, read_roma, read_roma_file
from read_instruments.seabird import find_seabird_files, read_seabird, read_seabird_file
from read_instruments.solinst import find_solinst_files, read_solinst, read_solinst_file
from read_instruments.vemco import find_vemco_files, read_vemco, read_vemco_file
from read_instruments.utils import combine, detect_encoding, merge_nearest

__all__ = [
    "read_campbell",
    "read_campbell_file",
    "find_campbell_files",
    "read_exo2",
    "read_exo2_file",
    "find_exo2_files",
    "read_gps",
    "read_gps_file",
    "find_gps_files",
    "read_lgr",
    "read_lgr_file",
    "find_lgr_files",
    "read_hobo",
    "read_hobo_file",
    "find_hobo_files",
    "read_meteoswiss",
    "read_meteoswiss_file",
    "find_meteoswiss_files",
    "read_minidot",
    "read_minidot_file",
    "find_minidot_files",
    "read_rbr",
    "read_rbr_file",
    "find_rbr_files",
    "read_roma",
    "read_roma_file",
    "find_roma_files",
    "read_seabird",
    "read_seabird_file",
    "find_seabird_files",
    "read_solinst",
    "read_solinst_file",
    "find_solinst_files",
    "read_vemco",
    "read_vemco_file",
    "find_vemco_files",
    "combine",
    "detect_encoding",
    "merge_nearest",
]
