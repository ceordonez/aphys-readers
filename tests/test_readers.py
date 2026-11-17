"""Tests on the real instrument files in tests/data.

Formats not present there (plain-text LGR, Excel and day-first EXO2 exports,
other NMEA talkers)
are derived from the real files in a temporary directory.
"""

import zipfile
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import pytest

from aphys_readers import (
    find_adcp_files,
    find_kestrel_files,
    read_adcp,
    read_adcp_file,
    read_kestrel,
    read_kestrel_file,
    read_pd0,
    find_campbell_files,
    read_campbell,
    read_campbell_file,
    find_exo2_files,
    find_gps_files,
    find_lgr_files,
    find_meteoswiss_files,
    find_seabird_files,
    merge_nearest,
    read_exo2,
    read_exo2_file,
    read_gps,
    read_gps_file,
    read_lgr,
    read_lgr_file,
    read_meteoswiss,
    read_meteoswiss_file,
    read_seabird,
    read_seabird_file,
)
from aphys_readers.exo2 import date_formats

DATA = Path(__file__).parent / "data"
LGR_WEEK1 = DATA / "lgr/AC_AtmGHG_20200716_20200722"
LGR_ZIP = LGR_WEEK1 / "2020-07-16/fgga_2020-07-16_f0000.txt.zip"
EXO2_DIR = DATA / "exo2"
EXO2_CSV = EXO2_DIR / "EXO_SD_15L103185_072320_072732.csv"
GPS_DIR = DATA / "gps"
GPS_GPX = GPS_DIR / "etrex/Track_16-JAN-25 180154.gpx"
GPS_NMEA = GPS_DIR / "adcp/T20_0/T20_0_000_26-02-05_105121_GPS.TXT"
# Maur_..._143037.csv holds the rows of its _1 and _2 parts
MAUR_PARTS = [EXO2_DIR / f"Maur_12M101161_060420_143037{s}.csv" for s in ("", "_1", "_2")]

LGR_COLUMNS = ["H2O_ppm", "CH4d_ppm", "CO2d_ppm", "GasP_torr", "GasT_C", "RD0_us", "RD1_us"]
EXO2_COLUMNS = [
    "Cond_uScm",
    "Depth_m",
    "nLFCond_uScm",
    "ODO_pctsat",
    "ODO_pctlocal",
    "ODO_mgL",
    "Press_psia",
    "Sal_psu",
    "SpCond_uScm",
    "TDS_mgL",
    "Turb_FNU",
    "TSS_mgL",
    "Temp_C",
    "VPos_m",
    "Battery_V",
]
GPS_COLUMNS = ["Lat_deg", "Lon_deg", "Alt_m"]


def utc(timestamp):
    return pd.Timestamp(timestamp, tz="UTC")


def exo2_lines(path):
    return path.read_text(encoding="utf-16").splitlines()


# LGR


@pytest.mark.parametrize("directory", [DATA, DATA / "lgr", LGR_WEEK1])
def test_find_lgr_files_recursive(directory):
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
    date_dir = tmp_path / "2020" / "2020-07-16"
    date_dir.mkdir(parents=True)
    (date_dir / LGR_ZIP.name).write_bytes(LGR_ZIP.read_bytes())
    with zipfile.ZipFile(LGR_ZIP) as zf:
        zf.extract(zf.namelist()[0], date_dir)
    assert find_lgr_files(tmp_path) == [date_dir / LGR_ZIP.name]
    (date_dir / LGR_ZIP.name).unlink()
    assert find_lgr_files(tmp_path) == [date_dir / "fgga_2020-07-16_f0000.txt"]


def test_find_lgr_files_skips_superseded_empty_and_other_files(tmp_path):
    date_dir = tmp_path / "2020" / "2020-07-16"
    (date_dir / "_superseded").mkdir(parents=True)
    with zipfile.ZipFile(LGR_ZIP) as zf:
        zf.extract(zf.namelist()[0], date_dir)
    data_file = date_dir / "fgga_2020-07-16_f0000.txt"
    (date_dir / "_superseded" / data_file.name).write_bytes(data_file.read_bytes()[:5000])
    (date_dir / "_superseded" / "fgga_2020-07-16_f0000__44dfbfa9.txt").write_text("old")
    (date_dir / "fgga_2020-07-16_b0000.txt").write_text("")
    (date_dir / "fgga_2020-07-16_f0001.txt").write_text("")
    (date_dir / "notes.txt").write_text("field notes")
    assert find_lgr_files(tmp_path) == [data_file]


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
    assert data["Depth_m"].iloc[0] == pytest.approx(0.680)
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


def exo2_parts(path):
    """Header cells and data rows of an old-format (comma-separated) KOR CSV."""
    lines = exo2_lines(path)
    start = next(i for i, line in enumerate(lines) if line.startswith("Date (MM/DD/YYYY)"))
    return lines[start].split(","), [line.split(",") for line in lines[start + 1 :] if line]


