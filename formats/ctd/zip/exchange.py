"""libcchdo.formats.ctd.zip.exchange"""

import StringIO
import zipfile
import datetime

import libcchdo
import libcchdo.model.datafile
import libcchdo.formats.ctd.exchange as ctdex


def read(self, handle):
    """How to read CTD Exchange files from a Zip."""
    zip = zipfile.ZipFile(handle, 'r')
    for file in zip.namelist():
        if '.csv' not in file: continue
        tempstream = StringIO.StringIO(zip.read(file))
        tempstream.name = file
        ctdfile = libcchdo.model.datafile.DataFile()
        ctdex.read(ctdfile, tempstream)
        self.files.append(ctdfile)
        tempstream.close()
    zip.close()


def write(self, handle):
    """How to write CTD Exchange files to a Zip."""
    zip = zipfile.ZipFile(handle, 'w')
    for file in self.files:
        tempstream = StringIO.StringIO()
        ctdex.write(file, tempstream)

        station = int(file.globals['STNNBR'].strip())
        cast = int(file.globals['CASTNO'].strip())
        info = zipfile.ZipInfo('%s_%05d_%05d_ct1.csv' % \
                       (file.globals['EXPOCODE'], station, cast))
        dt = datetime.datetime.now()
        info.date_time = (dt.year, dt.month, dt.day,
                          dt.hour, dt.minute, dt.second)
        info.external_attr = 0644 << 16L

        zip.writestr(info, tempstream.getvalue())
        tempstream.close()
    zip.close()
