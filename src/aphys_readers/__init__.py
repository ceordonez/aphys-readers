"""Readers for Aquatic Physics group instruments.

Every reader returns a DataFrame indexed by a UTC ``Datetime`` index with
``Quantity_unit`` column names. Loggers whose clocks are not on UTC are
converted using the offset in their files or the ``utc_offset`` argument.
MeteoSwiss station data (``read_meteoswiss``) are read the same way.

RDI ADCP files: ``read_adcp`` gives the per-ensemble values (attitude,
bottom track) like any other reader; ``read_pd0`` also gives the profiles.
"""

from aphys_readers.adcp import PD0, find_adcp_files, read_adcp, read_adcp_file, read_pd0
from aphys_readers.campbell import find_campbell_files, read_campbell, read_campbell_file
from aphys_readers.exo2 import find_exo2_files, read_exo2, read_exo2_file
from aphys_readers.gps import find_gps_files, read_gps, read_gps_file
from aphys_readers.idronaut import find_idronaut_files, read_idronaut, read_idronaut_file
from aphys_readers.hobo import find_hobo_files, read_hobo, read_hobo_file
from aphys_readers.kestrel import find_kestrel_files, read_kestrel, read_kestrel_file
from aphys_readers.lgr import find_lgr_files, read_lgr, read_lgr_file
from aphys_readers.meteoswiss import find_meteoswiss_files, read_meteoswiss, read_meteoswiss_file
from aphys_readers.minidot import find_minidot_files, read_minidot, read_minidot_file
from aphys_readers.rbr import find_rbr_files, read_rbr, read_rbr_file
from aphys_readers.roma import find_roma_files, read_roma, read_roma_file
from aphys_readers.seabird import find_seabird_files, read_seabird, read_seabird_file
from aphys_readers.solinst import find_solinst_files, read_solinst, read_solinst_file
from aphys_readers.vemco import find_vemco_files, read_vemco, read_vemco_file
from aphys_readers.seawater import salinity_pss78, sigma_t
from aphys_readers.utils import combine, detect_encoding, merge_nearest

__all__ = [
    "PD0",
    "read_adcp",
    "read_adcp_file",
    "read_pd0",
    "find_adcp_files",
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
    "read_idronaut",
    "read_idronaut_file",
    "find_idronaut_files",
    "salinity_pss78",
    "sigma_t",
    "read_hobo",
    "read_hobo_file",
    "find_hobo_files",
    "read_kestrel",
    "read_kestrel_file",
    "find_kestrel_files",
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
