"""Reader for Teledyne RDI ADCP binary files (PD0), e.g. WinRiver II ``.PD0``.

Tested on a 4-beam Workhorse-family ADCP recorded with WinRiver II. A PD0
file is a sequence of ensembles. Each starts with ``0x7F 0x7F``, the number of
bytes, and the offsets of its data types, and ends with a checksum; ensembles
whose checksum fails are skipped. Data types read (RDI "Workhorse Commands and
Output Data Format"):

- ``0x0000`` fixed leader: number of beams and cells, cell size, bin 1
  distance, beam angle, coordinate system;
- ``0x0080`` variable leader: time, heading, pitch, roll, temperature...;
- ``0x0100`` velocity, ``0x0200`` correlation, ``0x0300`` echo intensity,
  ``0x0400`` percent good (per beam and cell);
- ``0x0600`` bottom track: range and velocity per beam.

Other data types (e.g. the NMEA blocks WinRiver II embeds) are ignored, so
ensembles may hold a varying number of data types.

Velocities are in the coordinate system the instrument was set to (the EX
command, `PD0.coordinates`): beam 1-4 for ``"beam"``, otherwise
x/y/z/error (``"instrument"``, ``"ship"``) or east/north/up/error (``"earth"``).
Nothing is transformed.

The ADCP clock is set from the acquisition computer and the file does not
state its time zone, so `utc_offset` must be given.
"""

import logging
import struct
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from read_instruments.utils import Paths, StrPath, UtcOffset, combine, resolve_files, to_utc, walk_files

HEADER_ID = b"\x7f\x7f"
FIXED_LEADER, VARIABLE_LEADER = 0x0000, 0x0080
VELOCITY, CORRELATION, ECHO, PERCENT_GOOD, BOTTOM_TRACK = 0x0100, 0x0200, 0x0300, 0x0400, 0x0600
BAD_VELOCITY = -32768
# Fixed leader coordinate transform bits 3-4 (EX command)
COORDINATES = ("beam", "instrument", "ship", "earth")
# Fixed leader system configuration bits 8-9; "other" angles are not stated
BEAM_ANGLES = (15.0, 20.0, 30.0, None)


@dataclass
class PD0:
    """Contents of one PD0 file.

    Arrays are indexed (beam, cell, ensemble) or (beam, ensemble); bad values
    are NaN.
    """

    ensembles: pd.DataFrame
    """Per-ensemble values, indexed by UTC ``Datetime`` (see `read_adcp_file`)."""
    vel: np.ndarray
    """Velocity (m/s), in `coordinates`."""
    corr: np.ndarray
    """Correlation magnitude (counts, 0-255)."""
    echo: np.ndarray
    """Echo intensity (counts)."""
    pgood: np.ndarray
    """Percent good (%)."""
    bt_range: np.ndarray
    """Bottom track range per beam (m). RDI documents it as the vertical range
    to the bottom, not corrected for pitch and roll."""
    bt_vel: np.ndarray
    """Bottom track velocity (m/s), in `coordinates`."""
    bin_distance: np.ndarray
    """Distance from the transducer to the centre of each cell (m)."""
    cell_size: float
    """Cell size (m)."""
    blank: float
    """Blank after transmit (m)."""
    beam_angle: float | None
    """Beam angle from the vertical (degrees); None when not stated."""
    coordinates: str
    """Coordinate system of the velocities: beam, instrument, ship or earth."""
    upward: bool
    """Whether the transducer faces up."""

    @property
    def time(self) -> pd.DatetimeIndex:
        """Ensemble times (UTC)."""
        return pd.DatetimeIndex(self.ensembles.index)


def read_adcp(paths: Paths, utc_offset: UtcOffset = None, resample: str | None = None) -> pd.DataFrame:
    """Read the per-ensemble values (attitude, bottom track...) of PD0 files.

    For velocity profiles use `read_pd0`.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_adcp_files`), a single
        file, or a list of files.
    utc_offset : str, float or None
        ADCP clock offset (e.g. ``"UTC+02:00"``); required, as the files
        state no time zone.
    resample : str or None
        Frequency to average to; None (default) keeps every ensemble.

    Returns
    -------
    pandas.DataFrame
        See `read_adcp_file`; empty if no files were found.
    """
    logging.info("Reading ADCP data")
    files = resolve_files(paths, find_adcp_files)
    if not files:
        logging.warning("No ADCP files found in: %s", paths)
    return combine([read_adcp_file(f, utc_offset) for f in files], resample)


