# Read AP instruments

Small, reusable routines to read raw data from the instruments of the Aquatic Physics group at the University of Geneva.

| Instrument | Reader | Files read |
| --- | --- | --- |
| LGR greenhouse gas analyser | `read_lgr` | Daily `*_f0000.txt` files, plain or zipped |
| YSI EXO2 sonde | `read_exo2` | KOR exports, CSV or Excel |
| Seabird | planned | |
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

- a `Datetime` index in **UTC** (all instruments log in UTC);
- numeric columns named `Quantity_unit`, e.g. `CH4d_ppm`, `CO2d_ppm`, `Temp_C`, `ODO_mgL`.

Each instrument also has `read_<instrument>_file(path)`, which reads one file at native resolution, and `find_<instrument>_files(directory)`, which lists the files a directory would be read from.

When reading a directory:

- folders whose name starts with `_` (such as `_superseded`, holding earlier copies of a file) are skipped, as are empty files;
- rows that appear identically in several files (overlapping exports) are kept once;
- if nothing is found, an empty DataFrame is returned and a warning is logged.

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
- **Dropped columns:** site name, file name, user, fault code, depth, pressure, vertical position and cable power.

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
