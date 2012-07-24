import re
import datetime

from ... import fns
from ... import LOG
from ... import config
from ...model import datafile
from .. import woce


def read(self, handle):
    """ How to read a Bottle Exchange file. """
    # Read identifier and stamp
    stamp = re.compile('BOTTLE,(\d{8}\w+)')
    m = stamp.match(handle.readline())
    if m:
        self.globals['stamp'] = m.group(1)
    else:
        raise ValueError(("Expected identifier line with stamp "
                          "(e.g. BOTTLE,YYYYMMDDdivINSwho)"))
    # Read comments
    l = handle.readline()
    headers = []
    while l and l.startswith('#'):
        # It's possible for files to come in with unicode.
        headers.append(l.decode('raw_unicode_escape'))
        l = handle.readline()
    self.globals['header'] = u''.join(headers)

    # Read columns and units
    columns = [x.strip() for x in l.strip().split(',')]
    units = [x.strip() for x in handle.readline().strip().split(',')]
    
    # Check columns and units to match length
    if len(columns) is not len(units):
        raise ValueError(("Expected as many columns as units in file. "
                          "Found %d columns and %d units.") % (len(columns),
                                                               len(units)))

    # Check for unique identifer
    identifier = []
    if 'EXPOCODE' in columns and \
       'STNNBR' in columns and \
       'CASTNO' in columns:
        identifier = ['STNNBR', 'CASTNO']
        if 'SAMPNO' in columns:
            identifier.append('SAMPNO')
            if 'BTLNBR' in columns:
                identifier.append('BTLNBR')
        elif 'BTLNBR' in columns:
            identifier.append('BTLNBR')
        else:
            raise ValueError(
                ("No unique identifer found for file. "
                 "(STNNBR,CASTNO,SAMPNO,BTLNBR),"
                 "(STNNBR,CASTNO,SAMPNO),"
                 "(STNNBR,CASTNO,BTLNBR)"))

    self.create_columns(columns, units)

    # Read data
    l = handle.readline().strip()
    while l:
        if l.startswith('END_DATA'): break
        values = l.split(',')
        
        # Check columns and values to match length
        if len(columns) is not len(values):
            raise ValueError(("Expected as many columns as values in file. "
                              "Found %d columns and %d values at "
                              "data line %d") % (len(columns), len(values),
                                                len(self) + 1))

        # TODO check if parameter exists but no flag & vice versa

        for column, raw in zip(columns, values):
            value = raw.strip()
            if fns.out_of_band(value):
                value = None
            try:
                value = float(value)
            except:
                pass
            if column.endswith('_FLAG_W'):
                try:
                    self[column[:-7]].flags_woce.append(int(value))
                except KeyError:
                    LOG.warn(
                        ("Flag WOCE column exists for parameter %s but "
                         "parameter column does not exist.") % column[:-7])
            elif column.endswith('_FLAG_I'):
                try:
                    self[column[:-7]].flags_igoss.append(int(value))
                except KeyError:
                    LOG.warn(
                        ("Flag IGOSS column exists for parameter %s but "
                         "parameter column does not exist.") % column[:-7])
            else:
                self[column].append(value)
        l = handle.readline().strip()

    # Format all data to be what it is
    try:
        self['LATITUDE'].values = map(float, self['LATITUDE'].values)
    except KeyError:
        pass
    try:
        self['LONGITUDE'].values = map(float, self['LONGITUDE'].values)
    except KeyError:
        pass
    try:
        self['DATE']
    except KeyError:
        self['DATE'] = datafile.Column('DATE')
        self['DATE'].values = [None] * len(self)
    try:
        self['TIME']
    except KeyError:
        self['TIME'] = datafile.Column('TIME')
        self['TIME'].values = [None] * len(self)

    woce.fuse_datetime(self)

    self.check_and_replace_parameters()


def write(self, handle):
    """ How to write a Bottle Exchange file. """
    if self.globals['stamp']:
        handle.write('BOTTLE,%s\n' % self.globals['stamp'])
    else:
        LOG.warning("No stamp given. Using current user's stamp.")
        stamp = config.stamp()
        handle.write('BOTTLE,%s\n' % stamp)
    if self.globals['header']:
        handle.write('# Original header:\n')
        handle.write(self.globals['header'])

    woce.split_datetime(self)

    # Convert all float stnnbr, castno, sampno, btlnbr to ints
    def if_float_then_int(x):
        if type(x) is float:
            return int(x)
        return x

    self['STNNBR'].values = map(if_float_then_int, self['STNNBR'].values)
    self['CASTNO'].values = map(if_float_then_int, self['CASTNO'].values)
    self['SAMPNO'].values = map(if_float_then_int, self['SAMPNO'].values)
    self['BTLNBR'].values = map(if_float_then_int, self['BTLNBR'].values)
    self.check_and_replace_parameters()

    columns = self.sorted_columns()
    flagged_parameter_names = []
    flagged_units = []
    flagged_format_parameter_values = []

    for c in columns:
        param = c.parameter
        flagged_parameter_names.append(param.mnemonic_woce())
        flagged_units.append(param.units.mnemonic if param.units and \
            param.units.mnemonic else '')
        flagged_format_parameter_values.append(
            [param.format, param, c.values])
        if c.is_flagged_woce():
            flagged_parameter_names.append(param.mnemonic_woce() + '_FLAG_W')
            flagged_units.append('')
            flagged_format_parameter_values.append(
                ['%1d', param, c.flags_woce])
        if c.is_flagged_igoss():
            flagged_parameter_names.append(param.mnemonic_woce() + '_FLAG_I')
            flagged_units.append('')
            flagged_format_parameter_values.append(
                ['%1d', param, c.flags_igoss])

    handle.write(','.join(flagged_parameter_names))
    handle.write('\n')
    handle.write(','.join(flagged_units))
    handle.write('\n')

    for i in range(len(self)):
        values = []
        for format_str, param, col in flagged_format_parameter_values:
            value = col[i]
            try:
                if value is not None:
                    values.append(format_str % value)
                else:
                    values.append(format_str % woce.FILL_VALUE)
            except Exception, e:
                LOG.warn(
                    u'Could not format %r (column %r row %d) with %r' % (
                    value, param, i, format_str))
                values.append(value)
        handle.write(','.join(values))
        handle.write('\n')

    handle.write('END_DATA\n')
