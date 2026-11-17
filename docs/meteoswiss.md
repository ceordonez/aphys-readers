# MeteoSwiss

[← aphys-readers](../README.md)

Reads the station files of the MeteoSwiss open data (OGD; data © MeteoSwiss, see [opendatadocs.meteoswiss.ch](https://opendatadocs.meteoswiss.ch) for the terms of use and parameter descriptions). One file per station, granularity and period: `ogd-smn_ego_t_historical_2010-2019.csv` is SwissMetNet station EGO (Egolzwil), 10-min values (`t`; also `h`, `d`, `m`, `y`), checked data up to the end of last year (`historical`; also `recent` and `now`).

```python
from aphys_readers import read_meteoswiss

ego = read_meteoswiss("data/raw/ego")                     # 10-min files by default
ego_hourly = read_meteoswiss("data/raw/ego", granularity="h")
```

- **Timestamps are UTC and kept as published:** for 10-min and hourly values they mark the *end* of the interval (`16:00` = 15:50:01–16:00:00 for means and totals; current values are taken at that time); for daily, monthly and yearly values they mark the start. `resample` therefore averages each value into the bin of its end time.
- **One station per call:** pass `station=` (e.g. `"EGO"`) when a folder holds several. Only files of one granularity are read from a directory; the metadata files (`ogd-smn_meta_parameters.csv`, ...) are ignored.
- **Columns:** the 10-min parameter short names are renamed (`tre200s0` → `Tair_C`, `ure200s0` → `RH_pct`, `pva200s0` → `VapPress_hPa`, `prestas0` → `Press_hPa` (station level, QFE), `fkl010z0` → `WS_ms`, `dkl010z0` → `WD_deg`, `rre150z0` → `Precip_mm`, `gre000z0` → `SWin_Wm2`, `oli000z0` → `LWin_Wm2`, ...; see `COLUMN_NAMES`); others keep their short name. Parameters not measured at the station (empty columns) are dropped. Empty fields are missing values.
