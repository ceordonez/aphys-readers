# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Small, reusable Python routines for reading raw data files from instruments used by the Aquatic Physics (AP) group at the University of Geneva. Target instruments: Seabird, EXO2, LGR, Picarro, and the mooring loggers. Code lives in the `src/read_instruments/` package (built with `uv_build`), one module per instrument. Readers exist for LGR (`lgr.py`), EXO2 (`exo2.py`), Sea-Bird CTDs (`seabird.py`), GPS (`gps.py`), and the mooring loggers: Vemco (`vemco.py`), HOBO (`hobo.py`), miniDOT (`minidot.py`), RBR (`rbr.py`), Solinst (`solinst.py`) and the CH4/CO2 "Roma" probes (`roma.py`). Picarro is still to be written. Public readers are re-exported from `__init__.py`, so consumers write `from read_instruments import read_lgr`.

The library is meant to be consumed from other projects via an editable install:

```
uv add --editable /path/to/read_instruments
```

## Commands

Environment is managed with `uv` (Python 3.12, see `.python-version`):

```
uv sync                                   # create/update .venv from uv.lock
uv run pytest                             # run all tests
uv run pytest tests/test_readers.py::test_read_lgr_file_zip   # one test
uv run --with mypy --with pandas-stubs mypy src   # type-check
uv build                                  # build sdist + wheel into dist/
uv add <package>                          # add a dependency (updates pyproject.toml and uv.lock)
```

No linter is configured.

## Reader architecture

Every instrument module in `src/read_instruments/` exposes the same three functions, all re-exported from `__init__.py` (add new ones to `__all__`):

- `find_<instrument>_files(directory)` — knows the folder layout and returns the data files.
- `read_<instrument>_file(path)` — parses one raw file at native resolution.
- `read_<instrument>(paths, resample="1min")` — accepts a directory, a file, or a list of files; uses `utils.resolve_files()` to turn that into files, then `utils.combine()` to concatenate, sort, drop exactly duplicated rows (overlapping exports), and resample (`resample=None` keeps native resolution). Returns an empty `pd.DataFrame([])` when nothing is found.

Output contract, which lets data from different instruments be merged directly:

- Index is a tz-aware UTC `DatetimeIndex` named `Datetime`. LGR, EXO2, GPS and miniDOT log in UTC, so their file readers `tz_localize("UTC")`. The mooring loggers keep local clocks: their file readers take `utc_offset` and convert with `utils.to_utc`, using the offset in the file header when there is one (Vemco, HOBO, RBR plain export) and raising when neither the file nor the caller gives one (RBR ODV export, Solinst, Roma).
- Columns are renamed to `<Quantity>_<unit>` (e.g. `CH4d_ppm`, `Temp_C`) via a per-module mapping (`COLUMNS` in `lgr.py` and `gps.py`, `COLUMN_NAMES` in `exo2.py`) and are numeric.
- Progress and skipped folders go through `logging`, not `print`.

Instruments at different resolutions are merged with `utils.merge_nearest(left, right, tolerance="1min")`, a `merge_asof` on the index (direction nearest) that accepts a string tolerance, aligns the right index's time unit (`us`/`ns`) to the left's, and ignores all-NaN rows of `right` (empty resample bins) so they never shadow real data.

Mooring folders hold many loggers of one type, so the mooring readers take `serial=` and pass their files through `utils.check_one_logger`, which raises when files from several loggers would be averaged together. Each of those modules has a `<instrument>_serial(path)` helper.

Shared helpers (`walk_files`, `resolve_files`, `combine`, `merge_nearest`, `detect_encoding`, `offset_hours`, `to_utc`, `check_one_logger`) and the path type aliases used in annotations (`StrPath` for one path, `Paths` for one or many) live in `utils.py`. All functions are annotated and the package ships `py.typed`.

## Tests

`tests/data` holds real, trimmed instrument output. The mooring loggers' files (`vemco/`, `hobo/`, `minidot/`, `rbr/`, `solinst/`, `roma/`, `exo2_mooring/`) come from the Lake Soppen mooring and are tested in `tests/test_loggers.py`; the rest is in `tests/test_readers.py`: two weeks of zipped LGR files (`lgr/<week>/<date>/`), seven UTF-16 KOR CSV exports from two EXO2 sondes, a Sea-Bird `.cnv` (`seabird/`: full header, first 40 scans of a Lake Soppen SBE 19plus cast), and GPS files (`gps/`: a trimmed eTrex 10 GPX track, a waypoints-only GPX, and 100 s of a WinRiver II `_GPS.TXT`). Tests assert exact row counts and values from these files. Formats not represented there (plain-text LGR; Excel, newer-KOR, multi-section and dot-separated EXO2 exports) are built from the real files inside `tmp_path`, so keep that approach rather than adding synthetic fixtures.

## Instrument specifics

**LGR** (`lgr.py`): `find_lgr_files` searches recursively for non-empty files matching `FILE_NAME` (`*_fNNNN.txt` or `*_fNNNN.txt.zip`); no folder naming is assumed. Folders starting with `_` are skipped: real archives (e.g. `2020_ArcticChange/data/raw/atm_ghg/<year>/<date>/`) keep earlier partial copies of a day in `_superseded/`. A plain file is skipped if its `.zip` twin exists. Closed daily files end with a PGP signature block (first line starts with `-----B`) that `footer_pos()` counts so `read_csv` can skip it, for both zipped and plain files. Columns are selected by position (`COLUMNS`).