def new_format_lines(drop_col=None):
    """EXO2_CSV rewritten as a newer KOR export: upper-case headers, time
    first, ';' with decimal commas, day-first dates, newest row first."""
    header, rows = exo2_parts(EXO2_CSV)
    order = [1, 0, *range(2, len(header))]
    if drop_col is not None:
        order.remove(header.index(drop_col))
    out = [";".join(header[i].upper() for i in order)]
    for row in reversed(rows):
        month, day, year = row[0].split("/")
        row = [f"{int(day):02d}/{int(month):02d}/{year}", *row[1:]]
        out.append(";".join(row[i] for i in order).replace(".", ","))
    return out


def new_format_file(path, body):
    meta = ["sep=;", "Kor MEASUREMENT DATA FILE EXPORT", "", "FILE CREATED:;21/10/2024 10:13:46", ""]
    path.write_text("\n".join(meta + body) + "\n", encoding="utf-16")
    return path


def test_find_exo2_files_one_format_per_recording(tmp_path):
    day = tmp_path / "2020"
    (day / "_superseded").mkdir(parents=True)
    names = [
        "rec_A.csv", "rec_A.xls", "rec_A.bin",  # CSV preferred
        "rec_B.xls", "rec_B.bin",  # Excel only
        "rec_C_1.csv", "rec_C_2.csv", "rec_C.xls",  # CSV parts preferred
        "_superseded/rec_A__1a2b3c4d.csv",
    ]  # fmt: skip
    for name in names:
        (day / name).write_text("x")
    (day / "rec_D.csv").write_text("")  # empty
    found = [f.relative_to(day).as_posix() for f in find_exo2_files(tmp_path)]
    assert found == ["rec_A.csv", "rec_B.xls", "rec_C_1.csv", "rec_C_2.csv"]


def test_read_exo2_file_new_kor_format(tmp_path):
    path = new_format_file(tmp_path / "new.csv", new_format_lines())
    expected = read_exo2_file(EXO2_CSV)
    pd.testing.assert_frame_equal(read_exo2_file(path).sort_index(), expected)


def test_read_exo2_file_multiple_sections(tmp_path):
    first = new_format_lines()
    second = new_format_lines(drop_col="TSS mg/L")
    summary = ["", "MEAN VALUE:" + ";" * 25 + "1,0", "", "SENSOR SERIAL NUMBER:;;;;;;15J103285"]
    path = new_format_file(tmp_path / "backup.csv", first[:101] + summary + [second[0], *second[101:]])
    data = read_exo2_file(path).sort_index()
    expected = read_exo2_file(EXO2_CSV)
    assert len(data) == len(expected)
    # The second section (oldest rows, as rows are newest first) lacks TSS
    assert data["TSS_mgL"].isna().sum() == len(expected) - 100
    pd.testing.assert_frame_equal(data.drop(columns="TSS_mgL"), expected.drop(columns="TSS_mgL"))


def test_read_exo2_file_dot_separator(tmp_path):
    # A KOR export with sep="." writes values with decimal commas, but splits
    # the "Time (Fract. Sec)" header and its 0.0 values in two
    header, rows = exo2_parts(EXO2_CSV)
    lines = exo2_lines(EXO2_CSV)
    meta = [line.replace(",", ".") for line in lines[: lines.index(",".join(header))]]
    body = [".".join(header)]
    for row in rows:
        values = [v.replace(".", ",") for v in row[3:]]
        body.append(".".join([*row[:2], row[2], *values]))
    path = tmp_path / "dot.csv"
    path.write_text("\n".join(meta + body) + "\n", encoding="utf-16")
    pd.testing.assert_frame_equal(read_exo2_file(path), read_exo2_file(EXO2_CSV))


def test_read_exo2_file_fractional_seconds(tmp_path):
    # Sampling faster than 1 Hz: rows share a second and differ in "Time (Fract. Sec)"
    lines = exo2_lines(EXO2_CSV)
    start = next(i for i, line in enumerate(lines) if line.startswith("Date (MM/DD/YYYY)"))
    row = lines[start + 1].split(",")
    quarter = [",".join([*row[:2], f"{s:.2f}", *row[3:]]) for s in (0, 0.25, 0.5, 0.75)]
    path = tmp_path / "fast.csv"
    path.write_text("\n".join(lines[: start + 1] + quarter) + "\n", encoding="utf-16")
    data = read_exo2_file(path)
    assert data.index.name == "Datetime"
    assert list(data.index - data.index[0]) == [pd.Timedelta(seconds=s) for s in (0, 0.25, 0.5, 0.75)]


@pytest.mark.parametrize(
    ("created", "first_format"),
    [
        ("7/29/2020 1:36:35 PM", "%m/%d/%Y"),  # month above 12
        ("21/10/2024 10:13:46", "%d/%m/%Y"),  # day above 12
        ("9/2/2020 2:59:17 PM", "%m/%d/%Y"),  # ambiguous, 12-hour clock
        ("06/08/2023 20:44:08", "%d/%m/%Y"),  # ambiguous, 24-hour clock
        (None, "%m/%d/%Y"),
    ],
)
def test_date_formats_from_file_created(created, first_format):
    assert date_formats(created)[0] == first_format


