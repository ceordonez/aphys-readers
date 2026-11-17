# Kestrel

[← aphys-readers](../README.md)

Reads Kestrel LiNK exports (`WEATHER - <serial>_<date>.csv`), recognised by their `Device Information:` first line.

```python
from aphys_readers import read_kestrel

wind = read_kestrel("data/raw/kestrel", utc_offset="UTC", resample="30s")
```

- **Time zone:** the meter clock is set by hand and the export does not state its zone; pass `utc_offset`.
- **One meter per call:** pass `serial=` when a folder holds exports from several meters.
- **Overlapping downloads:** each export holds the whole meter memory; identical rows are kept once. Old points from an earlier deployment can remain at the start of an export (e.g. a 2024 point in a 2025 file): slice by time.
- **Columns** are named from the units row, since units follow the meter settings and LiNK versions spell them differently (`Celsius` / `Deg. C`): `Tair_C`, `Twet_C`, `RH_pct`, `Baro_hPa` (reduced to sea level), `Press_hPa` (station pressure), `Alt_m`, `WS_ms`, `HeatIndex_C`, `Tdew_C`, `DensAlt_m`, `Crosswind_ms`, `Headwind_ms`, `WDmag_deg`, `WD_deg`, `WindChill_C`. `***` (not computed, e.g. no wind vane) becomes NaN.
