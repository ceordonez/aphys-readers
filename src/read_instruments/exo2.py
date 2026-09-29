import logging
import os

import pandas as pd

from read_instruments.utils import detect_encoding


def read_exo(path_unzipdata):
    """TODO: Docstring for read_exo.

    Parameters
    ----------
    path_unzipdata : TODO

    Returns
    -------
    TODO

    """

    logging.info("Reading EXO data")
    allfiles = os.listdir(path_unzipdata)
    data = []
    #    for datefile in allfiles:
    datefile_path = path_unzipdata  # os.path.join(path_unzipdata, datefile)
    exofiles = [x for x in os.listdir(datefile_path) if ".csv" in x or "xls" in x]
    for exofile in exofiles:
        exofile_path = os.path.join(datefile_path, exofile)
        logging.info("Reading file: %s" % exofile_path)
        if os.path.splitext(exofile_path)[1].lower() != ".csv":
            df = pd.read_excel(exofile_path)
            idx = df[df[df.columns[0]] == "Date (MM/DD/YYYY)"].index.values[0] + 1
            exodata = pd.read_excel(exofile_path, skiprows=idx)
        else:
            idx, encoding, sep = find_firstcol(exofile_path)
            exodata = pd.read_csv(
                exofile_path, sep=sep, skiprows=idx, encoding=encoding
            )
        cols = exodata.columns[:3].values.tolist()
        exodata = exodata.dropna(subset=cols, how="all")
        exodata = exodata.set_index("Date (MM/DD/YYYY)")
        if "Date (MM/DD/YYYY)" in exodata.index.values:
            exodata = exodata.drop("Date (MM/DD/YYYY)", axis=0)
        exodata = exodata.reset_index()
        try:
            exodata["Date (MM/DD/YYYY)"] = pd.to_datetime(
                exodata["Date (MM/DD/YYYY)"], format="%m/%d/%Y"
            )
        except Exception:
            try:
                exodata["Date (MM/DD/YYYY)"] = pd.to_datetime(
                    exodata["Date (MM/DD/YYYY)"], format="%d/%m/%Y"
                )
            except Exception as err:
                raise ValueError(
                    "Unrecognised date format in %s" % exofile_path
                ) from err

        exodata["Datetime"] = pd.to_datetime(
            exodata["Date (MM/DD/YYYY)"].astype(str)
            + " "
            + exodata[cols[1]].astype(str),
            format="%Y-%m-%d %H:%M:%S",
        )
        data.append(exodata)
    if not data:
        logging.warning("No EXO files found in: %s", path_unzipdata)
        return pd.DataFrame([])
    data = pd.concat(data)
    droplist = [
        "Site Name",
        "Date (MM/DD/YYYY)",
        "Time (HH:mm:ss)",
        "Time (HH:MM:SS)",
        "Time (Fract. Sec)",
        "Depth m",
        "Pressure psi a",
        "Vertical Position m",
        "Cable Pwr V",
    ]
    for dropcol in droplist:
        if dropcol in data.columns:
            data = data.drop(
                dropcol,
                axis=1,
            )
    data = data.set_index("Datetime")
    data = data.sort_index()
    data = data.astype(float)
    data = data.resample("1min").mean()
    return data


def find_firstcol(filename):
    encoding = detect_encoding(filename)
    sep = open(filename, encoding=encoding).readline().split("=")[1].rstrip("\n")
    for idx, line in enumerate(open(filename, encoding=encoding).readlines()):
        newline = line.split(sep)
        if "Date (MM/DD/YYYY)" in newline:
            break
    return idx, encoding, sep
