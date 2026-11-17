# Sea-Bird

[← aphys-readers](../README.md)

Reads `.cnv` files (casts converted with SBE Data Processing / DatCnv) below the directory, and `.asc` + `.hdr` pairs (the same conversion saved by SeaTerm in two files) when there is no `.cnv` of the same name. The raw `.hex` uploads need SBE Data Processing first and are ignored.

```python
from aphys_readers import read_seabird

cast = read_seabird("ctd/sbe19plus/20180410", utc_offset="UTC")
```

- **Every scan is kept** (`resample=None` by default), as a profile needs.
- **Times** are `# start_time` plus the `timeS` or `scan` column when there is one, otherwise row number × `# interval`. Bin-averaged files are refused.
- **Time zone:** the instrument clock is set from the computer used to set it up; the file does not say which zone. Pass `utc_offset`.
- **Pressure is sea pressure.** The instrument subtracts a standard sea-level atmosphere (10.1325 dbar), so on a lake above sea level `Press_dbar` and `Depth_m` read below zero at the surface (about −0.7 dbar at 600 m a.s.l.), and the strain-gauge reading drifts for a minute or two after the instrument goes from air into water. Reference the depth to the surface yourself (e.g. from a surface soak before the cast).
- **Columns:** SBE short names are renamed (`prdM` → `Press_dbar`, `depFM` → `Depth_m`, `tv290C` → `Temp_C`, `c0uS/cm` → `Cond_uScm`, `specc` → `SpCond_uScm`, `sbeox0Mm/L` → `DO_umolL`, `sbeox0PS` → `DO_pctsat`, `flECO-AFL` → `Chl_mgm3`, `turbWETntu0` → `Turb_NTU`, ...; see `COLUMN_NAMES`); others keep their SBE name. Values equal to `# bad_flag` become NaN.
- **Copies:** identical copies of a cast under different names are kept once when a directory is read.
