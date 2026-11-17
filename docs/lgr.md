# LGR

[← aphys-readers](../README.md)

Reads every file named like `fgga_2020-07-16_f0000.txt` or `fgga_2020-07-16_f0000.txt.zip` below the directory, whatever the folder names:

```
atm_ghg/
├── 2020/
│   ├── 2020-06-09/fgga_2020-06-09_f0000.txt
│   └── 2020-06-22/
│       ├── fgga_2020-06-22_f0000.txt
│       └── _superseded/fgga_2020-06-22_f0000__ad4dbeca.txt   skipped
└── 2021/...
```

- If a day has both a plain and a zipped copy, only the zipped one is read.
- The signature block at the end of closed daily files is ignored.
- Columns: `H2O_ppm`, `CH4d_ppm`, `CO2d_ppm` (dry mole fractions), `GasP_torr`, `GasT_C`, `RD0_us`, `RD1_us`.