def test_date_formats_twelve_hour_rows_win_over_24_hour_stamp():
    # Copy re-saved by Excel: 24-hour stamp, rows still "9:01:40 am"
    assert date_formats("06/08/2026 15:35", twelve_hour=True)[0] == "%m/%d/%Y"
    # A stamp with a day above 12 still decides
    assert date_formats("21/10/2024 10:13", twelve_hour=True)[0] == "%d/%m/%Y"


def test_read_exo2_file_recent_kor_headers(tmp_path):
    # Recent KOR: TIME (h:mm:ss tt) and DATE (M/d/yyyy), 12-hour clock, UTF-16
    lines = [
        "sep=,",
        "Kor MEASUREMENT DATA FILE EXPORT",
        "FILE CREATED:,06/08/2026 15:35",
        "TIME (h:mm:ss tt),DATE (M/d/yyyy),SITE NAME,DEPTH M,TEMP °C",
        "1:01:40 pm,06/08/2026,RIVER T10,0.185,27.727",
        "9:01:10 am,06/08/2026,RIVER T10,6.239,28.402",
    ]
    path = tmp_path / "RIVER_T10.csv"
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-16")
    data = read_exo2_file(path)
    assert list(data.columns) == ["Depth_m", "Temp_C"]
    assert list(data.index) == [pd.Timestamp("2026-06-08 13:01:40", tz="UTC"),
                                pd.Timestamp("2026-06-08 09:01:10", tz="UTC")]


# GPS


def test_find_gps_files():
    assert find_gps_files(GPS_DIR) == [
        GPS_NMEA,
        GPS_GPX,
        GPS_DIR / "etrex/Waypoints_13-JAN-25.gpx",
    ]


def test_read_gps_file_gpx():
    data = read_gps_file(GPS_GPX)
    assert len(data) == 100
    assert list(data.columns) == GPS_COLUMNS
    assert data.index.name == "Datetime"
    assert data.index[0] == utc("2025-01-14 02:48:36")
    assert data.iloc[0].tolist() == [13.2954753935, -14.2065412458, 29.94]


def test_read_gps_file_gpx_corrupted_time(tmp_path):
    # Some OpenCPN exports have binary garbage in a <time>, making invalid XML
    content = GPS_GPX.read_bytes()
    first_time = b"<time>2025-01-14T02:48:36Z</time>"
    assert first_time in content
    path = tmp_path / "corrupted.gpx"
    path.write_bytes(content.replace(first_time, b"<time>\x80\xef&#16;\tP</time>"))
    data = read_gps_file(path)
    assert len(data) == 99
    assert data.index[0] == utc("2025-01-14 02:48:46")
    assert data.iloc[0].tolist() == read_gps_file(GPS_GPX).iloc[1].tolist()

@pytest.mark.parametrize("corrupted", [False, True])
def test_read_gps_file_gpx_skips_ais_tracks(tmp_path, corrupted):
    # OpenCPN exports can hold tracks of other ships recorded from AIS
    content = GPS_GPX.read_bytes()
    start, end = content.index(b"<trk>"), content.index(b"</trk>") + len(b"</trk>")
    track = content[start:end]
    ais = track.replace(b"<trk>", b"<trk>\n<name>AIS  (331394000) 2021-08-18 17:04:32</name>", 1)
    if corrupted:
        ais = ais.replace(b"<time>2025-01-14T02:48:36Z</time>", b"<time>\x80</time>")
    path = tmp_path / "ais.gpx"
    path.write_bytes(content[:end] + ais + content[end:])
    assert read_gps_file(path).equals(read_gps_file(GPS_GPX))


def test_read_gps_file_gpx_waypoints_only():
    assert read_gps_file(GPS_DIR / "etrex/Waypoints_13-JAN-25.gpx").empty


def test_read_gps_file_nmea():
    data = read_gps_file(GPS_NMEA)
    assert len(data) == 100
    assert list(data.columns) == GPS_COLUMNS
    assert data.index[0] == utc("2026-02-05 10:52:28")
    assert data.index[-1] == utc("2026-02-05 10:54:07")
    # 1318.8548,N,01629.4987,W
    assert data["Lat_deg"].iloc[0] == pytest.approx(13 + 18.8548 / 60)
    assert data["Lon_deg"].iloc[0] == pytest.approx(-(16 + 29.4987 / 60))
    assert data["Alt_m"].iloc[0] == 9.5


def test_read_gps_file_nmea_other_talker_and_no_fix(tmp_path):
    lines = GPS_NMEA.read_text().splitlines()[:18]
    lines = [line.replace("$GP", "$GN") for line in lines]
    # Second GGA without a fix (quality 0)
    lines[11] = lines[11].replace(",W,1,", ",W,0,")
    path = tmp_path / "GN_GPS.TXT"
    path.write_text("\n".join(lines))
    data = read_gps_file(path)
    assert data.index.tolist() == [utc("2026-02-05 10:52:28")]


