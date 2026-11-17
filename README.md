# aphys-readers

Small, reusable routines to read raw data from the instruments of the Aquatic Physics group at the University of Geneva.

| Instrument | Reader | Files read |
| --- | --- | --- |
| LGR greenhouse gas analyser | `read_lgr` | Daily `*_f0000.txt` files, plain or zipped |
| YSI EXO2 sonde | `read_exo2` | KOR exports, CSV or Excel |
| GPS | `read_gps` | GPX tracks, WinRiver II NMEA logs |
| Teledyne RDI ADCP (Workhorse / WinRiver II) | `read_adcp`, `read_pd0` | Binary `.PD0` files |
| Kestrel weather meter (5500, 5500L) | `read_kestrel` | Kestrel LiNK `.csv` exports |
| Vemco Minilog-II-T | `read_vemco` | LoggerVUE `.csv` exports |
| HOBO Pendant, HOBO U20 water level | `read_hobo` | HOBOware `.csv` exports (English or Spanish) |
| PME miniDOT | `read_minidot` | Concatenated `Cat.TXT` files, or the daily files |
| RBR (e.g. TR-1060) | `read_rbr` | Ruskin text exports (ODV spreadsheet or plain) |
| Solinst Levelogger / Barologger | `read_solinst` | `.xle` files and their `.csv` exports |
| CH4/CO2 probe ("Roma") | `read_roma` | Probe text files, raw or processed |
| Sea-Bird CTD (SBE 19plus) | `read_seabird` | `.cnv` files from SBE Data Processing; `Sal_psu` computed (PSS-78) when the file has none |
| Idronaut CTD (Ocean Seven 316Plus) | `read_idronaut` | REDAS text exports (`Col n :` header, start time, CSV data); a `Cast` column per file |
| Campbell Scientific loggers (e.g. METER ATMOS 41 weather station on a CR200) | `read_campbell` | `TOA5` table files (`.dat`) |
| MeteoSwiss weather stations | `read_meteoswiss` | Open-data station files (`ogd-smn_<station>_<t/h/d/m/y>_*.csv`) |
| Picarro | planned | |

Practical salinity from conductivity, temperature and pressure (PSS-78, UNESCO 1983) is available as `salinity_pss78`.

## Install

