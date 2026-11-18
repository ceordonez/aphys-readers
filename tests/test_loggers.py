"""Tests of the mooring logger readers on trimmed real files in tests/data.

The files come from the Lake Soppen mooring (2016-2020). Formats not present
there (an Excel EXO2 export with an edited sheet first) are built from the real
files in a temporary directory.
"""

import csv
import shutil
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from aphys_readers import (
    find_hobo_files,
    find_minidot_files,
    find_rbr_files,
    find_roma_files,
    find_solinst_files,
    find_vemco_files,
    read_exo2_file,
    read_hobo,
    read_hobo_file,
    read_minidot,
    read_minidot_file,
    read_rbr,
    read_rbr_file,
    read_roma,
    read_roma_file,
    read_solinst,
    read_solinst_file,
    read_vemco,
    read_vemco_file,
)
from aphys_readers.rbr import rbr_serial
from aphys_readers.utils import offset_hours

DATA = Path(__file__).parent / "data"
VEMCO = DATA / "vemco"
HOBO = DATA / "hobo"
HOBO_U20 = DATA / "hobo_u20/20619145_2.csv"
MINIDOT = DATA / "minidot"
RBR = DATA / "rbr"
SOLINST = DATA / "solinst"
ROMA = DATA / "roma"
EXO2 = DATA / "exo2_mooring"

ROMA_COLUMNS = [
    "CH4_pct",
    "CO2_pct",
    "AR_CH4",
    "AR_CO2",
    "Tsensor_C",
    "Text_C",
    "Battery_V",
    "Press_bar",
]


def utc(timestamp):
    return pd.Timestamp(timestamp, tz="UTC")


# Time zones


@pytest.mark.parametrize(
    "text, hours",
    [("UTC+02:00", 2), ("UTC+2", 2), ("GMT+01:00", 1), ("+02:00", 2), ("UTC", 0), ("UTC-5", -5), (2, 2)],
)
def test_offset_hours(text, hours):
    assert offset_hours(text) == hours


@pytest.mark.parametrize("text", ["", "CEST", "two"])
def test_offset_hours_rejects_other_text(text):
    with pytest.raises(ValueError):
        offset_hours(text)


# Vemco


def test_read_vemco_file_comma_separated_date_and_time():
    data = read_vemco_file(VEMCO / "Minilog-II-T_357451_20170828_1.csv")
    assert list(data.columns) == ["Temp_C"]
    assert len(data) == 120
    # Header says UTC+2: 2017-05-22 20:34 local
    assert data.index[0] == utc("2017-05-22 18:34")
    assert data["Temp_C"].iloc[0] == 18.05


def test_read_vemco_file_date_time_in_one_field():
    data = read_vemco_file(VEMCO / "Minilog-II-T_357451_20171012_1.csv")
    assert len(data) == 120
    assert data.index[0] == utc("2017-08-28 18:32")
    assert data["Temp_C"].iloc[0] == 19.64


def test_read_vemco_file_offset_argument_overrides_header():
    data = read_vemco_file(VEMCO / "Minilog-II-T_357451_20171012_1.csv", utc_offset="UTC")
    assert data.index[0] == utc("2017-08-28 20:32")


def test_find_vemco_files_and_one_logger_per_call():
    assert len(find_vemco_files(VEMCO)) == 3
    with pytest.raises(ValueError, match="357443, 357451"):
        read_vemco(VEMCO)
    data = read_vemco(VEMCO, serial=357451, resample=None)
    assert len(data) == 240


# HOBO


def test_read_hobo_file_english():
    data = read_hobo_file(HOBO / "20034738_28aug.csv")
    assert list(data.columns) == ["Temp_C", "Light_lux"]
    assert len(data) == 100  # closing event row dropped
    assert data.index[0] == utc("2017-04-19 12:30")  # GMT+02:00
    assert data.iloc[0].tolist() == [23.196, 2497.2]