def find_adcp_files(directory: StrPath) -> list[Path]:
    """List ``.PD0`` files below a directory (any case).

    Folders whose name starts with ``_`` are skipped.
    """
    return [f for f in walk_files(directory) if f.suffix.lower() == ".pd0"]


def read_adcp_file(path: StrPath, utc_offset: UtcOffset = None) -> pd.DataFrame:
    """Per-ensemble values of one PD0 file.

    Columns: ``Ens`` (ensemble number), ``Heading_deg``, ``Pitch_deg``,
    ``Roll_deg``, ``Temp_C``, ``SoundSpeed_ms``, ``Sal_psu`` (as set),
    ``XdcrDepth_m`` (as set), ``BTRange1_m`` .. ``BTRange<n>_m``,
    ``BTRange_m`` (mean of the valid beams), ``BTVel1_ms`` ..
    ``BTVel<n>_ms``; indexed by UTC ``Datetime``.
    """
    return read_pd0(path, utc_offset).ensembles


def ensemble_offsets(raw: bytes) -> list[dict[int, int]]:
    """For each valid ensemble, the file offset of each of its data types."""
    ensembles = []
    n = len(raw)
    pos = raw.find(HEADER_ID)
    while 0 <= pos < n - 6:
        size = struct.unpack_from("<H", raw, pos + 2)[0]
        n_types = raw[pos + 5]
        end = pos + size + 2
        valid = (
            size >= 6 + 2 * n_types
            and 2 <= n_types <= 64
            and end <= n
            and sum(raw[pos : end - 2]) & 0xFFFF == struct.unpack_from("<H", raw, end - 2)[0]
        )
        if not valid:
            pos = raw.find(HEADER_ID, pos + 1)
            continue
        offsets: dict[int, int] = {}
        for i in range(n_types):
            start = pos + struct.unpack_from("<H", raw, pos + 6 + 2 * i)[0]
            if start + 2 <= end:
                # Keep the first block of each type (WinRiver II repeats its NMEA blocks)
                offsets.setdefault(struct.unpack_from("<H", raw, start)[0], start)
        ensembles.append(offsets)
        pos = raw.find(HEADER_ID, end)
    return ensembles


