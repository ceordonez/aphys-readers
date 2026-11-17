# EXO2

[← aphys-readers](../README.md)

Reads KOR exports (`.csv`, `.xls`, `.xlsx`) below the directory. Raw sonde files (`.bin`) need KOR and are ignored.

```
exo2/15L103185/
├── 2020/
│   ├── EXO_SD_15L103185_072320_072732.bin   ignored
│   ├── EXO_SD_15L103185_072320_072732.csv   read
│   ├── EXO_SD_15L103185_072320_072732.xls   skipped, same recording as the .csv
│   └── _superseded/...                      skipped
└── 2023/QS_15L103185_20230713_20230715.csv
```

- **One copy per recording.** KOR often exports a recording several times (`.xls`, `.csv`, or `_1.csv`, `_2.csv` parts) with slightly different rounding. Its CSV files are read when there are any, otherwise its Excel file.
- **Old and new KOR exports.** Both older exports (mixed-case headers, date first) and newer ones (upper-case headers, time first, `;` with decimal commas, newest row first) are read, as are backup files holding several exports one after another.
- **Date order.** KOR labels the date column MM/DD/YYYY but writes dates in the exporting computer's locale. The order is taken from the file's `FILE CREATED` stamp: a 12-hour clock (`7/29/2020 1:36:35 PM`) means month-first, a 24-hour clock (`06/08/2023 20:44:08`) day-first.
- **Dropped columns:** site name, file name, user, fault code and cable power. Depth, pressure and vertical position are kept (`Depth_m`, `Press_psia` or `Press_bara`, `VPos_m`). The pressure sensor is non-vented, so `Depth_m` moves with air pressure; KOR references it to the air pressure when the depth was last zeroed.
- **Other variants read:** older KOR CSVs without a `sep=` line, `Temp C` headers, Excel files with edited copies of the data as extra sheets (the `KOR Export File` sheet is used), and copies re-saved by Excel in Latin-1 with `;` and `dd.mm.yyyy` dates.
- **One sonde per call.** Reading files from different sondes together averages them into a single series. Keep them in separate directories, or pass separate lists of files.
- **Backup copies.** Don't read a folder that also holds backups of the same data (e.g. a `kor_exports` folder next to the sonde folders): backups often have a different set of columns, so their rows are not recognised as duplicates and appear twice.
- **Several readings in one timestamp.** Some newer KOR backups log different sensors in separate sections, occasionally at the same second. The 1-minute mean combines them; with `resample=None` they stay as separate rows.
