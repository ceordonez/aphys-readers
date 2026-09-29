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

Shared helpers (`resolve_files`, `combine`, `detect_encoding`) and the path type aliases used in annotations (`StrPath` for one path, `Paths` for one or many) live in `utils.py`. All functions are annotated and the package ships `py.typed`.

## Tests

`tests/data` holds real, trimmed instrument output: two weeks of zipped LGR files (`lgr/AC_AtmGHG_*/<date>/`) and seven UTF-16 KOR CSV exports from two EXO2 sondes. Tests assert exact row counts and values from these files. Formats not represented there (plain-text LGR, Excel and day-first EXO2 exports) are built from the real files inside `tmp_path`, so keep that approach rather than adding synthetic fixtures.

## Instrument specifics

**LGR** (`lgr.py`): `find_lgr_files` searches at any depth for folders whose name contains "YB", "AtmGHG" or "atmGHG" and reads every one of them; each holds one subfolder per date containing zip archives and/or plain `*_fNNNN.txt` files (a plain file is skipped if its `.zip` twin exists). Closed daily files end with a PGP signature block (first line starts with `-----B`) that `footer_pos()` counts so `read_csv` can skip it, for both zipped and plain files. Columns are selected by position (`COLUMNS`).

**EXO2** (`exo2.py`): KOR exports, CSV or Excel. CSVs start with a `sep=<char>` line and have metadata before the header row; `find_header()` locates the row containing `Date (MM/DD/YYYY)` and detects encoding with chardet. Despite the header, dates may be DD/MM/YYYY, so `DATE_FORMATS` are tried in order. KOR files are typically UTF-16. Repeated header rows (concatenated exports) are dropped, as are metadata/position columns in `DROP_COLUMNS`. KOR headers missing from `COLUMN_NAMES` pass through unrenamed.