From another project managed with [uv](https://docs.astral.sh/uv/):

```
uv add --editable /path/to/aphys_readers
```

Requires Python 3.12 or newer.

## Usage

```python
from aphys_readers import read_exo2, read_lgr

# A directory (searched recursively), a single file, or a list of files
lgr = read_lgr("/path/to/atm_ghg")
exo = read_exo2("/path/to/exo2/15L103185")
one_day = read_lgr("/path/to/2020-07-16/fgga_2020-07-16_f0000.txt.zip")
some_files = read_exo2(["a.csv", "b.xlsx"])

# 1-minute means by default; any pandas frequency, or None for native resolution
lgr_10min = read_lgr("/path/to/atm_ghg", resample="10min")
exo_raw = read_exo2("/path/to/exo2/15L103185", resample=None)

# All readers share the same output format, so they can be joined directly
both = lgr.join(exo)
```

Every reader returns a pandas DataFrame with:

- a `Datetime` index in **UTC** (see "Time zones" below);
- numeric columns named `Quantity_unit`, e.g. `CH4d_ppm`, `CO2d_ppm`, `Temp_C`, `ODO_mgL`.

Each instrument also has `read_<instrument>_file(path)`, which reads one file at native resolution, and `find_<instrument>_files(directory)`, which lists the files a directory would be read from.

When reading a directory:

- folders whose name starts with `_` (such as `_superseded`, holding earlier copies of a file) are skipped, as are empty files;
- rows that appear identically in several files (overlapping exports) are kept once;
- if nothing is found, an empty DataFrame is returned and a warning is logged.

## Time zones

The output is always UTC. LGR, EXO2, GPS, miniDOT and MeteoSwiss data are in UTC. The mooring loggers often keep local time:

| Logger | Clock offset taken from |
| --- | --- |
| Vemco | the header (`Minilog Initialized: ... (UTC+2)`) |
| HOBO | the date column header (`Date Time, GMT+02:00`) |
| miniDOT | Unix timestamps (UTC) |
| RBR plain export | the `Z` on each timestamp (UTC) |
| RBR ODV export, Solinst, CH4/CO2 probe, Sea-Bird, Idronaut, Campbell, Kestrel, ADCP | nothing: pass `utc_offset` |

`utc_offset` accepts `"UTC+02:00"`, `"GMT+1"`, `"+02:00"`, `"UTC"` or a number of hours. When given, it overrides the offset in the file. A reader raises an error rather than guess when a file states no offset and none is given.

## Mooring loggers

A mooring folder holds many loggers of the same type at different depths. Their readers therefore read **one logger per call**: they raise an error if the files come from several loggers, unless you pass `serial=` (leading zeros are ignored).

```python
from aphys_readers import read_vemco, read_solinst, read_roma

t_5m = read_vemco("/path/to/mooring/20170828_20171012/Vemco", serial=357451)
level = read_solinst("/path/to/mooring", serial=2085605, utc_offset="UTC+02:00")
probe4 = read_roma("/path/to/mooring", serial=4, utc_offset="UTC+02:00")
```

Columns:

| Reader | Columns |
| --- | --- |
| `read_vemco` | `Temp_C` |
| `read_hobo` | `Temp_C`, `Light_lux` (Pendant) or `Pressure_kPa` (U20, absolute pressure) |
| `read_minidot` | `Temp_C`, `ODO_mgL`, `ODO_pctsat` (Cat files), `Q`, `Battery_V` (newer firmware) |
| `read_rbr` | one per channel, e.g. `Temp_C`; `Temp_raw` for uncalibrated thermistor ratios |
| `read_solinst` | `Level_m` (Levelogger) or `Pressure_kPa` (Barologger), `Temp_C` |
| `read_roma` | `CH4_pct`, `CO2_pct`, `AR_CH4`, `AR_CO2`, `Tsensor_C`, `Text_C`, `Battery_V`, `Press_bar` |

- **miniDOT:** a folder's `Cat*.TXT` is read when it has one, otherwise its daily files (`57A8BF40.txt`). Processed copies are ignored.
- **Solinst:** folders often hold the same recording raw and barometrically compensated, each as `.xle` and `.csv`. A directory read keeps the compensated Levelogger files (`compensated=False` for the raw ones), plus the Barologger, and skips an `.xle` when a `.csv` of the same kind is next to it. Compensated levels are metres of water above the sensor; raw levels include the atmosphere (about 9.5 m more).
- **CH4/CO2 probe:** the probes have no serial number; the probe number in the first column is used as the serial, since file names can be wrong. Rows written while the clock was reset (`00/00/00` and similar dates) are dropped. `T_ext` = 327.67 (error value) becomes NaN. A directory read uses the raw exports; `processed=True` uses the processed copies (with an `ExcelTime` column) where a folder has them. Hourly samples are kept by default (`resample=None`).

## Instruments

### LGR

Reads every file named like `fgga_2020-07-16_f0000.txt` or `fgga_2020-07-16_f0000.txt.zip` below the directory, whatever the folder names:

```
atm_ghg/
├── 2020/
│   ├── 2020-06-09/fgga_2020-06-09_f0000.txt
│   └── 2020-06-22/
│       ├── fgga_2020-06-22_f0000.txt
│       └── _superseded/fgga_2020-06-22_f0000__ad4dbeca.txt   skipped
└── 2021/...
```

- If a day has both a plain and a zipped copy, only the zipped one is read.
- The signature block at the end of closed daily files is ignored.
- Columns: `H2O_ppm`, `CH4d_ppm`, `CO2d_ppm` (dry mole fractions), `GasP_torr`, `GasT_C`, `RD0_us`, `RD1_us`.

### EXO2

Reads KOR exports (`.csv`, `.xls`, `.xlsx`) below the directory. Raw sonde files (`.bin`) need KOR and are ignored.

```
exo2/15L103185/
├── 2020/
│   ├── EXO_SD_15L103185_072320_072732.bin   ignored
│   ├── EXO_SD_15L103185_072320_072732.csv   read
│   ├── EXO_SD_15L103185_072320_072732.xls   skipped, same recording as the .csv
│   └── _superseded/...                      skipped
└── 2023/QS_15L103185_20230713_20230715.csv
```

- **One copy per recording.** KOR often exports a recording several times (`.xls`, `.csv`, or `_1.csv`, `_2.csv` parts) with slightly different rounding. Its CSV files are read when there are any, otherwise its Excel file.
- **Old and new KOR exports.** Both older exports (mixed-case headers, date first) and newer ones (upper-case headers, time first, `;` with decimal commas, newest row first) are read, as are backup files holding several exports one after another.
- **Date order.** KOR labels the date column MM/DD/YYYY but writes dates in the exporting computer's locale. The order is taken from the file's `FILE CREATED` stamp: a 12-hour clock (`7/29/2020 1:36:35 PM`) means month-first, a 24-hour clock (`06/08/2023 20:44:08`) day-first.
- **Dropped columns:** site name, file name, user, fault code and cable power. Depth, pressure and vertical position are kept (`Depth_m`, `Press_psia` or `Press_bara`, `VPos_m`). The pressure sensor is non-vented, so `Depth_m` moves with air pressure; KOR references it to the air pressure when the depth was last zeroed.
- **Other variants read:** older KOR CSVs without a `sep=` line, `Temp C` headers, Excel files with edited copies of the data as extra sheets (the `KOR Export File` sheet is used), and copies re-saved by Excel in Latin-1 with `;` and `dd.mm.yyyy` dates.

### Sea-Bird

Reads `.cnv` files (casts converted with SBE Data Processing / DatCnv) below the directory, and `.asc` + `.hdr` pairs (the same conversion saved by SeaTerm in two files) when there is no `.cnv` of the same name. The raw `.hex` uploads need SBE Data Processing first and are ignored.

```python
from aphys_readers import read_seabird

cast = read_seabird("ctd/sbe19plus/20180410", utc_offset="UTC")
```

- **Every scan is kept** (`resample=None` by default), as a profile needs.
- **Times** are `# start_time` plus the `timeS` or `scan` column when there is one, otherwise row number × `# interval`. Bin-averaged files are refused.
- **Time zone:** the instrument clock is set from the computer used to set it up; the file does not say which zone. Pass `utc_offset`.
- **Pressure is sea pressure.** The instrument subtracts a standard sea-level atmosphere (10.1325 dbar), so on a lake above sea level `Press_dbar` and `Depth_m` read below zero at the surface (about −0.7 dbar at 600 m a.s.l.), and the strain-gauge reading drifts for a minute or two after the instrument goes from air into water. Reference the depth to the surface yourself (e.g. from a surface soak before the cast).
- **Columns:** SBE short names are renamed (`prdM` → `Press_dbar`, `depFM` → `Depth_m`, `tv290C` → `Temp_C`, `c0uS/cm` → `Cond_uScm`, `specc` → `SpCond_uScm`, `sbeox0Mm/L` → `DO_umolL`, `sbeox0PS` → `DO_pctsat`, `flECO-AFL` → `Chl_mgm3`, `turbWETntu0` → `Turb_NTU`, ...; see `COLUMN_NAMES`); others keep their SBE name. Values equal to `# bad_flag` become NaN.
- **Copies:** identical copies of a cast under different names are kept once when a directory is read.

### Campbell (ATMOS 41)

Reads Campbell Scientific `TOA5` tables, the text files a CR200/CR1000/CR6 logger writes per table (here `CR200-Soppen_Atmos41_10min.dat`, a METER ATMOS 41 all-in-one weather station). Files are recognised by their first field (`"TOA5"`), whatever their extension.

```python
from aphys_readers import read_campbell

atmos = read_campbell("data/raw/weather/atmos41", utc_offset="UTC+01:00")
```

- **Time zone:** the files do not state the logger clock's time zone; pass `utc_offset`. Timestamps are kept as recorded: for averages and totals Campbell marks the **end** of the interval.
- **One table per call:** a logger writes one file per table (10-min, daily...). Pass `table=` (the last field of the first header line, e.g. `"Atmos41_10min"`) when a folder holds several.
- **Overlapping downloads:** each download repeats what is still in the logger memory; identical rows are kept once.
- **Columns:** the ATMOS 41 fields are renamed (`Rad_Avg` → `SWin_Wm2`, `AirTemp_Avg` → `Tair_C`, `AirPress_Avg` → `Press_kPa`, `VaporPress_Avg` → `VapPress_kPa`, `WSpeed_Avg` → `WS_ms`, `WDirection_Avg` → `WD_deg`, `WSpeed`/`WDirection` (samples) → `WSsmp_ms`/`WDsmp_deg`, `gWSpeed_Tot` → `Gust_ms`, `Pp_Tot` → `Precip_mm`, `batt_volt_Min` → `Battery_V`; see `COLUMN_NAMES`); the CR300 ATMOS 41 program of the Gambia station (1-min samples) is renamed too (`Solar` → `SWin_Wm2`, `AirTemp` → `Tair_C`, `AtmPressure` → `Press_kPa`, `WindSpeed` → `WS_ms`, `GustWindSpeed` → `Gust_ms`, `Strikes` → `Strikes_count`, ...); other fields keep their name, units as in the file. `RECORD` is dropped, `NAN` becomes NaN. Values are not checked: the Lake Soppen files have impossible pressures and negative wind averages that need cleaning.

### Kestrel

Reads Kestrel LiNK exports (`WEATHER - <serial>_<date>.csv`), recognised by their `Device Information:` first line.

```python
from aphys_readers import read_kestrel

wind = read_kestrel("data/raw/kestrel", utc_offset="UTC", resample="30s")
```

- **Time zone:** the meter clock is set by hand and the export does not state its zone; pass `utc_offset`.
- **One meter per call:** pass `serial=` when a folder holds exports from several meters.
- **Overlapping downloads:** each export holds the whole meter memory; identical rows are kept once. Old points from an earlier deployment can remain at the start of an export (e.g. a 2024 point in a 2025 file): slice by time.
- **Columns** are named from the units row, since units follow the meter settings and LiNK versions spell them differently (`Celsius` / `Deg. C`): `Tair_C`, `Twet_C`, `RH_pct`, `Baro_hPa` (reduced to sea level), `Press_hPa` (station pressure), `Alt_m`, `WS_ms`, `HeatIndex_C`, `Tdew_C`, `DensAlt_m`, `Crosswind_ms`, `Headwind_ms`, `WDmag_deg`, `WD_deg`, `WindChill_C`. `***` (not computed, e.g. no wind vane) becomes NaN.

### RDI ADCP

Reads Teledyne RDI binary files (`.PD0`, as written by WinRiver II). Ensembles that fail their checksum are skipped, and blocks other than the standard ones (such as the NMEA blocks WinRiver II embeds) are ignored.

```python
from aphys_readers import read_adcp, read_pd0

bt = read_adcp("data/raw/adcp/Station_6_0", utc_offset="UTC")   # one row per ensemble
pd0 = read_pd0("data/raw/adcp/Station_6_0/Station_6_0_004_25-01-13.PD0", utc_offset="UTC")
pd0.vel          # (beam, cell, ensemble), m/s; also pd0.corr, pd0.echo, pd0.pgood
pd0.bin_distance # m from the transducer to each cell centre
pd0.coordinates  # "beam", "instrument", "ship" or "earth"
```

- **`read_adcp`** gives the per-ensemble values like any other reader: `Ens`, `Heading_deg`, `Pitch_deg`, `Roll_deg`, `Temp_C`, `SoundSpeed_ms`, `Sal_psu` and `XdcrDepth_m` (as set in the instrument), bottom track per beam `BTRange1_m`..`BTRange4_m` and their mean `BTRange_m`, `BTVel1_ms`..`BTVel4_ms`. Every ensemble is kept (`resample=None`).
- **`read_pd0`** also gives the profiles, the bottom track as arrays, and the settings (`cell_size`, `blank`, `beam_angle`, `upward`).
- **Velocities are not transformed.** They are in the coordinate system set in the instrument (`coordinates`): beams 1-4, or x/y/z/error (instrument, ship), or east/north/up/error (earth). The same holds for the bottom-track velocities.
- **Bottom-track range** is, as RDI documents it, the *vertical* range from the transducer to the bottom per beam, not corrected for pitch and roll. Add the transducer depth to get water depth.
- **Time zone:** the ADCP clock is set from the acquisition computer; pass `utc_offset`. Check it: the clock may be off by days.

### MeteoSwiss

Reads the station files of the MeteoSwiss open data (OGD; data © MeteoSwiss, see [opendatadocs.meteoswiss.ch](https://opendatadocs.meteoswiss.ch) for the terms of use and parameter descriptions). One file per station, granularity and period: `ogd-smn_ego_t_historical_2010-2019.csv` is SwissMetNet station EGO (Egolzwil), 10-min values (`t`; also `h`, `d`, `m`, `y`), checked data up to the end of last year (`historical`; also `recent` and `now`).

```python
from aphys_readers import read_meteoswiss

ego = read_meteoswiss("data/raw/ego")                     # 10-min files by default
ego_hourly = read_meteoswiss("data/raw/ego", granularity="h")
```

- **Timestamps are UTC and kept as published:** for 10-min and hourly values they mark the *end* of the interval (`16:00` = 15:50:01–16:00:00 for means and totals; current values are taken at that time); for daily, monthly and yearly values they mark the start. `resample` therefore averages each value into the bin of its end time.
- **One station per call:** pass `station=` (e.g. `"EGO"`) when a folder holds several. Only files of one granularity are read from a directory; the metadata files (`ogd-smn_meta_parameters.csv`, ...) are ignored.
- **Columns:** the 10-min parameter short names are renamed (`tre200s0` → `Tair_C`, `ure200s0` → `RH_pct`, `pva200s0` → `VapPress_hPa`, `prestas0` → `Press_hPa` (station level, QFE), `fkl010z0` → `WS_ms`, `dkl010z0` → `WD_deg`, `rre150z0` → `Precip_mm`, `gre000z0` → `SWin_Wm2`, `oli000z0` → `LWin_Wm2`, ...; see `COLUMN_NAMES`); others keep their short name. Parameters not measured at the station (empty columns) are dropped. Empty fields are missing values.

## Things to watch

- **One sonde per call.** Reading files from different sondes together averages them into a single series. Keep them in separate directories, or pass separate lists of files.
- **Backup copies.** Don't read a folder that also holds backups of the same data (e.g. a `kor_exports` folder next to the sonde folders): backups often have a different set of columns, so their rows are not recognised as duplicates and appear twice.
- **Several readings in one timestamp.** Some newer KOR backups log different sensors in separate sections, occasionally at the same second. The 1-minute mean combines them; with `resample=None` they stay as separate rows.

## Development

```
uv sync                                           # set up the environment
uv run pytest                                     # run the tests
uv run --with mypy --with pandas-stubs mypy src   # type-check
```

The tests run on trimmed real instrument files in `tests/data`.
