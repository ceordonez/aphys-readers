# Read AP instruments

Small, reusable routines to read raw data from the instruments of the Aquatic Physics group at the University of Geneva.

| Instrument | Reader | Files read |
| --- | --- | --- |
| LGR greenhouse gas analyser | `read_lgr` | Daily `*_f0000.txt` files, plain or zipped |
| YSI EXO2 sonde | `read_exo2` | KOR exports, CSV or Excel |
| GPS | `read_gps` | GPX tracks, WinRiver II NMEA logs |
| Vemco Minilog-II-T | `read_vemco` | LoggerVUE `.csv` exports |
| HOBO Pendant | `read_hobo` | HOBOware `.csv` exports (English or Spanish) |
| PME miniDOT | `read_minidot` | Concatenated `Cat.TXT` files, or the daily files |
| RBR (e.g. TR-1060) | `read_rbr` | Ruskin text exports (ODV spreadsheet or plain) |
| Solinst Levelogger / Barologger | `read_solinst` | `.xle` files and their `.csv` exports |
| CH4/CO2 probe ("Roma") | `read_roma` | Probe text files, raw or processed |
| Sea-Bird CTD (SBE 19plus) | `read_seabird` | `.cnv` files from SBE Data Processing |
| Picarro | planned | |

## Install

From another project managed with [uv](https://docs.astral.sh/uv/):

```
uv add --editable /path/to/read_instruments
```

Requires Python 3.12 or newer.

## Usage

```python
from read_instruments import read_exo2, read_lgr

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

The output is always UTC. LGR, EXO2, GPS and miniDOT log in UTC. The mooring loggers often keep local time:

| Logger | Clock offset taken from |
| --- | --- |
| Vemco | the header (`Minilog Initialized: ... (UTC+2)`) |
| HOBO | the date column header (`Date Time, GMT+02:00`) |
| miniDOT | Unix timestamps (UTC) |
| RBR plain export | the `Z` on each timestamp (UTC) |
| RBR ODV export, Solinst, CH4/CO2 probe, Sea-Bird | nothing: pass `utc_offset` |

`utc_offset` accepts `"UTC+02:00"`, `"GMT+1"`, `"+02:00"`, `"UTC"` or a number of hours. When given, it overrides the offset in the file. A reader raises an error rather than guess when a file states no offset and none is given.

## Mooring loggers

A mooring folder holds many loggers of the same type at different depths. Their readers therefore read **one logger per call**: they raise an error if the files come from several loggers, unless you pass `serial=` (leading zeros are ignored).

```python
from read_instruments import read_vemco, read_solinst, read_roma

t_5m = read_vemco("/path/to/mooring/20170828_20171012/Vemco", serial=357451)
level = read_solinst("/path/to/mooring", serial=2085605, utc_offset="UTC+02:00")
probe4 = read_roma("/path/to/mooring", serial=4, utc_offset="UTC+02:00")
```

Columns:

| Reader | Columns |
| --- | --- |
| `read_vemco` | `Temp_C` |
| `read_hobo` | `Temp_C`, `Light_lux` |
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
from read_instruments import read_seabird

cast = read_seabird("ctd/sbe19plus/20180410", utc_offset="UTC")
```

- **Every scan is kept** (`resample=None` by default), as a profile needs.
- **Times** are `# start_time` plus the `timeS` or `scan` column when there is one, otherwise row number × `# interval`. Bin-averaged files are refused.
- **Time zone:** the instrument clock is set from the computer used to set it up; the file does not say which zone. Pass `utc_offset`.
- **Pressure is sea pressure.** The instrument subtracts a standard sea-level atmosphere (10.1325 dbar), so on a lake above sea level `Press_dbar` and `Depth_m` read below zero at the surface (about −0.7 dbar at 600 m a.s.l.), and the strain-gauge reading drifts for a minute or two after the instrument goes from air into water. Reference the depth to the surface yourself (e.g. from a surface soak before the cast).
- **Columns:** SBE short names are renamed (`prdM` → `Press_dbar`, `depFM` → `Depth_m`, `tv290C` → `Temp_C`, `c0uS/cm` → `Cond_uScm`, `specc` → `SpCond_uScm`, `sbeox0Mm/L` → `DO_umolL`, `sbeox0PS` → `DO_pctsat`, `flECO-AFL` → `Chl_mgm3`, `turbWETntu0` → `Turb_NTU`, ...; see `COLUMN_NAMES`); others keep their SBE name. Values equal to `# bad_flag` become NaN.
- **Copies:** identical copies of a cast under different names are kept once when a directory is read.

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