def test_read_gps_directory():
    data = read_gps(GPS_DIR, resample=None)
    assert len(data) == 200
    assert data.index.is_monotonic_increasing
    # 10:52:28 to 10:54:07
    assert len(read_gps(GPS_DIR / "adcp")) == 3


def test_read_gps_empty_directory(tmp_path):
    assert read_gps(tmp_path).empty


# Merging


def lgr_native_and_minutes():
    native = read_lgr_file(LGR_ZIP)
    minutes = read_lgr(LGR_ZIP)[["CH4d_ppm"]].rename(columns={"CH4d_ppm": "CH4_1min"})
    return native, minutes


def test_merge_nearest_different_resolutions():
    native, minutes = lgr_native_and_minutes()
    merged = merge_nearest(native, minutes)
    assert merged.index.equals(native.index)
    assert list(merged.columns) == [*LGR_COLUMNS, "CH4_1min"]
    # 06:56:34 is nearest to the 06:57 bin (26 s away)
    assert merged.index[0] == utc("2020-07-16 06:56:34.139")
    assert merged["CH4_1min"].iloc[0] == minutes.loc[utc("2020-07-16 06:57"), "CH4_1min"]
    assert merged["CH4_1min"].notna().all()


def test_merge_nearest_skips_empty_bins():
    native, minutes = lgr_native_and_minutes()
    minutes.loc[utc("2020-07-16 06:57")] = float("nan")
    merged = merge_nearest(native, minutes)
    # The empty 06:57 bin is ignored; the 06:56 bin (34 s away) is used
    assert merged["CH4_1min"].iloc[0] == minutes.loc[utc("2020-07-16 06:56"), "CH4_1min"]


@pytest.mark.parametrize("tolerance", ["10s", pd.Timedelta("10s")])
def test_merge_nearest_tolerance(tolerance):
    native, minutes = lgr_native_and_minutes()
    merged = merge_nearest(native, minutes, tolerance)
    assert merged["CH4_1min"].notna().sum() == 589
    assert merge_nearest(native, minutes, None)["CH4_1min"].notna().all()


def test_merge_nearest_different_time_units():
    native, minutes = lgr_native_and_minutes()
    minutes.index = minutes.index.as_unit("ns")
    merged = merge_nearest(native, minutes)
    assert merged.index.equals(native.index)
    assert merged["CH4_1min"].notna().all()


SEABIRD_DIR = DATA / "seabird"
SEABIRD_CNV = SEABIRD_DIR / "SBE19plus_01907803_2018_04_10.cnv"


def test_read_seabird_file():
    data = read_seabird_file(SEABIRD_CNV, utc_offset="UTC")
    assert len(data) == 40
    assert {"Press_dbar", "Depth_m", "Temp_C", "Cond_uScm", "DO_umolL"} <= set(data.columns)
    assert data.index[0] == utc("2018-04-10 11:08:58")
    assert data.index[1] - data.index[0] == pd.Timedelta("250ms")
    assert data["Press_dbar"].iloc[0] == pytest.approx(-0.604)  # sea pressure: < 0 at the surface
    assert data["Temp_C"].iloc[0] == pytest.approx(12.4859)
    assert (data.dtypes == float).all()


def test_read_seabird_file_needs_offset():
    with pytest.raises(ValueError, match="utc_offset"):
        read_seabird_file(SEABIRD_CNV)
    local = read_seabird_file(SEABIRD_CNV, utc_offset="UTC+02:00")
    assert local.index[0] == utc("2018-04-10 09:08:58")


def test_read_seabird_file_time_from_scan_column(tmp_path):
    # Every second row dropped: times must follow the scan numbers, not the row numbers
    lines = SEABIRD_CNV.read_text(encoding="latin-1").splitlines()
    end = lines.index("*END*")
    names = [i for i, line in enumerate(lines) if line.startswith("# name")]
    head = lines[: names[-1] + 1] + [f"# name {len(names)} = scan: Scan Count"] + lines[names[-1] + 1 : end + 1]
    rows = [f"{line} {i + 1}" for i, line in enumerate(lines[end + 1 :])][::2]
    path = tmp_path / "every_second_scan.cnv"
    path.write_text("\n".join(head + rows), encoding="latin-1")
    data = read_seabird_file(path, utc_offset="UTC")
    assert "scan" not in data
    assert data.index[1] - data.index[0] == pd.Timedelta("500ms")


def test_read_seabird_directory_keeps_one_copy(tmp_path):
    (tmp_path / "a.cnv").write_bytes(SEABIRD_CNV.read_bytes())
    (tmp_path / "a_copy.cnv").write_bytes(SEABIRD_CNV.read_bytes())
    assert len(find_seabird_files(tmp_path)) == 2
    data = read_seabird(tmp_path, utc_offset="UTC")
    assert len(data) == 40


