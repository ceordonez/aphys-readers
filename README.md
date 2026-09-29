# Read AP instruments

Small, reusable routines to read raw data from the instruments of the Aquatic Physics group at the University of Geneva.

| Instrument | Status | Formats |
| --- | --- | --- |
| LGR greenhouse gas analyser | Available (`read_lgr`) | Zipped or plain-text daily files |
| YSI EXO2 sonde | Available (`read_exo2`) | KOR exports, CSV or Excel |
| Seabird | Planned | |
| Picarro | Planned | |

## Install

From another project managed with [uv](https://docs.astral.sh/uv/):

```
uv add --editable /path/to/read_instruments
```

Requires Python 3.12 or newer.

## Usage

```python
from read_instruments import read_exo2, read_lgr

# A directory, a single file, or a list of files
lgr = read_lgr("/path/to/unzipped/campaign")
exo = read_exo2("/path/to/exo2/exports")
one_day = read_lgr("/path/to/2020-07-16/fgga_2020-07-16_f0000.txt.zip")
some_files = read_exo2(["a.csv", "b.xlsx"])

# Data are averaged to 1-minute means by default
exo_raw = read_exo2("/path/to/exo2/exports", resample=None)  # native resolution
lgr_10min = read_lgr("/path/to/unzipped/campaign", resample="10min")
```

### Output

Every reader returns a pandas DataFrame with:

- a `Datetime` index in **UTC** (all instruments log in UTC);
- numeric columns named `Quantity_unit`, e.g. `CH4d_ppm`, `CO2d_ppm`, `Temp_C`, `ODO_mgL`.

Data from different instruments can therefore be joined directly, e.g. `lgr.join(exo)`.

Rows that appear identically in several files (overlapping exports) are kept once. When nothing is found, an empty DataFrame is returned and a warning is logged.

Each instrument also has:

- `read_<instrument>_file(path)`: read one file at native resolution;
- `find_<instrument>_files(directory)`: list the files a directory would be read from.

### Expected data layout

**LGR**: folders whose name contains `AtmGHG`, `atmGHG` or `YB`, at any depth below the directory given, each holding one folder per date:

```
campaign/
└── AC_AtmGHG_20200716_20200722/
    ├── 2020-07-16/fgga_2020-07-16_f0000.txt.zip
    └── 2020-07-17/fgga_2020-07-17_f0000.txt.zip
```

Columns read: `H2O_ppm`, `CH4d_ppm`, `CO2d_ppm` (dry mole fractions), `GasP_torr`, `GasT_C`, `RD0_us`, `RD1_us`.

**EXO2**: KOR exports (`.csv`, `.xls`, `.xlsx`) directly in the directory given. Dates may be MM/DD/YYYY or DD/MM/YYYY. Metadata and position columns (site name, depth, pressure, vertical position, cable power) are dropped.

Keep files from different sondes in separate directories, or pass them as separate lists: reading them together averages them into a single series.

## Development

```
uv sync                                           # set up the environment
uv run pytest                                     # run the tests
uv run --with mypy --with pandas-stubs mypy src   # type-check
```

The tests run on trimmed real instrument files in `tests/data`.
