"""Readers for Aquatic Physics group instruments."""

from read_instruments.lgr import detect_encoding, read_lgr

__all__ = ["read_lgr", "detect_encoding"]