def test_read_seabird_file_asc_with_hdr(tmp_path):
    # SeaTerm's split conversion: header in .hdr, column titles and data in .asc
    lines = SEABIRD_CNV.read_text(encoding="latin-1").splitlines()
    end = lines.index("*END*")
    (tmp_path / "cast.hdr").write_text("\n".join(lines[: end + 1]), encoding="latin-1")
    (tmp_path / "cast.asc").write_text("\n".join(["      DepFM  Density00 ...", *lines[end + 1 :]]), encoding="latin-1")
    assert find_seabird_files(tmp_path) == [tmp_path / "cast.asc"]
    data = read_seabird_file(tmp_path / "cast.asc", utc_offset="UTC")
    pd.testing.assert_frame_equal(data, read_seabird_file(SEABIRD_CNV, utc_offset="UTC"))
    # With a .cnv of the same name, the .asc is not listed
    (tmp_path / "cast.cnv").write_bytes(SEABIRD_CNV.read_bytes())
    assert find_seabird_files(tmp_path) == [tmp_path / "cast.cnv"]


METEOSWISS_DIR = DATA / "meteoswiss"
METEOSWISS_EGO = METEOSWISS_DIR / "ogd-smn_ego_t_historical_2010-2019.csv"


def test_read_meteoswiss_file():
    data = read_meteoswiss_file(METEOSWISS_EGO)
    assert len(data) == 12
    assert data.index[0] == utc("2010-01-01 00:00")
    assert data.index.name == "Datetime"
    # Parameters not measured at the station (empty columns) are dropped
    assert "tre005s0" not in data and "Tair5cm_C" not in data
    assert {"Tair_C", "RH_pct", "Press_hPa", "WS_ms", "WD_deg", "Precip_mm", "SWin_Wm2"} <= set(data.columns)
    row = data.loc[utc("2017-07-01 10:00")]
    assert row["Tair_C"] == pytest.approx(17.1)
    assert row["SWin_Wm2"] == 388
    assert row["Press_hPa"] == pytest.approx(954.6)
    assert pd.isna(data["Tair_C"].iloc[0])  # empty field = missing
    assert (data.dtypes == float).all()


def test_find_meteoswiss_files(tmp_path):
    (tmp_path / "ogd-smn_meta_parameters.csv").write_text("parameter_shortname;parameter_unit\n")
    for name in (
        "ogd-smn_ego_t_historical_2010-2019.csv",
        "ogd-smn_ego_t_recent.csv",
        "ogd-smn_ego_h_historical_2010-2019.csv",
        "ogd-smn_ego_t_historical_2010-2019-Laptop-safeBackup-0001.csv",
    ):
        (tmp_path / name).write_bytes(METEOSWISS_EGO.read_bytes())
    assert [f.name for f in find_meteoswiss_files(tmp_path)] == [
        "ogd-smn_ego_t_historical_2010-2019-Laptop-safeBackup-0001.csv",
        "ogd-smn_ego_t_historical_2010-2019.csv",
        "ogd-smn_ego_t_recent.csv",
    ]
    assert [f.name for f in find_meteoswiss_files(tmp_path, "h")] == ["ogd-smn_ego_h_historical_2010-2019.csv"]


def test_read_meteoswiss_one_station(tmp_path):
    (tmp_path / METEOSWISS_EGO.name).write_bytes(METEOSWISS_EGO.read_bytes())
    lines = METEOSWISS_EGO.read_text().replace("EGO;", "LUZ;")
    (tmp_path / "ogd-smn_luz_t_historical_2010-2019.csv").write_text(lines)
    with pytest.raises(ValueError, match="several"):
        read_meteoswiss(tmp_path)
    ego = read_meteoswiss(tmp_path, station="ego")
    pd.testing.assert_frame_equal(ego, read_meteoswiss_file(METEOSWISS_EGO))


def test_read_meteoswiss_empty_directory(tmp_path):
    assert read_meteoswiss(tmp_path).empty


CAMPBELL_DIR = DATA / "campbell"
CAMPBELL_ATMOS41 = CAMPBELL_DIR / "CR200-Soppen_Atmos41_10min.dat"


def test_read_campbell_file():
    data = read_campbell_file(CAMPBELL_ATMOS41, utc_offset="UTC+01:00")
    assert len(data) == 20
    assert data.index[0] == utc("2018-05-29 13:20:00")
    assert data.index.name == "Datetime"
    assert "RECORD" not in data
    assert data["Record"].iloc[0] + 1 == data["Record"].iloc[1]  # the logger's record number
    assert {"SWin_Wm2", "Tair_C", "Press_kPa", "VapPress_kPa", "WS_ms", "WD_deg", "Precip_mm", "Battery_V"} <= set(data.columns)
    assert data["Tair_C"].iloc[0] == pytest.approx(19.7)
    assert data["Press_kPa"].iloc[1] == pytest.approx(94.71)
    assert (data.dtypes == float).all()


