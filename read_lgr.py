import io
import logging
import os
import zipfile
import zipfile as zf
from datetime import datetime

import chardet
import pandas as pd


def read_lgr(unzip_path):
    """Reading LGR file.

    Parameters
    ----------
    unzip_path

    """
    logging.info("Reading LGR data")

    data = []
    for alldata in os.listdir(unzip_path):
        allfiles = os.path.join(unzip_path, alldata)
        ## Searching for YB AtmGHG or atmGHG folder
        lgrfolderdata = [
            x
            for x in os.listdir(allfiles)
            if any(s in x for s in ("YB", "AtmGHG", "atmGHG"))
        ]
        try:
            lgrfolderdata = lgrfolderdata[0]
        except IndexError:
            logging.warning("YB or GHG folder does not found in: %s", allfiles)
            continue

        lgrdatadate = os.path.join(allfiles, lgrfolderdata)
        folderdates = os.listdir(lgrdatadate)
        for date in sorted(folderdates):
            datadate = os.path.join(lgrdatadate, date)
            filedate = os.listdir(datadate)
            for lgrfolderdate in filedate:
                readfile = os.path.join(datadate, lgrfolderdate)
                if zipfile.is_zipfile(readfile):
                    ifoot = footer_pos(readfile)
                else:
                    ifoot = 0
                    newfile = "_".join(["fgg", date, "f0000.txt"])
                    readfile = os.path.join(datadate, newfile)

                if os.path.isfile(readfile) and os.path.getsize(readfile) > 0:
                    logging.info("Reading file: %s", readfile)
                    ## Reading column 0 is time, column 7 [CH4]d_ppm and column 9 [CO2]d_ppm
                    rfile = pd.read_csv(
                        readfile,
                        sep=",",
                        header=1,
                        skipfooter=ifoot,
                        skipinitialspace=True,
                        parse_dates=[0],
                        index_col=[0],
                        date_format="%m/%d/%Y %H:%M:%S.%f",
                        usecols=[0, 3, 7, 9, 11, 13, 17, 19],
                        engine="python",
                        names=[
                            "Datetime",
                            "H20_ppm",
                            "CH4d_ppm",
                            "CO2d_ppm",
                            "GasP_torr",
                            "GasT_C",
                            "RD0_us",
                            "RD1_us",
                        ],
                    )
                    data.append(rfile)
                else:
                    continue
    if data:
        data = pd.concat(data)
        data = data.sort_index()
        data = data.resample("1min").mean()
        return data
    else:
        return pd.DataFrame([])


def footer_pos(LGRfile):
    """find footer position"""

    zipf = zipfile.ZipFile(LGRfile)
    f = zipf.namelist()[0]
    content = io.BytesIO(zipf.read(f))
    i = 0
    foot = False
    for line in content.readlines():  # zipf.read(f): #zipf.read(f):
        if line.startswith(b"-----B"):
            ib = i
            foot = True
        i += 1
    if foot:
        ifooter = i - ib
    else:
        ifooter = 0
    return ifooter


def detect_encoding(file_path, sample_size=10000):
    """
    Detects the text encoding of a file using chardet.
    Reads up to `sample_size` bytes from the file.
    """
    with open(file_path, "rb") as f:
        raw_data = f.read(sample_size)
    result = chardet.detect(raw_data)
    return result["encoding"]