def test_read_hobo_file_spanish():
    data = read_hobo_file(HOBO / "es/20034739.csv")
    assert len(data) == 100
    assert data.index[0] == utc("2017-08-28 20:00")
    assert data["Temp_C"].iloc[0] == 18.331


def test_read_hobo_file_u20_water_level():
    data = read_hobo_file(HOBO_U20)
    assert list(data.columns) == ["Pressure_kPa", "Temp_C"]
    assert len(data) == 20  # coupler and host event rows dropped
    assert data.index[0] == utc("2025-05-12 11:30:17")  # GMT+00:00
    assert data["Pressure_kPa"].iloc[0] == 101.075
    assert data["Temp_C"].iloc[0] == 31.166
    # The closing row holds a reading and the end-of-file event
    assert data.index[-1] == utc("2025-06-19 15:30:17")


def test_read_hobo_one_logger_per_call():
    assert len(find_hobo_files(HOBO)) == 2
    with pytest.raises(ValueError, match="several loggers"):
        read_hobo(HOBO)
    assert len(read_hobo(HOBO, serial="20034739", resample=None)) == 100


# miniDOT


def test_read_minidot_file_cat():
    data = read_minidot_file(MINIDOT / "SN1159/Cat.TXT")
    assert list(data.columns) == ["Temp_C", "ODO_mgL", "ODO_pctsat", "Q"]
    assert len(data) == 150
    assert data.index[0] == utc("2016-05-25 13:36")
    assert data["Temp_C"].iloc[0] == pytest.approx(20.710455)


def test_read_minidot_file_cat_with_battery():
    data = read_minidot_file(MINIDOT / "SN069616/Cat.TXT")
    assert list(data.columns) == ["Battery_V", "Temp_C", "ODO_mgL", "ODO_pctsat", "Q"]
    assert data["Battery_V"].iloc[0] == 3.2


def test_read_minidot_file_daily():
    data = read_minidot_file(MINIDOT / "DATA/57A8BF40.txt")
    assert list(data.columns) == ["Temp_C", "ODO_mgL", "Q"]
    assert len(data) == 60
    assert data.index[0] == utc("2016-08-08 17:20")


def test_find_minidot_files_cat_else_daily():
    names = [f.relative_to(MINIDOT).as_posix() for f in find_minidot_files(MINIDOT)]
    assert names == ["DATA/57A8BF40.txt", "DATA/57A913A0.txt", "SN069616/Cat.TXT", "SN1159/Cat.TXT"]


def test_read_minidot_serial_without_leading_zeros():
    assert len(read_minidot(MINIDOT, serial=69616, resample=None)) == 150
    assert len(read_minidot(MINIDOT, serial="1159", resample=None)) == 150 + 120


# RBR


def test_read_rbr_file_odv_needs_offset():
    path = RBR / "020135_20160525_2238.txt"
    with pytest.raises(ValueError, match="utc_offset"):
        read_rbr_file(path)
    data = read_rbr_file(path, utc_offset="UTC+02:00")
    assert list(data.columns) == ["Temp_C"]
    assert len(data) == 300
    assert data.index[0] == utc("2016-04-26 08:00")
    assert data["Temp_C"].iloc[0] == pytest.approx(15.000572)


def test_read_rbr_file_plain_raw_values():
    data = read_rbr_file(RBR / "020138_20160525_2114.txt")
    assert list(data.columns) == ["Temp_raw"]  # thermistor ratios, not degrees
    assert data.index[0] == utc("2016-04-26 10:00")  # Z timestamps


def test_find_rbr_files():
    assert [f.name for f in find_rbr_files(RBR)] == [
        "020135_20160525_2238.txt",
        "020138_20160525_2114.txt",
        "208406_20250724_1223.rsk",
    ]


# The .rsk is the first 300 s of an RBRduet³ (Lake Bretaye 2025 mooring), still in air
RSK = RBR / "208406_20250724_1223.rsk"


