import os
import tempfile
import zipfile

from .... import StringIO
from ....model.datafile import DataFile
from ... import netcdf as nc
from ... import zip as Zip
from .. import netcdf as botnc


def read(self, handle):
    """How to read Bottle NetCDF files from a Zip."""
    zip = Zip.ZeroCommentZipFile(handle, 'r')
    for file in zip.namelist():
        if '.csv' not in file:
            continue
        tempstream = StringIO(zip.read(file))
        file = DataFile()
        botnc.read(file, tempstream)
        self.files.append(file)
        tempstream.close()
    zip.close()


def write(self, handle):
    """How to write Bottle NetCDF files to a Zip.

       The collection should already be split apart based on station cast.
    """
    station_i = 0
    cast_i = 0

    zip = Zip.create(handle)
    for file in self:
        temp = StringIO()
        botnc.write(file, temp)

        # Create a name for the file
        expocode = file.columns['EXPOCODE'][0] or 'UNKNOWN'
        station = file.columns['STNNBR'][0]
        cast = file.columns['CASTNO'][0]
        if station is None:
            station = station_i
            station_i += 1
        if cast is None:
            cast = cast_i
            cast_i += 1
        filename = nc.get_filename(expocode, station, cast)

        zip.writestr(filename, temp.getvalue())
        temp.close()
    zip.close()
