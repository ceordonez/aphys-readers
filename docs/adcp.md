# RDI ADCP

[← aphys-readers](../README.md)

Reads Teledyne RDI binary files (`.PD0`, as written by WinRiver II). Ensembles that fail their checksum are skipped, and blocks other than the standard ones (such as the NMEA blocks WinRiver II embeds) are ignored.

```python
from aphys_readers import read_adcp, read_pd0

bt = read_adcp("data/raw/adcp/Station_6_0", utc_offset="UTC")   # one row per ensemble
pd0 = read_pd0("data/raw/adcp/Station_6_0/Station_6_0_004_25-01-13.PD0", utc_offset="UTC")
pd0.vel          # (beam, cell, ensemble), m/s; also pd0.corr, pd0.echo, pd0.pgood
pd0.bin_distance # m from the transducer to each cell centre
pd0.coordinates  # "beam", "instrument", "ship" or "earth"
```

- **`read_adcp`** gives the per-ensemble values like any other reader: `Ens`, `Heading_deg`, `Pitch_deg`, `Roll_deg`, `Temp_C`, `SoundSpeed_ms`, `Sal_psu` and `XdcrDepth_m` (as set in the instrument), bottom track per beam `BTRange1_m`..`BTRange4_m` and their mean `BTRange_m`, `BTVel1_ms`..`BTVel4_ms`. Every ensemble is kept (`resample=None`).
- **`read_pd0`** also gives the profiles, the bottom track as arrays, and the settings (`cell_size`, `blank`, `beam_angle`, `upward`).
- **Velocities are not transformed.** They are in the coordinate system set in the instrument (`coordinates`): beams 1-4, or x/y/z/error (instrument, ship), or east/north/up/error (earth). The same holds for the bottom-track velocities.
- **Bottom-track range** is, as RDI documents it, the *vertical* range from the transducer to the bottom per beam, not corrected for pitch and roll. Add the transducer depth to get water depth.
- **Time zone:** the ADCP clock is set from the acquisition computer; pass `utc_offset`. Check it: the clock may be off by days.
