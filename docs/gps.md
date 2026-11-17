# GPS

[← aphys-readers](../README.md)

Reads GPX files (GPX 1.0 or 1.1, e.g. Garmin eTrex or OpenCPN exports) and the NMEA logs WinRiver II writes next to ADCP files (`*_GPS.TXT`). Columns: `Lat_deg`, `Lon_deg`, `Alt_m`, as in the EXO2 GPS columns.

```python
from aphys_readers import read_gps

gps = read_gps("data/raw/gps/2020", resample=None)
```

- **Track points only.** Waypoints and routes are ignored; a GPX file with only waypoints gives no rows.
- **AIS tracks are skipped.** OpenCPN saves the tracks of other ships it received by AIS (named `AIS ...`) next to the own track; reading them would put the ship far from where it was.
- **Damaged files.** Some OpenCPN exports have garbage bytes inside a few `<time>` elements, which makes them invalid XML. They are still read, by scanning the text; points whose time does not parse are dropped.
- **NMEA:** time, position and altitude come from `GGA` sentences with a fix, the date from the latest `RMC`. Any talker is accepted (`GP`, `GN`, ...). When a timestamp repeats within a file, the first fix is kept.
