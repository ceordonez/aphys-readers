"""Readers for Aquatic Physics group instruments."""

from read_instruments.exo2 import read_exo
from read_instruments.lgr import read_lgr
from read_instruments.utils import detect_encoding

__all__ = ["read_exo", "read_lgr", "detect_encoding"]
