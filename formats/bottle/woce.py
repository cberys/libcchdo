'''libcchdo.bottle.woce'''

import datetime

import libcchdo
import libcchdo.formats.woce
import re


def read(self, handle):
    '''How to read a Bottle WOCE file.'''
    # Read Woce Bottle header
    try:
        stamp_line = handle.readline()
        parameters_line = handle.readline()
        units_line = handle.readline()
        asterisk_line = handle.readline()
        self.header+='\n'.join([stamp_line, parameters_line,
                                units_line, asterisk_line])
    except Exception, e:
        raise ValueError('Malformed WOCE header in WOCE Bottle file: %s' % e)
    # Get stamp
    stamp = re.compile('EXPOCODE\s*([\w/]+)\s*WHP.?ID\s*([\w/]+(,[\w/]+)*)\s*CRUISE DATES\s*(\d{6}) TO (\d{6})\s*(\d{8}\w+)')
    m = stamp.match(stamp_line)
    if m:
        self.globals['EXPOCODE'] = m.group(1)
        self.globals['SECT_ID'] = libcchdo.strip_all(m.group(2).split(','))
        self.globals['_BEGIN_DATE'] = m.group(4)
        self.globals['_END_DATE'] = m.group(5)
        self.stamp = m.groups()[-1] # XXX
    else:
        raise ValueError(("Expected ExpoCode, SectIDs, dates, and a stamp. "
                          "Invalid WOCE record 1."))
    # Validate the parameter line
    if 'STNNBR' not in parameters_line or 'CASTNO' not in parameters_line:
        raise ValueError('Expected STNNBR and CASTNO in parameters record')
    self.read_WOCE_data(handle, parameters_line, units_line, asterisk_line)
    try:
        self.columns['DATE']
    except KeyError:
        self.columns['DATE'] = libcchdo.Column('DATE')
        self.columns['DATE'].values = [None] * len(self) # XXX
    try:
        self.columns['TIME']
    except KeyError:
        self.columns['TIME'] = libcchdo.Column('TIME')
        self.columns['TIME'].values = [None] * len(self)
    self.columns['_DATETIME'] = libcchdo.Column('_DATETIME')
    for d,t in zip(self.columns['DATE'].values,
                   self.columns['TIME'].values):
        self.columns['_DATETIME'].append(
            libcchdo.formats.woce.strptime_woce_date_time(d, t))
    del self.columns['DATE']
    del self.columns['TIME']


def write(self, handle):
    '''How to write a Bottle WOCE file.'''

    #datetimes = self.columns["_DATETIME"].values[:]
    #BEGIN_DATE = 0
    #END_DATE = 0
    #if any(datetimes):
    #    usable_datetimes = filter(None, datetimes)
    #    BEGIN_DATE = min(usable_datetimes)
    #    END_DATE = max(usable_datetimes)
    #del self.columns["_DATETIME"]

    #handle.write("EXPOCODE %-s WHP-ID %-s CRUISE DATES %06d TO %06d %-s\n" %
    #        (self.globals["EXPOCODE"],
    #         self.globals["SECT_ID"][0],
    #         BEGIN_DATE,
    #         END_DATE,
    #         self.stamp))
    #self.write_WOCE_data(handle)
    return NotImplementedError("Not to be used, nitwit!")