def read_pd0(path: StrPath, utc_offset: UtcOffset = None) -> PD0:
    """Read everything in one PD0 file: profiles, bottom track, attitude.

    Raises ValueError without `utc_offset`, since the files state no time
    zone, and when the file holds no valid ensemble.
    """
    path = Path(path)
    logging.info("Reading file: %s", path)
    raw = path.read_bytes()
    ensembles = [e for e in ensemble_offsets(raw) if FIXED_LEADER in e and VARIABLE_LEADER in e]
    if not ensembles:
        raise ValueError(f"{path}: no valid PD0 ensemble")

    fixed = ensembles[0][FIXED_LEADER]
    n_beams, n_cells = raw[fixed + 8], raw[fixed + 9]
    # Settings must not change within a file; drop ensembles where they do
    kept = [e for e in ensembles if raw[e[FIXED_LEADER] + 8 : e[FIXED_LEADER] + 10] == bytes([n_beams, n_cells])]
    if len(kept) < len(ensembles):
        logging.warning("%s: %d ensembles with other settings skipped", path, len(ensembles) - len(kept))
    ensembles = kept
    n_ens = len(ensembles)
    system = struct.unpack_from("<H", raw, fixed + 4)[0]
    cell_size = struct.unpack_from("<H", raw, fixed + 12)[0] / 100
    blank = struct.unpack_from("<H", raw, fixed + 14)[0] / 100
    bin1 = struct.unpack_from("<H", raw, fixed + 32)[0] / 100

    profiles = {k: np.full((n_beams, n_cells, n_ens), np.nan, dtype=np.float32) for k in ("vel", "corr", "echo", "pgood")}
    bt_range = np.full((n_beams, n_ens), np.nan)
    bt_vel = np.full((n_beams, n_ens), np.nan)
    leader = np.zeros((n_ens, 7), dtype=np.int64)  # year, month, day, hour, minute, second, hundredths
    values = np.full((n_ens, 8), np.nan)  # Ens, heading, pitch, roll, temperature, sound speed, salinity, depth

    for i, offsets in enumerate(ensembles):
        var = offsets[VARIABLE_LEADER]
        leader[i] = list(raw[var + 4 : var + 11])
        number = struct.unpack_from("<H", raw, var + 2)[0] + raw[var + 11] * 65536
        # Heading is unsigned (0-359.99 degrees); pitch, roll and temperature are signed
        sound, depth, heading, pitch, roll, sal, temp = struct.unpack_from("<HHHhhHh", raw, var + 14)
        values[i] = [number, heading / 100, pitch / 100, roll / 100, temp / 100, sound, sal, depth / 10]
        for key, block, dtype in (("vel", VELOCITY, "<i2"), ("corr", CORRELATION, "u1"), ("echo", ECHO, "u1"), ("pgood", PERCENT_GOOD, "u1")):
            if block in offsets:
                count = n_cells * n_beams
                start = offsets[block] + 2
                if start + count * np.dtype(dtype).itemsize <= len(raw):
                    block_values = np.frombuffer(raw, dtype=dtype, count=count, offset=start).reshape(n_cells, n_beams).T
                    profiles[key][:, :, i] = block_values
        if BOTTOM_TRACK in offsets and offsets[BOTTOM_TRACK] + 81 <= len(raw):
            bt = offsets[BOTTOM_TRACK]
            lsb = np.array(struct.unpack_from(f"<{n_beams}H", raw, bt + 16), dtype=float)
            msb = np.array(struct.unpack_from(f"<{n_beams}B", raw, bt + 77), dtype=float)
            bt_range[:, i] = np.where(lsb + msb == 0, np.nan, (lsb + msb * 65536) / 100)
            vel = np.array(struct.unpack_from(f"<{n_beams}h", raw, bt + 24), dtype=float)
            bt_vel[:, i] = np.where(vel == BAD_VELOCITY, np.nan, vel / 1000)

    vel = profiles["vel"]
    vel[vel == BAD_VELOCITY] = np.nan
    vel /= 1000

    stamps = pd.DataFrame(leader[:, :6], columns=["year", "month", "day", "hour", "minute", "second"])
    stamps["year"] += 2000
    times = pd.to_datetime(stamps, errors="coerce") + pd.to_timedelta(leader[:, 6] * 10, unit="ms")
    names = ["Ens", "Heading_deg", "Pitch_deg", "Roll_deg", "Temp_C", "SoundSpeed_ms", "Sal_psu", "XdcrDepth_m"]
    table = pd.DataFrame(values, columns=names)
    for b in range(n_beams):
        table[f"BTRange{b + 1}_m"] = bt_range[b]
    with warnings.catch_warnings():
        # Ensembles without any bottom detection give NaN
        warnings.simplefilter("ignore", RuntimeWarning)
        table["BTRange_m"] = np.nanmean(bt_range, axis=0)
    for b in range(n_beams):
        table[f"BTVel{b + 1}_ms"] = bt_vel[b]
    table.index = to_utc(times, utc_offset, path)

    return PD0(
        ensembles=table,
        vel=vel,
        corr=profiles["corr"],
        echo=profiles["echo"],
        pgood=profiles["pgood"],
        bt_range=bt_range,
        bt_vel=bt_vel,
        bin_distance=bin1 + cell_size * np.arange(n_cells),
        cell_size=cell_size,
        blank=blank,
        beam_angle=BEAM_ANGLES[(system >> 8) & 3],
        coordinates=COORDINATES[(raw[fixed + 25] >> 3) & 3],
        upward=bool(system & 0x80),
    )
