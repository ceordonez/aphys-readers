"""Reader for GPS tracks: GPX files (e.g. Garmin eTrex) and NMEA logs written
by WinRiver II alongside ADCP transects (``*_GPS.TXT``)."""

import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from read_instruments.utils import Paths, StrPath, combine, resolve_files, walk_files

COLUMNS = ["Lat_deg", "Lon_deg", "Alt_m"]
# OpenCPN records tracks of other ships from AIS, named e.g. "AIS  (331394000) ..."
AIS_TRACK = re.compile(r"\s*AIS\b")
# Lenient GPX scanning, for files an XML parser rejects
TRK = re.compile(r"<(?:\w+:)?trk>(.*?)</(?:\w+:)?trk>", re.S)
TRK_NAME = re.compile(r"<(?:\w+:)?name>([^<]*)</")
TRKPT = re.compile(r"<(?:\w+:)?trkpt\b([^>]*)>(.*?)</(?:\w+:)?trkpt>", re.S)
COORD = re.compile(r"\b(lat|lon)\s*=\s*[\"']([^\"']*)")
CHILD = re.compile(r"<(?:\w+:)?(time|ele)>([^<]*)</")


def read_gps(paths: Paths, resample: str | None = "1min") -> pd.DataFrame:
    """Read GPS tracks.

    Parameters
    ----------
    paths : str, os.PathLike or iterable of those
        A directory searched recursively (see `find_gps_files`), a single
        file, or a list of files.
    resample : str or None
        Frequency to average to; None keeps the native resolution.

    Returns
    -------
    pandas.DataFrame
        Indexed by UTC ``Datetime``; empty if no files were found.
    """
    logging.info("Reading GPS data")
    files = resolve_files(paths, find_gps_files)
    if not files:
        logging.warning("No GPS files found in: %s", paths)
    frames = [read_gps_file(f) for f in files]
    return combine([f for f in frames if not f.empty], resample)


def find_gps_files(directory: StrPath) -> list[Path]:
    """List GPS files anywhere below a directory.

    Picks up non-empty ``.gpx`` files and WinRiver II NMEA logs
    (``*_GPS.TXT``). Folders whose name starts with ``_`` are skipped.
    """
    return [
        f
        for f in walk_files(directory)
        if f.suffix.lower() == ".gpx" or f.name.upper().endswith("_GPS.TXT")
    ]


def read_gps_file(path: StrPath) -> pd.DataFrame:
    """Read one GPS file (GPX or NMEA text) at native resolution."""
    path = Path(path)
    logging.info("Reading file: %s", path)
    if path.suffix.lower() == ".gpx":
        return read_gpx(path)
    return read_nmea(path)


def read_gpx(path: StrPath) -> pd.DataFrame:
    """Read the track points of a GPX file; waypoints and routes are ignored.

    Tracks of other ships recorded from AIS (see `AIS_TRACK`) are skipped.
    Files that are not valid XML (some OpenCPN exports have corrupted bytes in
    a few ``<time>`` elements) are scanned leniently: points whose time cannot
    be read are dropped.
    """
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        logging.warning("Invalid XML in %s (%s); reading track points leniently", path, error)
        text = Path(path).read_bytes().decode("utf-8", errors="replace")
        return to_frame(scan_track_points(text))
    records = []
    for track in root.iter():
        if local_name(track.tag) != "trk":
            continue
        name = next((c.text for c in track if local_name(c.tag) == "name"), None)
        if is_ais(name):
            continue
        for point in track.iter():
            if local_name(point.tag) != "trkpt":
                continue
            children = {local_name(c.tag): c.text for c in point}
            records.append(
                gpx_record(point.attrib.get("lat"), point.attrib.get("lon"), children)
            )
    return to_frame(records)


def scan_track_points(text: str) -> list[tuple[str | None, float, float, float]]:
    """Track points of GPX text found with regular expressions, not an XML parser."""
    records = []
    for track in TRK.findall(text):
        # The track name comes before its first segment
        name = TRK_NAME.search(track.split("trkseg", 1)[0])
        if is_ais(name.group(1) if name else None):
            continue
        for attributes, content in TRKPT.findall(track):
            coords = dict(COORD.findall(attributes))
            children = dict(CHILD.findall(content))
            records.append(gpx_record(coords.get("lat"), coords.get("lon"), children))
    return records


def is_ais(track_name: str | None) -> bool:
    """Whether a GPX track name marks another ship's track recorded from AIS."""
    return bool(track_name and AIS_TRACK.match(track_name))


def gpx_record(
    lat: str | None, lon: str | None, children: dict[str, str | None]
) -> tuple[str | None, float, float, float]:
    """(time, lat, lon, alt) of one track point; missing values become NaN/None."""
    ele = children.get("ele")
    return (
        children.get("time"),
        float(lat) if lat else float("nan"),
        float(lon) if lon else float("nan"),
        float(ele) if ele else float("nan"),
    )


def read_nmea(path: StrPath) -> pd.DataFrame:
    """Read an NMEA log, e.g. a WinRiver II ``*_GPS.TXT`` file.

    The date comes from the latest ``RMC`` sentence; time, position and
    altitude from ``GGA`` sentences with a valid fix (quality >= 1).
    """
    records = []
    date = None
    with open(path, errors="replace") as fh:
        for line in fh:
            # Drop the checksum (*XX); talker may be GP, GN, GL, ...
            parts = line.strip().split("*")[0].split(",")
            kind = parts[0][3:] if parts[0].startswith("$") else ""
            if kind == "RMC" and len(parts) > 9 and len(parts[9]) == 6:
                ddmmyy = parts[9]
                date = f"20{ddmmyy[4:]}-{ddmmyy[2:4]}-{ddmmyy[:2]}"
            elif kind == "GGA" and len(parts) > 9 and date:
                hhmmss = parts[1]
                if not parts[6].isdigit() or int(parts[6]) < 1 or len(hhmmss) < 6:
                    continue
                time = f"{date}T{hhmmss[:2]}:{hhmmss[2:4]}:{hhmmss[4:]}"
                records.append(
                    (
                        time,
                        nmea_degrees(parts[2], parts[3]),
                        nmea_degrees(parts[4], parts[5]),
                        float(parts[9]) if parts[9] else float("nan"),
                    )
                )
    data = to_frame(records)
    # A GGA repeated before the next RMC would duplicate a timestamp
    return data[~data.index.duplicated()]


def nmea_degrees(value: str, hemisphere: str) -> float:
    """Convert NMEA ``(d)ddmm.mmmm`` plus hemisphere to signed decimal degrees."""
    if not value:
        return float("nan")
    dot = value.index(".")
    degrees = float(value[: dot - 2]) + float(value[dot - 2 :]) / 60
    return -degrees if hemisphere in ("S", "W") else degrees


def to_frame(records: Sequence[tuple[str | None, float, float, float]]) -> pd.DataFrame:
    """Build the output DataFrame from (ISO time, lat, lon, alt) records.

    Records without a readable time are dropped.
    """
    data = pd.DataFrame(records, columns=["Datetime", *COLUMNS])
    data["Datetime"] = pd.to_datetime(
        data["Datetime"], utc=True, format="ISO8601", errors="coerce"
    )
    if bad := data["Datetime"].isna().sum():
        logging.info("Dropped %d points without a valid time", bad)
    return data.dropna(subset=["Datetime"]).set_index("Datetime").sort_index()


def local_name(tag: str) -> str:
    """XML tag without its namespace (GPX 1.0 and 1.1 use different ones)."""
    return tag.rsplit("}", 1)[-1]
