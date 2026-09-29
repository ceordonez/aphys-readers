# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Small, reusable Python routines for reading raw data files from instruments used by the Aquatic Physics (AP) group at the University of Geneva. Target instruments: Seabird, EXO2, LGR, and Picarro. Code lives in the `src/read_instruments/` package (built with `uv_build`), one module per instrument. LGR (`lgr.py`) and EXO2 (`exo2.py`) readers exist; Seabird and Picarro are still to be written. Public readers are re-exported from `__init__.py`, so consumers write `from read_instruments import read_lgr`.

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

- Index is a tz-aware UTC `DatetimeIndex` named `Datetime`. All instruments log in UTC, so file readers `tz_localize("UTC")` rather than convert.
- Columns are renamed to `<Quantity>_<unit>` (e.g. `CH4d_ppm`, `Temp_C`) via a per-module mapping (`COLUMNS` in `lgr.py`, `COLUMN_NAMES` in `exo2.py`) and are numeric.
- Progress and skipped folders go through `logging`, not `print`.

Shared helpers (`walk_files`, `resolve_files`, `combine`, `detect_encoding`) and the path type aliases used in annotations (`StrPath` for one path, `Paths` for one or many) live in `utils.py`. All functions are annotated and the package ships `py.typed`.

## Tests

`tests/data` holds real, trimmed instrument output: two weeks of zipped LGR files (`lgr/<week>/<date>/`) and seven UTF-16 KOR CSV exports from two EXO2 sondes. Tests assert exact row counts and values from these files. Formats not represented there (plain-text LGR; Excel, newer-KOR, multi-section and dot-separated EXO2 exports) are built from the real files inside `tmp_path`, so keep that approach rather than adding synthetic fixtures.

## Instrument specifics

**LGR** (`lgr.py`): `find_lgr_files` searches recursively for non-empty files matching `FILE_NAME` (`*_fNNNN.txt` or `*_fNNNN.txt.zip`); no folder naming is assumed. Folders starting with `_` are skipped: real archives (e.g. `2020_ArcticChange/data/raw/atm_ghg/<year>/<date>/`) keep earlier partial copies of a day in `_superseded/`. A plain file is skipped if its `.zip` twin exists. Closed daily files end with a PGP signature block (first line starts with `-----B`) that `footer_pos()` counts so `read_csv` can skip it, for both zipped and plain files. Columns are selected by position (`COLUMNS`).

**EXO2** (`exo2.py`): KOR exports, CSV or Excel, from two KOR generations. Older ones have mixed-case headers with the date first; newer ones upper-case headers with time first, extra metadata columns, `;` separators with decimal commas, and newest rows first. All header handling is therefore case-insensitive: columns are upper-cased right after reading, and `DROP_COLUMNS` / `COLUMN_NAMES` are matched through their upper-cased forms (`_DROP`, `_RENAME`). Unknown headers pass through upper-cased.

- `find_exo2_files` walks recursively (`utils.walk_files`, which skips `_*` folders such as `_superseded`) and picks one format per recording (folder + name without `_N` part suffix): the CSVs if any, else the Excel file. `.xls` and `.csv` copies of a recording differ in rounding and extra columns, so reading both would double-count.
- `read_kor_csv` reads the text itself (encoding via chardet; real files are UTF-16 or UTF-8), takes the separator from the `sep=` first line, and parses each section separately: backup files concatenate several exports, each with summary lines and its own header/columns; a section runs from a header row to the next blank line. Values are read as text and `to_number` treats any comma as a decimal comma (KOR writes no thousands separators).
- Dates: the header always says MM/DD/YYYY, but dates follow the exporting locale. `date_formats` orders the formats from the `FILE CREATED` stamp (a field >12 decides; otherwise AM/PM means month-first, 24-hour clock day-first). This matters for short files where every day is <= 12.
- One real export used `sep=.`, which splits the `Time (Fract. Sec)` header and its `0.0` values into two aligned columns; both halves are in `DROP_COLUMNS`.
