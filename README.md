# Read AP instruments

A small, reusable routines to read several instruments on the Aquatic Physics group at the University of Geneva. The routines read the following instruments:

- Seabird 
- EXO2
- LGR
- Picarro

## Install (from another project)

```
uv add --editable /path/to/read_instruments
```

## Usage

```python
from read_instruments import read_lgr

df = read_lgr("/path/to/unzipped/campaign")  # 1-minute averaged DataFrame
```
