# aphys-readers

Small, reusable routines to read raw data from the instruments of the Aquatic Physics group at the University of Geneva.

| Instrument | Reader | Files read |
| --- | --- | --- |
| LGR greenhouse gas analyser | [`read_lgr`](docs/lgr.md) | Daily `*_f0000.txt` files, plain or zipped |
| YSI EXO2 sonde | [`read_exo2`](docs/exo2.md) | KOR exports, CSV or Excel |
| GPS | [`read_gps`](docs/gps.md) | GPX tracks, WinRiver II NMEA logs |
| Teledyne RDI ADCP (Workhorse / WinRiver II) | [`read_adcp`](docs/adcp.md), `read_pd0` | Binary `.PD0` files |
| Kestrel weather meter (5500, 5500L) | [`read_kestrel`](docs/kestrel.md) | Kestrel LiNK `.csv` exports |
| Vemco Minilog-II-T | [`read_vemco`](docs/mooring.md) | LoggerVUE `.csv` exports |
| HOBO Pendant, HOBO U20 water level | [`read_hobo`](docs/mooring.md) | HOBOware `.csv` exports (English or Spanish) |
| PME miniDOT | [`read_minidot`](docs/mooring.md) | Concatenated `Cat.TXT` files, or the daily files |
| RBR (e.g. TR-1060, RBRsolo³, RBRduet³) | [`read_rbr`](docs/mooring.md) | Native Ruskin `.rsk` files; Ruskin text exports (ODV spreadsheet or plain) |
| Solinst Levelogger / Barologger | [`read_solinst`](docs/mooring.md) | `.xle` files and their `.csv` exports |
| CH4/CO2 probe ("Roma") | [`read_roma`](docs/mooring.md) | Probe text files, raw or processed |
| Sea-Bird CTD (SBE 19plus) | [`read_seabird`](docs/seabird.md) | `.cnv` files from SBE Data Processing; `Sal_psu` computed (PSS-78) when the file has none |
| Idronaut CTD (Ocean Seven 316Plus) | [`read_idronaut`](docs/idronaut.md) | REDAS text exports (`Col n :` header, start time, CSV data); a `Cast` column per file |
| Campbell Scientific loggers (e.g. METER ATMOS 41 weather station on a CR200) | [`read_campbell`](docs/campbell.md) | `TOA5` table files (`.dat`) |
| MeteoSwiss weather stations | [`read_meteoswiss`](docs/meteoswiss.md) | Open-data station files (`ogd-smn_<station>_<t/h/d/m/y>_*.csv`) |
| Picarro | planned | |

Each reader's page (linked above) describes the files and folder layouts it reads, its output columns, and the quirks of the instrument's exports.

Two seawater routines work on any of these outputs: `salinity_pss78(cond_mscm, temp_c, press_dbar)` gives practical salinity (PSS-78, UNESCO 1983), and `sigma_t(salinity, temp_c)` gives density minus 1000 kg/m³ at atmospheric pressure (EOS-80), enough for stratification over a few tens of metres.

## Install

From another project managed with [uv](https://docs.astral.sh/uv/), straight from GitHub:

```
uv add git+https://github.com/ceordonez/aphys-readers
```

This installs the current version on GitHub; `uv lock --upgrade-package aphys-readers` updates it later, and appending `@<tag or commit>` to the URL pins a version.

To work on the readers themselves, clone the repository and install it in editable mode, so changes take effect without reinstalling:

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

# Resampled to the same frequency, outputs line up and can be joined directly
both = lgr.join(exo)
```

Instruments at different resolutions (a 1 Hz LGR and sparse GPS fixes, a native-resolution cast and a 10-min weather station) are matched with `merge_nearest`, which adds to each row of the first frame the nearest-in-time row of the second:

```python
from aphys_readers import merge_nearest, read_gps, read_lgr

lgr = read_lgr("/path/to/atm_ghg", resample=None)
gps = read_gps("/path/to/gps", resample=None)
track = merge_nearest(lgr, gps, tolerance="30s")   # NaN where no fix within 30 s
```

Columns present in both get `_x` / `_y` suffixes. Empty resample bins in the second frame are ignored, so they never hide a real value next to them; `tolerance=None` matches any gap.

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
| RBR `.rsk` | stored in UTC |
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

Columns and notes for each logger: [docs/mooring.md](docs/mooring.md).

## Development

```
uv sync                                           # set up the environment
uv run pytest                                     # run the tests
uv run --with mypy --with pandas-stubs mypy src   # type-check
```

The tests run on trimmed real instrument files in `tests/data`.