def test_read_campbell_file_needs_offset():
    with pytest.raises(ValueError, match="utc_offset"):
        read_campbell_file(CAMPBELL_ATMOS41)


def test_read_campbell_file_nan(tmp_path):
    lines = CAMPBELL_ATMOS41.read_text().splitlines()
    fields = lines[5].split(",")
    fields[3] = '"NAN"'
    path = tmp_path / "nan.dat"
    path.write_text("\n".join(lines[:5] + [",".join(fields)] + lines[6:]))
    data = read_campbell_file(path, utc_offset="UTC")
    assert pd.isna(data["Tair_C"].iloc[1])


def test_read_campbell_directory_overlapping_downloads(tmp_path):
    # A later download repeats the rows still in the logger memory
    lines = CAMPBELL_ATMOS41.read_text().splitlines()
    (tmp_path / "20180712").mkdir()
    (tmp_path / "20180913").mkdir()
    (tmp_path / "20180712/table.dat").write_text("\n".join(lines[:14]))
    (tmp_path / "20180913/table.dat").write_text("\n".join(lines))
    (tmp_path / "notes.txt").write_text("not a table")
    assert len(find_campbell_files(tmp_path)) == 2
    data = read_campbell(tmp_path, utc_offset="UTC")
    pd.testing.assert_frame_equal(data, read_campbell_file(CAMPBELL_ATMOS41, utc_offset="UTC"), check_freq=False)


def test_read_campbell_one_table(tmp_path):
    lines = CAMPBELL_ATMOS41.read_text().splitlines()
    (tmp_path / "a.dat").write_text("\n".join(lines))
    (tmp_path / "b.dat").write_text("\n".join([lines[0].replace("Atmos41_10min", "Daily"), *lines[1:]]))
    with pytest.raises(ValueError, match="several tables"):
        read_campbell(tmp_path, utc_offset="UTC")
    assert len(read_campbell(tmp_path, utc_offset="UTC", table="Daily")) == 20


def test_read_campbell_empty_directory(tmp_path):
    assert read_campbell(tmp_path, utc_offset="UTC").empty


CAMPBELL_CR300 = CAMPBELL_DIR / "CR300-Bintang_ATMOS41_Table.dat"


def test_read_campbell_file_cr300_names():
    # ATMOS 41 on a CR300 (Gambia): 1-min samples with other field names
    data = read_campbell_file(CAMPBELL_CR300, utc_offset="UTC")
    assert len(data) == 10
    assert data.index[0] == utc("2025-01-15 12:00:00")
    assert list(data.columns) == [
        "Record", "SWin_Wm2", "Precip_mm", "Strikes_count", "WS_ms", "WD_deg",
        "Gust_ms", "Tair_C", "VapPress_kPa", "Press_kPa",
    ]
    assert data["SWin_Wm2"].iloc[0] == 758
    assert data["WS_ms"].iloc[1] == pytest.approx(1.66)
    assert data["Tair_C"].iloc[0] == pytest.approx(27.3)


# Kestrel

KESTREL_DIR = DATA / "kestrel"
KESTREL_SFM = KESTREL_DIR / "sfm/WEATHER - 2886315_2025-01-12 19_09_00.csv"
KESTREL_SOPPEN = KESTREL_DIR / "soppen/WEATHER - 2111767_2018-05-19 10_48_30.csv"
KESTREL_COLUMNS = [
    "Tair_C", "Twet_C", "RH_pct", "Baro_hPa", "Alt_m", "Press_hPa", "WS_ms", "HeatIndex_C",
    "Tdew_C", "DensAlt_m", "Crosswind_ms", "Headwind_ms", "WDmag_deg", "WD_deg", "WindChill_C",
]


def test_read_kestrel_file_5500l():
    data = read_kestrel_file(KESTREL_SFM, utc_offset="UTC")
    assert list(data.columns) == KESTREL_COLUMNS
    assert len(data) == 20
    assert data.index.name == "Datetime"
    # The export starts with a stale point from an earlier deployment
    assert data.index[0] == utc("2024-04-11 04:58:30")
    assert data.index[1] == utc("2025-01-11 15:50:00")
    assert data["Tair_C"].iloc[1] == pytest.approx(32.1)
    assert data["Press_hPa"].iloc[1] == pytest.approx(1011.0)
    # No wind vane: "***" directions are missing
    assert data["WD_deg"].isna().all()
    assert (data.dtypes == float).all()


def test_read_kestrel_file_older_units():
    # LiNK 1.02 writes "Deg. C" and "m" where 1.04 writes "Celsius" and "Meters"
    data = read_kestrel_file(KESTREL_SOPPEN, utc_offset="UTC+02:00")
    assert list(data.columns) == KESTREL_COLUMNS
    assert data.index[0] == utc("2016-10-06 11:28:00")
    assert data["WS_ms"].iloc[0] == pytest.approx(3.6)
    assert data["WD_deg"].iloc[0] == pytest.approx(79.0)


