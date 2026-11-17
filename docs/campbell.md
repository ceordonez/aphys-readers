# Campbell (ATMOS 41)

[← aphys-readers](../README.md)

Reads Campbell Scientific `TOA5` tables, the text files a CR200/CR1000/CR6 logger writes per table (here `CR200-Soppen_Atmos41_10min.dat`, a METER ATMOS 41 all-in-one weather station). Files are recognised by their first field (`"TOA5"`), whatever their extension.

```python
from aphys_readers import read_campbell

atmos = read_campbell("data/raw/weather/atmos41", utc_offset="UTC+01:00")
```

- **Time zone:** the files do not state the logger clock's time zone; pass `utc_offset`. Timestamps are kept as recorded: for averages and totals Campbell marks the **end** of the interval.
- **One table per call:** a logger writes one file per table (10-min, daily...). Pass `table=` (the last field of the first header line, e.g. `"Atmos41_10min"`) when a folder holds several.
- **Overlapping downloads:** each download repeats what is still in the logger memory; identical rows are kept once.
- **Columns:** the ATMOS 41 fields are renamed (`Rad_Avg` → `SWin_Wm2`, `AirTemp_Avg` → `Tair_C`, `AirPress_Avg` → `Press_kPa`, `VaporPress_Avg` → `VapPress_kPa`, `WSpeed_Avg` → `WS_ms`, `WDirection_Avg` → `WD_deg`, `WSpeed`/`WDirection` (samples) → `WSsmp_ms`/`WDsmp_deg`, `gWSpeed_Tot` → `Gust_ms`, `Pp_Tot` → `Precip_mm`, `batt_volt_Min` → `Battery_V`; see `COLUMN_NAMES`); the CR300 ATMOS 41 program of the Gambia station (1-min samples) is renamed too (`Solar` → `SWin_Wm2`, `AirTemp` → `Tair_C`, `AtmPressure` → `Press_kPa`, `WindSpeed` → `WS_ms`, `GustWindSpeed` → `Gust_ms`, `Strikes` → `Strikes_count`, ...); other fields keep their name, units as in the file. `RECORD` is dropped, `NAN` becomes NaN. Values are not checked: the Lake Soppen files have impossible pressures and negative wind averages that need cleaning.
