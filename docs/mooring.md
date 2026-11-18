# Mooring loggers

[← aphys-readers](../README.md)

Vemco, HOBO, miniDOT, RBR, Solinst and the CH4/CO2 probes. These readers read one logger per call (`serial=`); see the README for the time zone each one takes its clock offset from.

## Columns

| Reader | Columns |
| --- | --- |
| `read_vemco` | `Temp_C` |
| `read_hobo` | `Temp_C`, `Light_lux` (Pendant) or `Pressure_kPa` (U20, absolute pressure) |
| `read_minidot` | `Temp_C`, `ODO_mgL`, `ODO_pctsat` (Cat files), `Q`, `Battery_V` (newer firmware) |
| `read_rbr` | one per channel, e.g. `Temp_C`, `Pres_dbar`; `Temp_raw` for uncalibrated thermistor ratios |
| `read_solinst` | `Level_m` (Levelogger) or `Pressure_kPa` (Barologger), `Temp_C` |
| `read_roma` | `CH4_pct`, `CO2_pct`, `AR_CH4`, `AR_CO2`, `Tsensor_C`, `Text_C`, `Battery_V`, `Press_bar` |

## Notes per logger

- **miniDOT:** a folder's `Cat*.TXT` is read when it has one, otherwise its daily files (`57A8BF40.txt`). Processed copies are ignored.
- **RBR:** native `.rsk` files are SQLite databases and are read directly (no Ruskin export needed), opened read-only. Only the channels Ruskin shows are kept: hidden/derived channels such as the RBRduet³'s pressure-sensor thermistor (`temp05`) are left out. Pressure is absolute (`Pres_dbar`, atmosphere included). A text export is skipped when its `.rsk` is in the same folder. The clock drift Ruskin measured at download (`deployments.loggerTimeDrift`, ms) is not applied.
- **Solinst:** folders often hold the same recording raw and barometrically compensated, each as `.xle` and `.csv`. A directory read keeps the compensated Levelogger files (`compensated=False` for the raw ones), plus the Barologger, and skips an `.xle` when a `.csv` of the same kind is next to it. Compensated levels are metres of water above the sensor; raw levels include the atmosphere (about 9.5 m more).
- **CH4/CO2 probe:** the probes have no serial number; the probe number in the first column is used as the serial, since file names can be wrong. Rows written while the clock was reset (`00/00/00` and similar dates) are dropped. `T_ext` = 327.67 (error value) becomes NaN. A directory read uses the raw exports; `processed=True` uses the processed copies (with an `ExcelTime` column) where a folder has them. Hourly samples are kept by default (`resample=None`).
