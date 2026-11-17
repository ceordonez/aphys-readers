# Idronaut

[← aphys-readers](../README.md)

Reads Ocean Seven 316Plus casts exported to text by REDAS (`.txt` files with `Col 1 : ...` header lines).

```python
from aphys_readers import read_idronaut

casts = read_idronaut("data/raw/ctd/idronaut", utc_offset="UTC+01:00")
```

- **Times** are the start time in the header (day first, `29/01/2026 10:20:52`) plus the `Time(s)` column. Every sample is kept (`resample=None` by default).
- **Time zone:** the file does not state the clock's zone; pass `utc_offset`.
- **`Cast` column:** the file name (without extension) of each row, so several casts read together can be split with `groupby("Cast")`.
- **Columns:** `Depth_m`, `Press_dbar`, `Temp_C`, `Cond_mScm`, `SpCond_mScm` (at 25 °C), `Sal_psu`, `DO_pctsat`, `DO_mgL`, `PAR`, `TDS_gL`, `pH`, `Turb_NTU`, `Chl_ugL`; other columns keep their title.
