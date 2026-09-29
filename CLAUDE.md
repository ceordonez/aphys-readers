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
uv sync                       # create/update .venv from uv.lock
uv run python -c "from read_instruments import read_lgr; print(read_lgr('/path/to/unzipped'))"
uv build                      # build sdist + wheel into dist/
uv add <package>              # add a dependency (updates pyproject.toml and uv.lock)
```

There is no test suite or linter config yet.

## Reader conventions (from `lgr.py`)

New instrument readers should follow the pattern set by `read_lgr`:

- One module per instrument in `src/read_instruments/`, exposing `read_<instrument>(path)` (add it to `__init__.py` and `__all__`), returning a `pandas.DataFrame` indexed by a `Datetime` column, with columns renamed to `<Quantity>_<unit>` (e.g. `CH4d_ppm`, `GasT_C`).
- Return an empty `pd.DataFrame([])` when nothing is found rather than raising.
- Report progress and missing data through `logging` (`info` for files read, `warning` for skipped folders), not `print`.
- Shared helpers go in `utils.py`; `detect_encoding()` (chardet) is available for instruments whose files have an unknown text encoding.

### LGR specifics

`read_lgr(unzip_path)` expects a field-campaign directory tree: `unzip_path/<station>/<folder containing "YB", "AtmGHG" or "atmGHG">/<date>/<files>`. Each file is either a zip archive (a trailing footer starting with `-----B` is detected by `footer_pos()` and skipped) or a plain `fgg_<date>_f0000.txt`. Only selected CSV columns are read (time, H2O, dry CH4, dry CO2, gas P/T, ringdown times), then all files are concatenated, sorted, and resampled to 1‑minute means.
