"""Tests on the real instrument files in tests/data.

Formats not present there (plain-text LGR, Excel and day-first EXO2 exports)
are derived from the real files in a temporary directory.
"""

import zipfile
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from read_instruments import (
    find_exo2_files,
    find_lgr_files,
    read_exo2,
    read_exo2_file,
    read_lgr,
    read_lgr_file,
)

DATA = Path(__file__).parent / "data"
LGR_WEEK1 = DATA / "lgr/AC_AtmGHG_20200716_20200722"
LGR_ZIP = LGR_WEEK1 / "2020-07-16/fgga_2020-07-16_f0000.txt.zip"
EXO2_DIR = DATA / "exo2"
EXO2_CSV = EXO2_DIR / "EXO_SD_15L103185_072320_072732.csv"
# Maur_..._143037.csv holds the rows of its _1 and _2 parts
MAUR_PARTS = [EXO2_DIR / f"Maur_12M101161_060420_143037{s}.csv" for s in ("", "_1", "_2")]

LGR_COLUMNS = ["H2O_ppm", "CH4d_ppm", "CO2d_ppm", "GasP_torr", "GasT_C", "RD0_us", "RD1_us"]
EXO2_COLUMNS = [
    "Cond_uScm",
    "nLFCond_uScm",
    "ODO_pctsat",
    "ODO_pctlocal",
    "ODO_mgL",
    "Sal_psu",
    "SpCond_uScm",
    "TDS_mgL",
    "Turb_FNU",
    "TSS_mgL",
    "Temp_C",
    "Battery_V",
]


def utc(timestamp):
    return pd.Timestamp(timestamp, tz="UTC")


def exo2_lines(path):
    return path.read_text(encoding="utf-16").splitlines()


# LGR


@pytest.mark.parametrize("directory", [DATA, DATA / "lgr", LGR_WEEK1])
def test_find_lgr_files_at_any_depth(directory):
    expected = 16 if directory != LGR_WEEK1 else 7
    files = find_lgr_files(directory)
    assert len(files) == expected
    assert files[0] == LGR_ZIP


def test_read_lgr_file_zip():
    data = read_lgr_file(LGR_ZIP)
    assert list(data.columns) == LGR_COLUMNS
    assert len(data) == 1769  # every data row, PGP footer skipped
    assert data.index[0] == utc("2020-07-16 06:56:34.139")
    assert data.index[-1] == utc("2020-07-17 06:55:53.523")
    assert data["CH4d_ppm"].iloc[0] == pytest.approx(1.093195)
    assert data["CO2d_ppm"].iloc[0] == pytest.approx(406.3437)
    assert data.notna().all().all()


def test_read_lgr_file_plain_text_with_footer(tmp_path):
    with zipfile.ZipFile(LGR_ZIP) as zf:
        txt = Path(zf.extract(zf.namelist()[0], tmp_path))
    pd.testing.assert_frame_equal(read_lgr_file(txt), read_lgr_file(LGR_ZIP))


def test_find_lgr_files_plain_text_skipped_when_zip_present(tmp_path):
    date_dir = tmp_path / "AtmGHG" / "2020-07-16"
    date_dir.mkdir(parents=True)
    (date_dir / LGR_ZIP.name).write_bytes(LGR_ZIP.read_bytes())
    with zipfile.ZipFile(LGR_ZIP) as zf:
        zf.extract(zf.namelist()[0], date_dir)
    assert find_lgr_files(tmp_path) == [date_dir / LGR_ZIP.name]
    (date_dir / LGR_ZIP.name).unlink()
    assert find_lgr_files(tmp_path) == [date_dir / "fgga_2020-07-16_f0000.txt"]


def test_read_lgr_all_weeks():
    data = read_lgr(DATA / "lgr")
    assert str(data.index.tz) == "UTC"
    assert data.index[0] == utc("2020-07-16 06:56")
    assert data.index[-1] == utc("2020-08-01 06:56")
    assert data.loc[utc("2020-07-16 07:00"), "CH4d_ppm"] == pytest.approx(1.091688)
    assert data.notna().all().all()


def test_read_lgr_native_resolution():
    assert len(read_lgr(DATA / "lgr", resample=None)) == 28302


def test_read_lgr_empty_directory(tmp_path):
    assert read_lgr(tmp_path).empty


# EXO2


def test_find_exo2_files():
    assert len(find_exo2_files(EXO2_DIR)) == 7


def test_read_exo2_file_csv():
    data = read_exo2_file(EXO2_CSV)
    assert list(data.columns) == EXO2_COLUMNS
    assert len(data) == 960
    assert data.index[0] == utc("2020-07-23 07:27:32")
    assert data.index[-1] == utc("2020-08-02 07:12:32")
    assert data["Temp_C"].iloc[0] == pytest.approx(7.924)
    assert (data.dtypes == float).all()


def test_read_exo2_drops_duplicate_rows_from_overlapping_exports():
    whole, part1, part2 = (read_exo2_file(p) for p in MAUR_PARTS)
    assert len(whole) == len(part1) + len(part2)
    data = read_exo2(MAUR_PARTS, resample=None)
    pd.testing.assert_frame_equal(data, whole)


def test_read_exo2_directory():
    data = read_exo2(EXO2_DIR, resample=None)
    assert len(data) == 6529
    assert not data.index.duplicated().any()
    resampled = read_exo2(EXO2_DIR)
    assert resampled.index[0] == utc("2020-06-04 14:30")
    assert resampled.index[-1] == utc("2020-09-03 21:16")


def test_read_exo2_file_day_first_dates(tmp_path):
    lines = exo2_lines(EXO2_CSV)
    header = lines.index(next(line for line in lines if line.startswith("Date (MM/DD/YYYY)")))
    for i in range(header + 1, len(lines)):
        month, day, rest = lines[i].split("/", 2)
        lines[i] = f"{day}/{month}/{rest}"
    day_first = tmp_path / EXO2_CSV.name
    day_first.write_text("\n".join(lines) + "\n", encoding="utf-16")
    pd.testing.assert_frame_equal(read_exo2_file(day_first), read_exo2_file(EXO2_CSV))


def test_read_exo2_file_xlsx(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    lines = exo2_lines(EXO2_CSV)[1:]  # Excel exports have no sep= line
    in_data = False
    for line in lines:
        cells = line.split(",")
        if in_data:
            cells = cells[:4] + [float(c) for c in cells[4:]]
        in_data = in_data or cells[0] == "Date (MM/DD/YYYY)"
        ws.append(cells)
    xlsx = tmp_path / "export.xlsx"
    wb.save(xlsx)
    pd.testing.assert_frame_equal(read_exo2_file(xlsx), read_exo2_file(EXO2_CSV))


def test_read_exo2_unknown_date_format(tmp_path):
    bad = tmp_path / "bad.csv"
    text = EXO2_CSV.read_text(encoding="utf-16").replace("7/23/2020", "2020.07.23")
    bad.write_text(text, encoding="utf-16")
    with pytest.raises(ValueError, match="Unrecognised date format"):
        read_exo2_file(bad)


def test_read_exo2_empty_directory(tmp_path):
    assert read_exo2(tmp_path).empty