def test_read_kestrel_file_needs_offset():
    with pytest.raises(ValueError, match="utc_offset"):
        read_kestrel_file(KESTREL_SFM)


def test_read_kestrel_one_meter_per_call():
    assert len(find_kestrel_files(KESTREL_DIR)) == 2
    with pytest.raises(ValueError, match="several loggers"):
        read_kestrel(KESTREL_DIR, utc_offset="UTC")
    data = read_kestrel(KESTREL_DIR, utc_offset="UTC", serial=2886315, resample=None)
    pd.testing.assert_frame_equal(data, read_kestrel_file(KESTREL_SFM, utc_offset="UTC"))


def test_read_kestrel_overlapping_downloads(tmp_path):
    # Each download holds the whole meter memory
    lines = KESTREL_SFM.read_text().splitlines()
    (tmp_path / "a.csv").write_text("\n".join(lines[:21]))
    (tmp_path / "b.csv").write_text("\n".join(lines))
    (tmp_path / "notes.csv").write_text("a,b\n1,2\n")
    assert len(find_kestrel_files(tmp_path)) == 2
    data = read_kestrel(tmp_path, utc_offset="UTC", resample=None)
    pd.testing.assert_frame_equal(data, read_kestrel_file(KESTREL_SFM, utc_offset="UTC"))


# RDI ADCP (PD0)

ADCP_DIR = DATA / "adcp"
# Last 28 ensembles of a WinRiver II file, heading crossing north
ADCP_PD0 = ADCP_DIR / "Station_3_0_000_25-01-12.PD0"


def test_read_pd0_profiles():
    pd0 = read_pd0(ADCP_PD0, utc_offset="UTC")
    assert pd0.vel.shape == pd0.corr.shape == pd0.echo.shape == pd0.pgood.shape == (4, 48, 28)
    assert pd0.bt_range.shape == pd0.bt_vel.shape == (4, 28)
    assert pd0.coordinates == "ship"
    assert pd0.beam_angle == 20.0
    assert not pd0.upward
    assert pd0.cell_size == 0.5
    assert pd0.blank == 0.25
    assert pd0.bin_distance[:3] == pytest.approx([0.98, 1.48, 1.98])
    assert pd0.vel[:, 0, 0] == pytest.approx([0.052, -0.124, 0.025, -0.178])
    assert list(pd0.corr[:, 0, 0]) == [114, 158, 130, 101]
    assert list(pd0.echo[:, 0, 0]) == [161, 174, 159, 161]
    # Bad velocities (0x8000) are NaN
    assert 0 < np.isnan(pd0.vel).mean() < 0.2
    assert pd0.time.equals(pd0.ensembles.index)


def test_read_adcp_file_ensembles():
    data = read_adcp_file(ADCP_PD0, utc_offset="UTC")
    assert len(data) == 28
    assert data.index.name == "Datetime"
    # Hundredths of seconds are kept
    assert data.index[0] == utc("2024-12-28 10:00:14.33")
    assert data["Ens"].iloc[0] == 3179
    assert data["Pitch_deg"].iloc[0] == pytest.approx(4.94)
    assert data["Temp_C"].iloc[0] == pytest.approx(24.12)
    assert data["BTRange1_m"].iloc[0] == pytest.approx(4.35)
    assert data["BTRange_m"].iloc[0] == pytest.approx((4.35 + 4.18 + 4.35 + 4.10) / 4)
    assert data["BTVel1_ms"].iloc[0] == pytest.approx(-0.154)


def test_read_adcp_file_heading_is_unsigned():
    # Headings above 327.67 degrees do not fit a signed 16-bit integer
    heading = read_adcp_file(ADCP_PD0, utc_offset="UTC")["Heading_deg"]
    assert heading.iloc[9] == pytest.approx(1.60)
    assert heading.iloc[10] == pytest.approx(359.73)
    assert heading.between(0, 360).all()


def test_read_adcp_file_needs_offset():
    with pytest.raises(ValueError, match="utc_offset"):
        read_adcp_file(ADCP_PD0)


def test_read_pd0_skips_corrupt_ensembles(tmp_path):
    raw = bytearray(ADCP_PD0.read_bytes())
    size = len(raw) // 28
    raw[size + 100] ^= 0xFF  # second ensemble fails its checksum
    path = tmp_path / "corrupt.PD0"
    path.write_bytes(b"\x00garbage\x7f\x7f" + raw)
    data = read_adcp_file(path, utc_offset="UTC")
    full = read_adcp_file(ADCP_PD0, utc_offset="UTC")
    assert len(data) == 27
    assert data["Ens"].tolist() == [e for i, e in enumerate(full["Ens"]) if i != 1]


def test_read_pd0_no_ensembles(tmp_path):
    path = tmp_path / "empty.PD0"
    path.write_bytes(b"not an adcp file")
    with pytest.raises(ValueError, match="no valid PD0 ensemble"):
        read_pd0(path, utc_offset="UTC")