def test_read_rbr_file_rsk():
    data = read_rbr_file(RSK)
    # temp05, the hidden pressure-sensor thermistor, is left out
    assert list(data.columns) == ["Temp_C", "Pres_dbar"]
    assert len(data) == 300
    assert data.index[0] == utc("2025-07-17 12:00:00")  # stored in UTC
    assert data.index[-1] == utc("2025-07-17 12:04:59")
    assert data["Temp_C"].iloc[0] == pytest.approx(24.896167, abs=1e-6)
    assert data["Pres_dbar"].iloc[0] == pytest.approx(8.250604, abs=1e-6)


def test_read_rbr_file_rsk_offset_and_serial():
    data = read_rbr_file(RSK, utc_offset="UTC+02:00")
    assert data.index[0] == utc("2025-07-17 10:00:00")
    assert rbr_serial(RSK) == "208406"
    assert len(read_rbr(RBR, serial=208406, resample="1min")) == 5


def test_find_rbr_files_skips_export_of_rsk(tmp_path):
    shutil.copy(RSK, tmp_path / RSK.name)
    (tmp_path / RSK.with_suffix(".txt").name).write_text("export of the same samples")
    assert [f.name for f in find_rbr_files(tmp_path)] == [RSK.name]


# Solinst


def test_find_solinst_files_one_copy_per_kind():
    found = [f.relative_to(SOLINST).as_posix() for f in find_solinst_files(SOLINST)]
    assert found == [
        "2018/Soppensee_29102018_2085605_Compensated.csv",
        "2019/Barologgerr_Soppensee_20190604.csv",
        "2019/LevelLogger_Soppensee_2085605_20190604_compensated.csv",
    ]
    raw = [f.name for f in find_solinst_files(SOLINST / "2019", compensated=False)]
    assert raw == ["Barologgerr_Soppensee_20190604.csv", "LevelLogger_Soppensee_20190604.csv"]


def test_read_solinst_file_xle_matches_csv():
    xle = read_solinst_file(SOLINST / "2019/LevelLogger_Soppensee_20190604Compensated.xle", "UTC+02:00")
    csv_ = read_solinst_file(
        SOLINST / "2019/LevelLogger_Soppensee_2085605_20190604_compensated.csv", "UTC+02:00"
    )
    assert list(xle.columns) == ["Level_m", "Temp_C"]
    pd.testing.assert_frame_equal(xle, csv_)
    assert xle.index[0] == utc("2019-04-10 15:29:59")


def test_read_solinst_file_raw_level_and_barologger():
    raw = read_solinst_file(SOLINST / "2019/LevelLogger_Soppensee_20190604.xle", 2)
    assert raw["Level_m"].iloc[0] == 9.5382  # includes the atmosphere
    baro = read_solinst_file(SOLINST / "2019/Barologger_Soppensee_20190604.xle", 2)
    assert list(baro.columns) == ["Pressure_kPa", "Temp_C"]


def test_read_solinst_file_day_first_dates():
    data = read_solinst_file(SOLINST / "2018/Soppensee_29102018_2085605_Compensated.csv", 2)
    assert data.index[0] == utc("2018-09-14 09:54:52")


def test_read_solinst_needs_offset_and_one_logger():
    with pytest.raises(ValueError, match="utc_offset"):
        read_solinst_file(SOLINST / "2018/Soppensee_29102018_2085605_Compensated.csv")
    with pytest.raises(ValueError, match="several loggers"):
        read_solinst(SOLINST / "2019", utc_offset=2)
    data = read_solinst(SOLINST, serial=2085605, utc_offset=2, resample=None)
    assert len(data) == 200


# CH4/CO2 probes ("Roma")