**EXO2** (`exo2.py`): KOR exports, CSV or Excel, from two KOR generations. Older ones have mixed-case headers with the date first; newer ones upper-case headers with time first, extra metadata columns, `;` separators with decimal commas, and newest rows first. All header handling is therefore case-insensitive: columns are upper-cased right after reading, and `DROP_COLUMNS` / `COLUMN_NAMES` are matched through their upper-cased forms (`_DROP`, `_RENAME`). Unknown headers pass through upper-cased.

- `find_exo2_files` walks recursively (`utils.walk_files`, which skips `_*` folders such as `_superseded`) and picks one format per recording (folder + name without `_N` part suffix): the CSVs if any, else the Excel file. `.xls` and `.csv` copies of a recording differ in rounding and extra columns, so reading both would double-count.
- `read_kor_csv` reads the text itself (encoding via chardet; real files are UTF-16 or UTF-8), takes the separator from the `sep=` first line, and parses each section separately: backup files concatenate several exports, each with summary lines and its own header/columns; a section runs from a header row to the next blank line. Values are read as text and `to_number` treats any comma as a decimal comma (KOR writes no thousands separators).
- Dates: the header always says MM/DD/YYYY, but dates follow the exporting locale. `date_formats` orders the formats from the `FILE CREATED` stamp (a field >12 decides; otherwise AM/PM means month-first, 24-hour clock day-first). This matters for short files where every day is <= 12.
- One real export used `sep=.`, which splits the `Time (Fract. Sec)` header and its `0.0` values into two aligned columns; both halves are in `DROP_COLUMNS`.

**Sea-Bird** (`seabird.py`): reads DatCnv `.cnv` text files, or an `.asc` (column-title line + data) with the `.hdr` of the same name when there is no `.cnv` (`split_file`; `find_seabird_files` lists such `.asc` files). Columns come from the `# name i = <short>: <description>` lines and are renamed via `COLUMN_NAMES`; `# bad_flag` values become NaN. Time = `# start_time` + `timeS`, else `scan` × `# interval`, else row number × `# interval`; files with `# binavg_` history are refused because their rows are not consecutive scans. The clock time zone is never stated (the instrument is set from the setup computer), so `utc_offset` goes through `to_utc`, which raises when it is missing. `read_seabird` defaults to `resample=None`. Pressure is sea pressure (standard atmosphere subtracted), so lake casts read below zero at the surface; the reader leaves it as recorded.

**Mooring loggers.**

- Vemco: rows are `date,time,T` or `date time,T`, CRLF and Latin-1; offset in `Minilog Initialized ... (UTC+2)`.
- HOBO: columns found by header text (`Temp`, `Intens...`), so English and Spanish exports both work; event-only rows are dropped; dates are always `%m/%d/%y %I:%M:%S %p`.
- miniDOT: columns mapped by header name (`COLUMNS`), as newer firmware adds `Battery`; daily files have a two-space-separated header.
- RBR: ODV data rows omit one depth field that the header names, so channels are matched from the end of each row. Plain exports with values in 0–1 are uncalibrated ratios and become `Temp_raw`.
- Solinst: a compensated `.xle` embeds the Barologger's header (second serial, kPa unit), so Barologger detection uses the *first* unit (`is_barologger`). Dates come in several orders (`DATE_FORMATS`); the first format that parses every row wins.
- Roma: `row_time` handles `ExcelTime`, Excel-mangled `20yy-mm-dd` dates (day and year swapped) and `dd/mm/yy`; dates outside 2010..now are clock resets.

**EXO2 extras from the mooring:** CSVs without `sep=` (separator taken from the header row), Latin-1 copies (`decode` avoids chardet's Big5 guess), `dd.mm.yyyy` dates (tried last), `File Created:` stamps in one cell, and Excel files whose first sheet is an edited copy (`kor_sheet`).

**GPS** (`gps.py`): `find_gps_files` walks recursively for `.gpx` files and WinRiver II NMEA logs (`*_GPS.TXT`, written next to ADCP `.PD0` files). Output columns are `Lat_deg`, `Lon_deg`, `Alt_m`, matching the EXO2 GPS columns.

- GPX is parsed with the stdlib `ElementTree`, matching tags without their namespace (GPX 1.0 and 1.1 differ). Only track points are read; waypoint-only files give an empty frame, which `read_gps` drops before `combine`. Tracks named `AIS ...` are skipped (`is_ais`): OpenCPN records other ships' AIS tracks alongside the own track (e.g. `2021/20210905_20210911_userobjects.gpx`), and merging them would put the ship tens of km off. The lenient scanner skips them too, splitting the text on `<trk>` (`TRK`, `TRK_NAME`).
- Some OpenCPN exports (`AC_GPS_20200813_20200827.gpx` and `AC_GPS_20200828_20200902.gpx` in `2020_ArcticChange/data/raw/gps/2020/`) have binary garbage in a few `<time>` elements, which is invalid XML. On `ParseError`, `read_gpx` falls back to regex scanning (`TRKPT`, `COORD`, `CHILD`), and `to_frame` drops points whose time does not parse.
- NMEA: the date comes from the latest `RMC` sentence; time, position and altitude from `GGA` with fix quality >= 1. Any talker (`GP`, `GN`, ...) is accepted, and timestamps repeated within a file keep the first fix.