def test_read_adcp_directory(tmp_path):
    (tmp_path / "Station_3_0").mkdir()
    (tmp_path / "Station_3_0/a.PD0").write_bytes(ADCP_PD0.read_bytes())
    (tmp_path / "Station_3_0/a_GPS.TXT").write_text("$GPGGA,\n")
    assert find_adcp_files(tmp_path) == [tmp_path / "Station_3_0/a.PD0"]
    data = read_adcp(tmp_path, utc_offset="UTC")
    pd.testing.assert_frame_equal(data, read_adcp_file(ADCP_PD0, utc_offset="UTC"))
    assert read_adcp(tmp_path, utc_offset="UTC", resample="10s")["BTRange_m"].notna().all()


IDRONAUT_TXT = DATA / "idronaut/BlueMap001.txt"


def test_salinity_pss78_check_values():
    from aphys_readers import salinity_pss78

    # UNESCO (1983) check values (IPTS-68 temperatures, converted to ITS-90 here)
    assert salinity_pss78(42.914, 15 / 1.00024, 0) == pytest.approx(35.0, abs=1e-4)
    assert salinity_pss78(1.888091 * 42.914, 40 / 1.00024, 10000) == pytest.approx(40.0, abs=1e-4)


def test_read_idronaut_file():
    from aphys_readers import find_idronaut_files, read_idronaut, read_idronaut_file, salinity_pss78

    data = read_idronaut_file(IDRONAUT_TXT, utc_offset="UTC")
    assert {"Depth_m", "Press_dbar", "Temp_C", "Cond_mScm", "SpCond_mScm", "Sal_psu", "DO_pctsat", "DO_mgL"} <= set(data.columns)
    assert data.index[0] == utc("2026-01-29 10:20:52.5")
    assert data["Cast"].iloc[0] == "BlueMap001"
    assert data["Sal_psu"].iloc[0] == pytest.approx(34.13)
    # The instrument's salinity is PSS-78
    in_water = data["Cond_mScm"] > 1
    computed = salinity_pss78(data["Cond_mScm"], data["Temp_C"], data["Press_dbar"])[in_water]
    assert (computed - data.loc[in_water, "Sal_psu"]).abs().max() < 0.02
    with pytest.raises(ValueError, match="utc_offset"):
        read_idronaut_file(IDRONAUT_TXT)
    assert find_idronaut_files(DATA / "idronaut") == [IDRONAUT_TXT]
    assert len(read_idronaut(DATA / "idronaut", utc_offset="UTC")) == len(data)


def test_read_seabird_computes_salinity_when_missing():
    data = read_seabird_file(SEABIRD_CNV, utc_offset="UTC")
    assert "Sal_psu" in data
    assert data["Sal_psu"].between(0, 1).all()  # lake water


def test_sigma_t_check_values():
    from aphys_readers import sigma_t

    # UNESCO (1981) check values of the one-atmosphere density (IPTS-68 temperatures)
    assert sigma_t(0, 5 / 1.00024) == pytest.approx(999.96675 - 1000, abs=1e-5)
    assert sigma_t(35, 5 / 1.00024) == pytest.approx(1027.67547 - 1000, abs=1e-5)
    assert sigma_t(35, 25 / 1.00024) == pytest.approx(1023.34306 - 1000, abs=1e-5)


def test_read_campbell_file_averages_and_samples(tmp_path):
    # CR300 program logging 1-min averages and wind samples (Mauritius_Atmos41):
    # the averages get the standard names, the samples smp ones
    lines = [
        '"TOA5","CR300Series","CR300","10041","CR300.Std.07.00","CPU:Mauritius_Atmos41.CR300","11092","ATMOS41_Table"',
        '"TIMESTAMP","RECORD","Solar_Avg","AirTemp_Avg","AtmPressure_Avg","Vapor_Pressure_Avg","WindDirection_Avg",'
        '"WindSpeed_Avg","WindSpeed","WindDirection","Precipitation_Tot","GustWindSpeed_Tot","batt_volt_Min"',
        '"TS","RN","W/m^2","DegC","kPa","kPa","degrees","m/s","m/s","degrees","mm","m/s",""',
        '"","","Avg","Avg","Avg","Avg","Avg","Avg","Smp","Smp","Tot","Tot","Min"',
        '"2024-01-14 10:00:00",7,512,27.1,101.4,2.1,233.5,1.5,1.4,230,0,2.2,12.7',
    ]
    path = tmp_path / "ATMOS41_Table.dat"
    path.write_text("\n".join(lines) + "\n")
    data = read_campbell_file(path, utc_offset="UTC")
    assert list(data.columns) == [
        "Record", "SWin_Wm2", "Tair_C", "Press_kPa", "VapPress_kPa", "WD_deg",
        "WS_ms", "WSsmp_ms", "WDsmp_deg", "Precip_mm", "Gust_ms", "Battery_V",
    ]
    assert data["WS_ms"].iloc[0] == 1.5
    assert data["WSsmp_ms"].iloc[0] == 1.4