def test_read_roma_file_drops_reset_clock_rows():
    data = read_roma_file(ROMA / "2019/Probe_04_130819092118.csv", utc_offset="UTC+02:00")
    assert list(data.columns) == ROMA_COLUMNS
    assert len(data) == 60 - 14  # 14 rows dated 00/00/00
    assert data.index[0] == utc("2018-10-28 11:02")
    assert data.index[-1] == utc("2019-08-12 16:02")


def test_read_roma_file_processed_copy_uses_excel_time():
    data = read_roma_file(ROMA / "2019/pCO2_20190604_20190812.txt", utc_offset=2)
    assert len(data) == 60  # the reset rows were re-timed in the copy
    assert data.index[-1] == utc("2019-08-13 06:02")


def test_read_roma_file_excel_mangled_dates():
    data = read_roma_file(ROMA / "excel/Probe_01_290817000128.csv", utc_offset=2)
    # 2003-11-16 14:02 is 03/11/16; 2028-08-17 23:02 is 28/08/17
    assert data.index[0] == utc("2016-11-03 12:02")
    assert data.index[-1] == utc("2017-08-28 21:02")
    assert data["CH4_pct"].iloc[0] == -0.0027


def test_read_roma_file_corrupt_dates_dropped():
    # The last rows carry dates such as 04/03/40 and 09/02/00
    assert len(read_roma_file(ROMA / "2016/Probe_01_100317143657.csv", 2)) == 31
    assert len(read_roma_file(ROMA / "2016/Probe_03_100317143800.csv", 2)) == 30


def test_find_roma_files_raw_or_processed():
    assert [f.name for f in find_roma_files(ROMA / "2019")] == ["Probe_04_130819092118.csv"]
    processed = find_roma_files(ROMA / "2019", processed=True)
    assert [f.name for f in processed] == ["pCO2_20190604_20190812.txt"]


def test_read_roma_probe_number_is_the_serial():
    with pytest.raises(ValueError, match="1, 3"):
        read_roma(ROMA / "2016", utc_offset=2)
    data = read_roma(ROMA / "2016", serial=3, utc_offset=2)
    assert len(data) == 30
    with pytest.raises(ValueError, match="utc_offset"):
        read_roma(ROMA / "2016", serial=3)


# EXO2 exports from the mooring


def test_read_exo2_file_kor_csv_without_sep_line():
    data = read_exo2_file(EXO2 / "EXO_SD_15L103185_051618_144500.csv")
    assert len(data) == 60
    assert data.index[0] == utc("2018-05-16 14:45")
    assert data["Temp_C"].iloc[0] == 15.061  # header "Temp C"
    assert {"ORP_mV", "ORPraw_mV"} <= set(data.columns)


def test_read_exo2_file_latin1_copy_with_dotted_dates():
    data = read_exo2_file(EXO2 / "resaved/EXO_SD_15L103185_012318_141500.csv")
    assert len(data) == 60
    assert data.index[0] == utc("2018-01-23 14:15")
    assert data["Temp_C"].iloc[0] == 12.766
    assert data["SpCond_uScm"].iloc[0] == 36.9  # µ decoded correctly


def test_read_exo2_file_excel_uses_kor_sheet(tmp_path):
    with open(EXO2 / "EXO_SD_15L103185_051618_144500.csv", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    book = openpyxl.Workbook()
    edited = book.active
    edited.title = "Sheet1 (2)"  # an edited copy placed before the export
    header = rows.index(next(r for r in rows if r and r[0].startswith("Date")))
    edited.append(rows[header][:2] + ["ExcelTime", "Temp"])
    edited.append(rows[header + 1][:2] + ["43236.6", "99"])
    kor = book.create_sheet("Sheet1")
    for row in rows:
        kor.append(row)
    path = tmp_path / "export.xlsx"
    book.save(path)
    data = read_exo2_file(path)
    expected = read_exo2_file(EXO2 / "EXO_SD_15L103185_051618_144500.csv")
    assert len(data) == len(expected)
    assert data["Temp_C"].iloc[0] == 15.061
