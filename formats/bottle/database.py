"""libcchdo.bottle.database

This writer expects the database to be using a schema like so:

cruises: expocode, etc...
casts: id, expocode, station, cast
cast_bottle_metadata: cast_id, latitude, longitude, depth
ctds: cast_id, latitude, longitude, depth, datetime, instr_id
bottles: id, cast_id, sample, bottle, datetime, flag_woce, flag_igoss
data_bottles: bottle_id, parameter_id, value, flag_woce, flag_igoss
data_ctds: ctd_id, parameter_id, value, flag_woce, flag_igoss
"""

from sys import path
path.insert(0, '/'.join(path[0].split('/')[:-1]))

import db.connect # cchdo_data()
from format import format

class database(format):
    #def read(self):
    def write(self):
        print self.datafile.to_hash()
