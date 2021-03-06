"""Entry point for libcchdo.

PYTHON_ARGCOMPLETE_OK

This module is the entry point for the hydro utility. To see a list of all
available sub entry points, run 

$ hydro commands

"""
from argparse import ArgumentParser, RawTextHelpFormatter, FileType
from datetime import datetime, date, timedelta
from contextlib import closing, contextmanager
from copy import copy
import sys
import os
import os.path
from traceback import format_exc
from logging import getLogger


log = getLogger(__name__)


import libcchdo
from libcchdo.log import setup as setup_logging
setup_logging()
from libcchdo.formats.formats import all_formats, read_arbitrary
known_formats = all_formats.keys()


class NiceUsageArgumentParser(ArgumentParser):
    """Exactly the same as ArgumentParser except prints nicer usage."""

    def format_usage(self):
        formatter = self._get_formatter()
        formatter.add_usage(self.usage, self._actions,
                            self._mutually_exclusive_groups)
        return formatter.format_help() + _format_parser_tree(self)


class LazyChoices(object):
    """Lazy-load for better startup performance."""
    def lazy(self):
        try:
            return self._lazy
        except AttributeError:
            self._lazy = self.load()
            return self._lazy

    def load(self):
        return []

    def __contains__(self, item):
        return item in self.lazy()

    def __getitem__(self, item):
        return self.lazy()[item]


class NoopFormatter(object):
    """Argparse formatter that does nothing.

    Used to prevent help string formatting error when adding lazy choices.

    add_argument normally calls the formatter on the choices to check the help
    string is formattable. Since the whole point is to lazily load the choices
    when they're really needed, don't actually do the format on add.

    """
    def _format_args(self, *args, **kwargs):
        """No-op for formatting lazy choices."""
        pass


@contextmanager
def lazy_choices(parser):
    """Lazily load choices.

    Use NoopFormatter to prevent choices from being loaded prematurely.

    """
    saved_formatter = parser._get_formatter
    parser._get_formatter = lambda: NoopFormatter()
    yield
    parser._get_formatter = saved_formatter


def _qualify_oceansites_type(args):
    if args.timeseries is None:
        log.warn(
            u'Printing an AMBIGUOUS (read: INVALID) OceanSITES NetCDF Zip')
    else:
        log.info(
            u'Printing a {0} OceanSITES NetCDF Zip'.format(args.timeseries))


def _add_oceansites_arguments(parser, allow_ts_select=True):
    from libcchdo.formats.netcdf_oceansites import (
        OCEANSITES_VERSIONS, OCEANSITES_TIMESERIES)
    with lazy_choices(parser):
        default = OCEANSITES_VERSIONS[-1]
        parser.add_argument(
            '--os-version', choices=OCEANSITES_VERSIONS,
            default=default,
            help='OceanSITES version number (default: {0})'.format(default))
        if allow_ts_select:
            parser.add_argument(
                'timeseries', type=str, nargs='?', default=None,
                choices=OCEANSITES_TIMESERIES,
                help='timeseries location (default: None)')


@contextmanager
def subcommand(superparser, name, func):
    """Add a subcommand to the superparser and yield it."""
    parser = superparser.add_parser(name, description=func.__doc__)
    parser.set_defaults(main=func)
    yield parser


hydro_parser = NiceUsageArgumentParser(
    description='libcchdo tools',
    formatter_class=RawTextHelpFormatter)


hydro_subparsers = hydro_parser.add_subparsers(
    title='subcommands')


check_parser = hydro_subparsers.add_parser(
    'check', help='Format checkers')
check_parsers = check_parser.add_subparsers(
    title='format checkers')


def check_any(args):
    """Check the format for any recognized CCHDO file."""
    import collections
    from libcchdo.formats import woce

    with closing(args.cchdo_file) as in_file:
        try:
            file = read_arbitrary(in_file, args.input_type)
        except Exception, e:
            log.error('Unable to read file {0}:\n{1}'.format(
                args.cchdo_file, format_exc(e)))
            hydro_parser.exit(1) 

    # Water Quality flags that require fill value
    flags_fill = [1, 5, 9]
    not_water_parameters = ['BTLNBR']

    def check_fill_value_has_flag_w_9(df):
        for c in df.columns.values():
            if not c.flags_woce:
                continue
            if c.parameter.name in not_water_parameters:
                continue

            if len(c.flags_woce) != len(c.values):
                log.error(u'column {0} has different number of values ({1}) '
                    'and flags ({2})'.format(
                        c.parameter.name, len(c.values), len(c.flags_woce)))

            for i in range(len(df)):
                value = c[i]
                flag = c.flags_woce[i]
                is_fill_value = value is None
                require_fill_value = flag in flags_fill
                if require_fill_value and not is_fill_value:
                    log.warn(
                        (u'column {0} row {1} has data {2!r} but expected '
                         'fill value for flag {3}: {4!r}').format(
                            c.parameter.name, i, value, flag,
                            woce.WATER_SAMPLE_FLAGS[flag]))
                elif is_fill_value and not require_fill_value:
                    log.warn(
                        (u'column {0} row {1} has unexpected fill value for '
                         'flag {2}: {3!r}').format(
                            c.parameter.name, i, flag,
                            woce.WATER_SAMPLE_FLAGS.get(flag, 'Unknown flag')))

    def check_empty_columns(dfile):
        for c in dfile.columns.values():
            if c.values and c.values[0] is None and c.is_global():
                log.info(u'column {0} is empty (only has fill values)'.format(
                    c.parameter.name))

    def check_blank_values(dfile):
        for c in dfile.columns.values():
            blanks = [(i, True) for i,v in enumerate(c) if v == ""]
            if any(blanks):
                rows = ",".join([str(b[0]) for b in blanks])
                log.error((u'column {0} is has blank values on row(s) {1}'
                        u', conversions may fail').format(
                    c.parameter.name, rows))


    def check_flag_0(dfile):
        """Data should not have flag 0."""
        for col in dfile.columns.values():
            try:
                index = col.flags_woce.index(0)
                log.warn(u'column {0} has flag 0 at row {1}'.format(
                    col.parameter.name, index))
            except ValueError:
                pass

    def check_datafile(df):
        log.info(u'Checking datafile format')
        df.check_and_replace_parameters(convert=False)
        check_fill_value_has_flag_w_9(df)
        check_empty_columns(df)
        check_flag_0(df)
        check_blank_values(df)
        if args.verify_unique:
            check_cols = []
            for col in args.verify_unique:
                check_cols.append(df.columns[col].values)
            check_cols = zip(*check_cols)
            unique_pairs = set(check_cols)
            # the integers can be large and will not satisfy 'is' conditions
            # because they will not be the same object
            if len(check_cols) != len(unique_pairs):
                log.warn("Non unique values for columns ({0})".format(
                                ",".join(args.verify_unique)
                                ))
                non_unique = [x for x, y in
                        collections.Counter(check_cols).items()
                        if y > 1]
                log.warn("The following are duplicated")
                for item in non_unique:
                    item = zip(args.verify_unique, item)
                    log.warn(", ".join(["{0}: {1}".format(*i) for i in item]))

    with closing(args.output) as out_file:
        try:
            for f in file.files:
                check_datafile(f)
        except AttributeError:
            check_datafile(file)


with subcommand(check_parsers, 'any', check_any) as p:
    p.add_argument('-i', '--input-type', choices=known_formats,
        help='force the input file to be read as the specified type')
    p.add_argument(
        'cchdo_file', type=FileType('r'),
         help='any recognized CCHDO file')
    p.add_argument(
        'output', type=FileType('w'), nargs='?', default=sys.stdout,
         help='output file (default: stdout)')
    p.add_argument(
        '--verify_unique', nargs='*',
        help='list of columns used to form unique key')


converter_parser = hydro_subparsers.add_parser(
    'convert', help='Format converters')
converter_parsers = converter_parser.add_subparsers(
    title='format converters')


any_converter_parser = converter_parsers.add_parser(
    'any', help='any format converters')
any_converter_parsers = any_converter_parser.add_subparsers(
    title='any format converters')


def any_to_type(args):
    """Convert any recognized CCHDO file to any valid output type."""
    from libcchdo.formats.common import nav
    from libcchdo.formats import google_wire

    with closing(args.cchdo_file) as in_file:
        file = read_arbitrary(in_file, args.input_type)

    with closing(args.output) as out_file:
        if args.output_type == 'nav':
            nav.write(file, out_file)
        elif args.output_type == 'google_wire':
            google_wire.write(file, out_file, json=args.json)
        elif args.output_type == 'dict':
            out_file.write(str(file.to_dict()))
            out_file.write('\n')
        elif args.output_type == 'str':
            out_file.write(str(file))
            out_file.write('\n')
        else:
            try:
                format = all_formats[args.output_type]
            except (KeyError, ImportError):
                log.error('Unrecognized format %s' % args.output_type)
                return 1
            format.write(file, out_file)


with subcommand(any_converter_parsers, 'type', any_to_type) as p:
    p.add_argument('-t', '--output-type', '--type',
        choices=['str', 'dict', 'google_wire', 'nav', ] + known_formats,
        default='str', help='output types (default: str)')
    p.add_argument('-i', '--input-type', choices=known_formats,
        help='force the input file to be read as the specified type')
    p.add_argument('-j', '--json', action='store_true',
        help='only applies to output type google_wire. Forces the google_wire '
             'output to be valid JSON.')
    p.add_argument(
        'cchdo_file', type=FileType('r'),
         help='any recognized CCHDO file')
    p.add_argument(
        'output', type=FileType('w'), nargs='?', default=sys.stdout,
         help='output file (default: stdout)')


def any_to_kml(args):
    from libcchdo.kml import any_to_kml

    with closing(args.cchdo_file) as in_file:
        file = read_arbitrary(in_file, args.input_type)

    with closing(args.output) as out_file:
        any_to_kml(file, out_file)


with subcommand(any_converter_parsers, 'kml', any_to_kml) as p:
    p.add_argument(
        'cchdo_file', type=FileType('r'),
        help='any recognized CCHDO file')
    p.add_argument('-i', '--input-type', choices=known_formats,
        help='force the input file to be read as the specified type')
    p.add_argument(
        'output', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output file (default: stdout)')


bot_converter_parser = converter_parsers.add_parser(
    'bottle', help='Bottle format converters')
bot_converter_parsers = bot_converter_parser.add_subparsers(
    title='bottle format converters')


def bot_bats_to_bot_ncos(args):
    from libcchdo.model.datafile import DataFileCollection
    from libcchdo.formats.bottle import (
        bermuda_atlantic_time_series_study as botbats)
    from libcchdo.formats.bottle.zip import netcdf_oceansites as botzipncos

    dfc = DataFileCollection()

    with closing(args.botbats) as in_file:
        botbats.read(dfc, in_file)

    args.timeseries = 'BATS'
    _qualify_oceansites_type(args)

    with closing(args.botzipncos) as out_file:
        botzipncos.write(
            dfc, out_file, timeseries=args.timeseries,
            version=args.os_version)


with subcommand(bot_converter_parsers, 'bats_to_ncos',
                bot_bats_to_bot_ncos) as p:
    _add_oceansites_arguments(p, allow_ts_select=False)
    p.add_argument(
        'botbats', type=FileType('r'),
        help='input BOT BATS file')
    p.add_argument(
        'botzipncos', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output BOT netCDF OceanSITES ZIP file')


def bottle_exchange_to_kml(args):
    from libcchdo.model.datafile import DataFile
    import libcchdo.formats.bottle.exchange as botex
    from libcchdo.kml import bottle_exchange_to_kml

    df = DataFile()
    
    with closing(args.input_botex) as in_file:
        botex.read(df, in_file)

    with closing(args.output) as out_file:
        bottle_exchange_to_kml(df, out_file)


with subcommand(bot_converter_parsers, 'exchange_to_kml',
                bottle_exchange_to_kml) as p:
    p.add_argument(
        'input_botex', type=FileType('r'),
        help='input Bottle Exchange file')
    p.add_argument(
        'output', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output file (default: stdout)')


def bottle_exchange_to_parameter_kml(args):
    from libcchdo.model.datafile import DataFile
    import libcchdo.formats.bottle.exchange as botex
    from libcchdo.kml import bottle_exchange_to_parameter_kml

    df = DataFile()
    
    with closing(args.input_botex) as in_file:
        botex.read(df, in_file)

    with closing(args.output) as out_file:
        bottle_exchange_to_parameter_kml(df, out_file)


with subcommand(bot_converter_parsers, 'exchange_to_parameter_kml',
                bottle_exchange_to_parameter_kml) as p:
    p.add_argument(
        'input_botex', type=FileType('r'),
        help='input Bottle Exchange file')
    p.add_argument(
        'output', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output file (default: stdout)')


def btlex_to_btlwoce(args):
    from libcchdo.model.datafile import DataFile
    from libcchdo.config import stamp
    import libcchdo.formats.bottle.exchange as btlex
    import libcchdo.formats.bottle.woce as btlwoce

    dfile = DataFile()

    with closing(args.input_btlex) as in_file:
        btlex.read(dfile, in_file)

    dfile.globals['stamp'] = stamp()

    with closing(args.output_btlwoce) as out_file:
        btlwoce.write(dfile, out_file)


with subcommand(bot_converter_parsers, 'exchange_to_woce',
                btlex_to_btlwoce) as p:
    p.add_argument(
        'input_btlex', type=FileType('r'),
        help='input Bottle Exchange file')
    p.add_argument(
        'output_btlwoce', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output Bottle WOCE file (default: stdout)')


def bottle_exchange_to_bottlezip_netcdf(args):
    from libcchdo.model.datafile import DataFile
    import libcchdo.model.convert.datafile_to_datafilecollection as df2dfc
    import libcchdo.formats.bottle.exchange as botex
    import libcchdo.formats.bottle.zip.netcdf as botzipnc

    df = DataFile()

    with closing(args.input_botex) as in_file:
        botex.read(df, in_file)

    with closing(args.output_botzipnc) as out_file:
        botzipnc.write(df2dfc.split_on_cast(df), out_file)


with subcommand(bot_converter_parsers, 'exchange_to_zip_netcdf',
                bottle_exchange_to_bottlezip_netcdf) as p:
    p.add_argument(
        'input_botex', type=FileType('r'),
        help='input Bottle Exchange file')
    p.add_argument(
        'output_botzipnc', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output Bottle ZIP NetCDF file (default: stdout)')


def bottle_woce_and_summary_woce_to_bottle_exchange(args):
    from libcchdo.model.datafile import DataFile, SummaryFile
    from libcchdo.formats import woce
    import libcchdo.formats.summary.woce as sumwoce
    import libcchdo.formats.bottle.woce as botwoce
    import libcchdo.formats.bottle.exchange as botex

    bottlefile = DataFile()
    sumfile = SummaryFile()

    with closing(args.botwoce) as in_file:
        botwoce.read(bottlefile, in_file)

    with closing(args.sumwoce) as in_file:
        sumwoce.read(sumfile, in_file)

    woce.combine(bottlefile, sumfile)

    with closing(args.botex) as out_file:
        botex.write(bottlefile, out_file)


with subcommand(bot_converter_parsers, 'woce_and_summary_woce_to_exchange',
                bottle_woce_and_summary_woce_to_bottle_exchange) as p:
    p.add_argument(
        'botwoce', type=FileType('r'),
        help='input Bottle WOCE file')
    p.add_argument(
        'sumwoce', type=FileType('r'),
        help='input Summary WOCE file')
    p.add_argument(
        'botex', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output Bottle Exchange file')


ctd_converter_parser = converter_parsers.add_parser(
    'ctd', help='CTD format converters')
ctd_converter_parsers = ctd_converter_parser.add_subparsers(
    title='CTD format converters')


def ctd_bats_to_ctd_exchange(args):
    from libcchdo.model.datafile import DataFile
    import libcchdo.formats.ctd.exchange as ctdex
    import libcchdo.formats.ctd.bermuda_atlantic_time_series_study as ctd_bats

    df = DataFile()

    with closing(args.ctdbats) as in_file:
        ctd_bats.read(df, in_file)

    with closing(args.ctdex) as out_file:
        ctdex.write(df, out_file)


with subcommand(ctd_converter_parsers, 'bats_to_exchange',
                ctd_bats_to_ctd_exchange) as p:
    p.add_argument(
        'ctdbats', type=FileType('r'),
        help='input CTD BATS file')
    p.add_argument(
        'ctdex', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output CTD Exchange file')


def ctd_exchange_to_ctd_netcdf(args):
    from libcchdo.model.datafile import DataFile
    import libcchdo.formats.ctd.exchange as ctdex
    import libcchdo.formats.ctd.netcdf as ctdnc

    df = DataFile()

    with closing(args.ctdex) as in_file:
        ctdex.read(df, in_file)

    with closing(args.ctdnc) as out_file:
        ctdnc.write(df, out_file)


with subcommand(ctd_converter_parsers, 'exchange_to_netcdf',
                ctd_exchange_to_ctd_netcdf) as p:
    p.add_argument(
        'ctdex', type=FileType('r'),
        help='input CTD Exchange file')
    p.add_argument(
        'ctdnc', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output CTD NetCDF file')


def ctd_pangea_to_ctdzipex(args):
    """Convert CTD Pangea file to CTD ZIP Exchange."""
    from libcchdo.formats.ctd import polarstern as ctdpangea
    from libcchdo.formats.ctd.zip import exchange as ctdzipex
    from libcchdo.model.datafile import DataFile

    dfile = DataFile()
    with closing(args.ctd_pangea) as in_file:
        ctdpangea.read(dfile, in_file)

    dfc = ctdpangea.split(dfile, args.expocode)

    with closing(args.ctdzip_exchange) as ooo:
        ctdzipex.write(dfc, ooo)


with subcommand(ctd_converter_parsers, 'pangea_to_ctdzipex',
                ctd_pangea_to_ctdzipex) as p:
    p.add_argument(
        'ctd_pangea', type=FileType('r'), 
        help='input CTD in Pangea format')
    p.add_argument(
        'expocode', 
        help='Expocode for CTD files')
    p.add_argument(
        'ctdzip_exchange', type=FileType('wb'), nargs='?',
        default=sys.stdout,
        help='output CTD ZIP Exchange file')


def ctd_polarstern_to_ctd_exchange(args):
    import sqlite3
    from libcchdo.tools import ctd_polarstern_to_ctd_exchange

    try:
        db = sqlite3.connect(args.database_file)
    except:
        log.error(u"{0} is not a SQLite3 database.".format(args.database_file))
        return 1

    with closing(db) as db:
        ctd_polarstern_to_ctd_exchange(args, db)


with subcommand(ctd_converter_parsers, 'polarstern_to_exchange',
                ctd_polarstern_to_ctd_exchange) as p:
    p.add_argument(
        '--commit-to-file', type=bool, default=False,
        help='Write to a file')
    p.add_argument(
        'database_file', type=str,
        help='SQLite3 database containing PolarStern metadata (previously '
             'extracted)')
    p.add_argument(
        'files', type=str, nargs='+',
        help='The PolarStern data file(s) (*.tab -> *.tab.txt)')
    p.add_argument(
        'ctdex', type=FileType('wb'), nargs='?',
        default=sys.stdout,
        help='output CTD Exchange file')


def ctd_sbe_to_ctd_exchange(args):
    """Convert raw ascii seabird ctd files to ctd exchange or ctd zip exchange.

    The channel specifiers use an index number rather than a name because of the
    posibility for channels to have identical names. All calculated parameters
    and non CCHDO recognized parameters (e.g. PAR) are ignored.

    """
    from libcchdo.tools import sbe_to_ctd_exchange

    sbe_to_ctd_exchange(args)


with subcommand(ctd_converter_parsers, 'sbe_to_exchange',
                ctd_sbe_to_ctd_exchange) as p:
    p.add_argument(
        'files', type=file, nargs='+',
        help='File or list of files that will be converted to exchange format, if '
            'a single file is given, a flat exchange file will be output, if more '
            'than one is given, a ctd zip will be output')
    p.add_argument(
        '-s', '--salt',
        help='in the case of multiple salinity channels, the channel may be '
            'chosen by index')
    p.add_argument(
        '-t', '--temp',
        help='In the case of multiple temperature channels, the channel may be '
            'chosen by index')
    p.add_argument(
        '-o', '--output',
        help='name of output file, _ct1.[csv, zip] will be added automatically, '
            'if not speified will default to standard out.')


def sbe_asc_to_ctd_exchange(args):
    """Convert the SeaBird asc ASCII interchange format to ctd exchange

    This format is not the cnv ASCII format which contains raw headers.

    """
    from libcchdo.tools import sbe_asc_to_ctd_exchange

    sbe_asc_to_ctd_exchange(args)


with subcommand(ctd_converter_parsers, 'sbe_asc_to_exchange',
                sbe_asc_to_ctd_exchange) as p:
    p.add_argument(
        'files', type=file, nargs='+',
        help='File or list of files that will be converted to exchange '
            'format, if a single file is given, a flat exchange file will be '
            'output, if more than one is given, a ctd zip will be output')
    p.add_argument(
        '-o', '--output',
        help='name of output file, _ct1.[csv, zip] will be added '
            'automatically, if not specified will default to standard out.')
    p.add_argument(
        '-e', '--expo',
        help="Manually enter an expocode if the files do not contain one")


def ctd_netcdf_to_ctd_netcdf_oceansites(args):
    from libcchdo.model.datafile import DataFile
    import libcchdo.formats.ctd.netcdf as ctdnc
    import libcchdo.formats.ctd.netcdf_oceansites as ctdnc_oceansites

    df = DataFile()

    with closing(args.ctdnc) as in_file:
        ctdnc.read(df, in_file)

    _qualify_oceansites_type(args)

    with closing(args.ctdnc_os) as out_file:
        ctdnc_oceansites.write(
            df, out_file, timeseries=args.timeseries, version=args.os_version)


with subcommand(ctd_converter_parsers, 'netcdf_to_netcdf_oceansites',
                ctd_netcdf_to_ctd_netcdf_oceansites) as p:
    _add_oceansites_arguments(p)
    p.add_argument(
        'ctdnc', type=FileType('r'),
        help='input CTD Exchange file')
    p.add_argument(
        'ctdnc_os', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output CTD NetCDF OceanSITES file')


def ctdzip_andrex_to_ctdzip_exchange(args):
    from libcchdo.model.datafile import DataFileCollection
    from libcchdo.formats.ctd.zip import exchange as ctdzipex
    from libcchdo.formats.ctd.zip import netcdf_andrex as ctdzipnc_andrex

    dfc = DataFileCollection()

    with closing(args.ctdzip_andrex) as in_file:
        ctdzipnc_andrex.read(dfc, in_file)
    
    with closing(args.ctdzipex) as out_file:
        ctdzipex.write(dfc, out_file)


with subcommand(ctd_converter_parsers, 'zip_andrex_to_zip_exchange',
                ctdzip_andrex_to_ctdzip_exchange) as p:
    p.add_argument(
        'ctdzip_andrex', type=FileType('r'),
        help='ANDREX NetCDF tar.gz')
    p.add_argument(
        'ctdzipex', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output CTD ZIP Exchange file')


def ctdzip_exchange_to_ctdzip_netcdf(args):
    from libcchdo.model.datafile import DataFileCollection
    import libcchdo.formats.ctd.zip.exchange as ctdzipex
    import libcchdo.formats.ctd.zip.netcdf as ctdzipnc

    dfc = DataFileCollection()
    log.debug(repr(args))

    with closing(args.ctdzipex) as in_file:
        ctdzipex.read(dfc, in_file)

    with closing(args.ctdzipnc) as out_file:
        ctdzipnc.write(dfc, out_file)


with subcommand(ctd_converter_parsers, 'zip_exchange_to_zip_netcdf',
                ctdzip_exchange_to_ctdzip_netcdf) as p:
    p.set_defaults(
        main=ctdzip_exchange_to_ctdzip_netcdf)
    p.add_argument(
        'ctdzipex', type=FileType('r'),
        help='input CTD ZIP Exchange file')
    p.add_argument(
        'ctdzipnc', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output CTD ZIP NetCDF file')


def ctdzip_exchange_to_ctdzip_netcdf_oceansites(args):
    from libcchdo.model.datafile import DataFileCollection
    import libcchdo.formats.ctd.zip.exchange as ctdzipex
    import libcchdo.formats.ctd.zip.netcdf_oceansites as ctdzipnc_oceansites

    dfc = DataFileCollection()
    with closing(args.ctdzipex) as in_file:
        ctdzipex.read(dfc, in_file)
    
    _qualify_oceansites_type(args)

    with closing(args.ctdzipnc_os) as out_file:
        ctdzipnc_oceansites.write(
            dfc, out_file, timeseries=args.timeseries, version=args.os_version)


with subcommand(ctd_converter_parsers, 'zip_exchange_to_zip_netcdf_oceansites',
                ctdzip_exchange_to_ctdzip_netcdf_oceansites) as p:
    _add_oceansites_arguments(p)
    p.add_argument(
        'ctdzipex', type=FileType('r'),
        help='input CTD ZIP Exchange file')
    p.add_argument(
        'ctdzipnc_os', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output CTD ZIP NetCDF OceanSITES file')


def ctdzip_netcdf_to_ctdzip_netcdf_oceansites(args):
    from libcchdo.model.datafile import DataFileCollection
    import libcchdo.formats.ctd.zip.netcdf as ctdzipnc
    import libcchdo.formats.ctd.zip.netcdf_oceansites as ctdzipnc_oceansites

    dfc = DataFileCollection()
    with closing(args.ctdzipnc) as in_file:
        ctdzipnc.read(dfc, in_file)
    
    _qualify_oceansites_type(args)

    with closing(args.ctdzipnc_os) as out_file:
        ctdzipnc_oceansites.write(
            dfc, out_file, timeseries=args.timeseries, version=args.os_version)


with subcommand(ctd_converter_parsers, 'zip_netcdf_to_zip_netcdf_oceansites',
                ctdzip_netcdf_to_ctdzip_netcdf_oceansites) as p:
    _add_oceansites_arguments(p)
    p.add_argument(
        'ctdzipnc', type=FileType('r'),
        help='input CTD ZIP NetCDF file')
    p.add_argument(
        'ctdzipnc_os', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output CTD ZIP NetCDF OceanSITES file')


def ctdzip_woce_and_summary_woce_to_ctdzip_exchange(args):
    from libcchdo.model.datafile import DataFileCollection, SummaryFile
    from libcchdo.formats import woce
    import libcchdo.formats.summary.woce as sumwoce
    import libcchdo.formats.ctd.zip.woce as ctdzipwoce
    import libcchdo.formats.ctd.zip.exchange as ctdzipex

    ctdfiles = DataFileCollection()
    sumfile = SummaryFile()

    with closing(args.ctdzipwoce) as in_file:
        ctdzipwoce.read(ctdfiles, in_file)

    with closing(args.sumwoce) as in_file:
        sumwoce.read(sumfile, in_file)

    for ctdfile in ctdfiles.files:
        woce.combine(ctdfile, sumfile)

    with closing(args.ctdzipex) as out_file:
        ctdzipex.write(ctdfiles, out_file)


with subcommand(ctd_converter_parsers,
                'zip_woce_and_summary_woce_to_zip_exchange',
                ctdzip_woce_and_summary_woce_to_ctdzip_exchange) as p:
    p.add_argument(
        'ctdzipwoce', type=FileType('r'),
        help='input CTD ZIP WOCE file')
    p.add_argument(
        'sumwoce', type=FileType('r'),
        help='input Summary WOCE file')
    p.add_argument(
        'ctdzipex', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output CTD ZIP Exchange file')


sum_converter_parser = converter_parsers.add_parser(
    'summary',
    help='Summary file converters')
sum_converter_parsers = sum_converter_parser.add_subparsers(
    title='Summary file converters')


def summary_hot_to_summary_woce(args):
    """Convert HOT program summary file to WOCE format summary file."""
    from libcchdo.model.datafile import SummaryFile
    import libcchdo.formats.summary.hot as sumhot
    import libcchdo.formats.summary.woce as sumwoce

    sf = SummaryFile()

    with closing(args.input_sumhot) as in_file:
        sumhot.read(sf, in_file)

    with closing(args.output_sumwoce) as out_file:
        sumwoce.write(sf, out_file)


with subcommand(sum_converter_parsers, 'hot_to_woce',
                summary_hot_to_summary_woce) as p:
    p.add_argument(
        'input_sumhot', type=FileType('r'),
        help='input Summary HOT file')
    p.add_argument(
        'output_sumwoce', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output Summary WOCE file (default: stdout)')


to_kml_converter_parser = converter_parsers.add_parser(
    'to_kml',
    help='Convert to KML')
to_kml_converter_parsers = to_kml_converter_parser.add_subparsers(
    title='Convert to KML')


def db_to_kml(args):
    """Dump CCHDO holdings tracks to KML ."""
    from libcchdo.kml import db_to_kml
    with closing(args.output) as out_file:
        db_to_kml(out_file, args.expocode, args.full)


with subcommand(to_kml_converter_parsers, 'db', db_to_kml) as p:
    p.add_argument(
        '--full', type=bool, default=False,
        help='full with dates')
    p.add_argument(
        'expocode', type=str, nargs='?', help='the cruise to plot')
    p.add_argument(
        'output', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output file (default: stdout)')


misc_converter_parser = converter_parsers.add_parser(
    'misc',
    help='Miscellaneous converters')
misc_converter_parsers = misc_converter_parser.add_subparsers(
    title='Miscellaneous converters')


def explore_any(args):
    """Attempt to read any CCHDO file and drop into a REPL."""
    from libcchdo.tools import HistoryConsole

    if len(args.cchdo_files) == 1:
        cchdo_file = args.cchdo_files[0]
        with closing(cchdo_file) as in_file:
            dfile = read_arbitrary(in_file, args.input_type)
        banner = (
            'Exploring {0}. Your data file is available as the variable '
            '"dfile".').format(cchdo_file.name)
    else:
        dfiles = []
        for cfile in args.cchdo_files:
            with closing(cfile) as in_file:
                dfiles.append(read_arbitrary(in_file, args.input_type))
        banner = (
            'Exploring {0}. Your data files are available as the variable '
            '"dfiles".').format([xxx.name for xxx in args.cchdo_files])

    console = HistoryConsole(locals=locals())
    console.interact(banner)


with subcommand(misc_converter_parsers, 'explore_any', explore_any) as p:
    p.add_argument('-i', '--input-type', choices=known_formats,
        help='force the input file to be read as the specified type')
    p.add_argument(
        'cchdo_files', type=FileType('r'), nargs='+',
         help='any recognized CCHDO file')


def matlab_hrp_and_config_to_nc_hrp(args):
    from libcchdo.model.datafile import DataFile, DataFileCollection
    from libcchdo.formats.matlab import hrp2
    from json import loads

    cfg = None
    with closing(args.hrp_cfg) as in_file:
        cfg = in_file.read()
        cfg = loads(cfg)
        hrp2.check_cfg(cfg)

    if cfg['data_type'] in ('HRP', 'HRP2 Oliver Sun'):
        dfile = DataFileCollection()
    else:
        dfile = DataFile()
    with closing(args.matlab_hrp) as in_file:
        hrp2.read(dfile, in_file, cfg=cfg)

    with closing(args.output) as out_file:
        hrp2.write(dfile, out_file, cfg=cfg)


with subcommand(misc_converter_parsers, 'matlab_hrp_and_config_to_nc_hrp',
                matlab_hrp_and_config_to_nc_hrp) as p:
    p.add_argument(
        'matlab_hrp', type=FileType('r'),
        help='input Matlab HRP file')
    p.add_argument(
        'hrp_cfg', type=FileType('r'),
        help='HRP configuration file')
    p.add_argument(
        'output', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output NetCDF HRP file')


def convert_per_litre_to_per_kg(args):
    """Do some common unit conversions."""
    from libcchdo.model.datafile import DataFile, DataFileCollection
    from libcchdo.formats.bottle import exchange as btlex
    from libcchdo.formats.ctd.zip import exchange as ctdzipex
    from libcchdo.tools import convert_per_litre_to_per_kg as cvt

    if args.format_module_name == 'btlex':
        format_module = btlex
        df = DataFile()
    elif args.format_module_name == 'ctdzipex':
        format_module = ctdzipex
        df = DataFileCollection()
    else:
        log.error(u'Unacceptable format name.')
        return

    with closing(args.input) as in_file:
        format_module.read(df, in_file)

    # This was originally a bottle only utility, hence the were whole/aliquot
    # question.
    try:
        cvt(
            df, whole_not_aliquot=args.whole_not_aliquot,
            default_convert=args.default_convert)
    except AttributeError:
        for fff in df.files:
            cvt(fff, whole_not_aliquot=args.whole_not_aliquot,
                default_convert=args.default_convert)

    with closing(args.output) as out_file:
        format_module.write(df, out_file)


with subcommand(misc_converter_parsers, 'per_litre_to_per_kg',
                convert_per_litre_to_per_kg) as p:
    p.add_argument(
        '--whole-not-aliquot', type=bool, default=None,
        help='Whether the oxygen measurements where with the whole bottle or '
             'aliquot')
    p.add_argument(
        '--default-convert', type=bool, default=False,
        help='Whether to ask before converting')
    p.add_argument(
        '--format-module-name', default='btlex', choices=['btlex', 'ctdzipex'],
        help='format to use to read and write')
    p.add_argument(
        'input', type=FileType('r'),
        help='input Exchange file')
    p.add_argument(
        'output', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output Exchange file')


def convert_australian_navy_ctd(args):
    """Convert Australian Navy CTD files.

    Australian Navy and Bureau of Meteorology has data available.
    See Google Groups message [CCHDO:4467].

    """
    from libcchdo.tools import australian_navy_ctd
    australian_navy_ctd(args)


with subcommand(misc_converter_parsers, 'austr_navy',
                convert_australian_navy_ctd) as p:
    p.add_argument(
        'output', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output Zip of CTD Zip Exchange files')


def convert_hly0301(args):
    """Make changes specific to HLY0301 by request from D. Muus."""
    from libcchdo.model.datafile import DataFileCollection
    from libcchdo.formats.ctd.zip import exchange as ctdzipex
    from libcchdo.tools import operate_healy_file

    dfc = DataFileCollection()

    with closing(args.input_file) as in_file:
        ctdzipex.read(dfc, in_file, retain_order=True)

    for f in dfc.files:
        operate_healy_file(f)

    with closing(args.output) as out_file:
        ctdzipex.write(dfc, out_file)


with subcommand(misc_converter_parsers, 'hly0301', convert_hly0301) as p:
    p.add_argument(
        'input_file', type=FileType('r'),
        help='input Exchange file')
    p.add_argument(
        'output', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output CTD Zip Exchange file')


def convert_bonus_goodhope(args):
    """Make changes specific to Bonus Goodhope."""
    from libcchdo.model.datafile import DataFileCollection
    from libcchdo.formats.ctd.zip import ecp as ecptar
    from libcchdo.formats.ctd.zip import exchange as ctdzipex

    dfc = DataFileCollection()
    with closing(args.input) as fff:
        ecptar.read(dfc, fff)
    
    for fff in dfc.files:
        fff.globals['EXPOCODE'] = '35MF20080207'
        del fff.columns['DEPTH']
        del fff.columns['GAMMA']
    
    ctdzipex.write(dfc, args.output)


with subcommand(misc_converter_parsers, 'bonus_goodhope',
                convert_bonus_goodhope) as p:
    p.add_argument(
        'input', type=FileType('r'),
        help='input ECP tar')
    p.add_argument(
        'output', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output CTD ZIP Exchange file')


merge_parser = hydro_subparsers.add_parser(
    'merge', help='Mergers')
merge_parsers = merge_parser.add_subparsers(title='mergers')


def merge_ctd_bacp_xmiss_and_ctd_exchange(args):
    from libcchdo.model.datafile import DataFile
    import libcchdo.formats.ctd.bacp as ctdbacp
    import libcchdo.formats.ctd.exchange as ctdex
    from libcchdo.merge import merge_ctd_bacp_xmiss_and_ctd_exchange as domerge

    mergefile = DataFile()
    df = DataFile()

    with closing(args.ctd_bacp) as in_file:
        ctdbacp.read(mergefile, in_file)
    with closing(args.in_ctdex) as in_file:
        ctdex.read(df, in_file)

    domerge(df, mergefile)

    with closing(args.out_ctdex) as out_file:
        ctdex.write(df, out_file)


with subcommand(merge_parsers, 'ctd_bacp_xmiss_and_ctd_exchange',
                merge_ctd_bacp_xmiss_and_ctd_exchange) as p:
    p.add_argument(
        'ctd_bacp', type=FileType('r'),
        help='input CTD BACP file')
    p.add_argument(
        'in_ctdex', type=FileType('r'),
        help='input CTD Exchange file')
    p.add_argument(
        'out_ctdex', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output CTD Exchange file')


def merge_ctdzip_bacp_xmiss_and_ctdzipex(args):
    """Merge BACp file into CTD Zip Exchange."""
    from libcchdo.model.datafile import DataFileCollection
    import libcchdo.formats.ctd.zip.bacp as ctdzipbacp
    import libcchdo.formats.ctd.zip.exchange as ctdzipex
    from libcchdo.merge import (
        merge_ctd_bacp_xmiss_and_ctd_exchange as merge, merge_collections)

    bacpfile = DataFileCollection()
    ctdzipexfile = DataFileCollection()

    with closing(args.ctdzip_bacp) as in_file:
        ctdzipbacp.read(bacpfile, in_file)
    with closing(args.in_ctdzipex) as in_file:
        ctdzipex.read(ctdzipexfile, in_file)

    merged_dfc = merge_collections(
        ctdzipexfile, bacpfile, merge, ['STNNBR', 'CASTNO'])

    with closing(args.out_ctdzipex) as out_file:
        ctdzipex.write(ctdzipexfile, out_file)


with subcommand(merge_parsers, 'ctdzip_bacp_xmiss_and_ctdzip_exchange',
                merge_ctdzip_bacp_xmiss_and_ctdzipex) as p:
    p.add_argument(
        'ctdzip_bacp', type=FileType('r'),
        help='input CTD ZIP BACP file')
    p.add_argument(
        'in_ctdzipex', type=FileType('r'),
        help='input CTD ZIP Exchange file')
    p.add_argument(
        'out_ctdzipex', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output CTD ZIP Exchange file')


def _merge_ex_and_ex(args, file_format, key_determiner, collection=False):
    from libcchdo.merge import (
        merge_datafiles, different_columns, map_collections, merge_collections)
    import libcchdo.formats.bottle.exchange as btlex
    from libcchdo.model.datafile import DataFile, DataFileCollection
    from libcchdo.recipes.orderedset import OrderedSet

    if collection:
        origin = DataFileCollection()
        deriv = DataFileCollection()
    else:
        origin = DataFile()
        deriv = DataFile()
    with closing(args.origin) as forigin:
        file_format.read(origin, forigin)
    with closing(args.derivative) as fderiv:
        deriv_name = fderiv.name
        file_format.read(deriv, fderiv)

    if args.guess_key:
        keycols = key_determiner(origin, deriv)
    else:
        keycols = [xxx.strip() for xxx in args.key.split(',')]
    log.info('Merging on keys composed of: {0!r}'.format(keycols))

    if args.parameters_to_merge:
        parameters = args.parameters_to_merge
    else:
        p_different, p_not_in_origin, p_not_in_derivative, p_common = \
            different_columns(origin, deriv, keycols)
        parameters = p_different + p_not_in_origin
        log.info(u'The following parameters in {0} are different'.format(
            deriv_name))
        if args.merge_different:
            log.info(u', '.join(parameters))
        else:
            # Show parameters with differing data
            print u'\n'.join(parameters)
            return

    parameters = list(OrderedSet(parameters) - OrderedSet(keycols))
    if collection:
        def merge(origin, deriv):
            return merge_datafiles(origin, deriv, keycols, parameters)
        dfout = merge_collections(origin, deriv, merge)
    else:
        dfout = merge_datafiles(origin, deriv, keycols, parameters)

    with closing(args.output) as out_file:
        file_format.write(dfout, out_file)


def _add_merge_arguments(p):
    key_group = p.add_mutually_exclusive_group(required=True)
    key_group.add_argument(
        '--guess-key', action='store_true', 
        help='Whether to guess the key on which to merge the files.')
    key_group.add_argument(
        '--key', type=str, 
        help='Comma separated columns to use as the key to merge on.')
    p.add_argument(
        '--merge-different', action='store_true',
        help='Merge all different parameters')
    p.add_argument(
        'origin', type=FileType('r'),
        help='file to merge onto')
    p.add_argument(
        'derivative', type=FileType('r'),
        help='file to update first file with')
    merge_group = p.add_argument_group(title='Merge parameters')
    merge_group.add_argument(
        'parameters_to_merge', type=str, nargs='*', default=[],
        help='parameters to merge')


def merge_btlex_and_btlex(args):
    """Merge Bottle Exchange files by overwriting the first with the second.

    If no parameters to merge are given, show the parameters that have differing
    data.

    """
    from libcchdo.merge import determine_bottle_keys
    import libcchdo.formats.bottle.exchange as btlex
    _merge_ex_and_ex(args, btlex, determine_bottle_keys)


with subcommand(merge_parsers, 'botex_and_botex', merge_btlex_and_btlex) as p:
    p.add_argument(
        '--output', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output Bottle Exchange file')
    _add_merge_arguments(p)


def merge_ctdex_and_ctdex(args):
    """Merge CTD Exchange files by overwriting origin's data with derivative's.

    If no parameters to merge are given, show the parameters that have differing
    data.

    """
    from libcchdo.merge import determine_ctd_keys
    import libcchdo.formats.ctd.exchange as ctdex
    _merge_ex_and_ex(args, ctdex, determine_ctd_keys)


with subcommand(merge_parsers, 'ctdex_and_ctdex', merge_ctdex_and_ctdex) as p:
    p.add_argument(
        '--output', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output CTD Exchange file')
    _add_merge_arguments(p)


def merge_ctdzipex_and_ctdzipex(args):
    """Merge CTD Exchange files by overwriting the first with the second.

    If no parameters to merge are given, show the parameters that have differing
    data.

    """
    from libcchdo.recipes.orderedset import OrderedSet
    from libcchdo.merge import (
        map_collections, determine_ctd_keys)
    import libcchdo.formats.ctd.zip.exchange as ctdzipex

    def key_determiner(origin, deriv):
        dfile_map = map_collections(origin, deriv)
        keycols = OrderedSet()
        for odfile, ddfile, dfkey in dfile_map:
            keycols.add(determine_ctd_keys(odfile, ddfile))

        if not keycols:
            raise ValueError(
                u'Unable to determine the key columns across all CTD files.')
        keycols = keycols.pop()
        return keycols
    _merge_ex_and_ex(args, ctdzipex, key_determiner, collection=True)


with subcommand(merge_parsers, 'ctdzipex_and_ctdzipex',
                merge_ctdzipex_and_ctdzipex) as p:
    p.add_argument(
        '--output', type=FileType('w'), nargs='+', default=sys.stdout,
        help='output CTD ZIP Exchange file')
    _add_merge_arguments(p)



plot_parser = hydro_subparsers.add_parser(
    'plot', help='Plotters')
plot_parsers = plot_parser.add_subparsers(title='plotters')


def plot_etopo(args):
    """Plot the world and, optionally, some points with ETOPO bathymetry.

    Note: It is recommended to use a resolution higher than 5 degrees for north
    polar plots, i.e. use ETOPO2 or ETOPO1.

    # Examples

    # plot of a bottle file in mercator with cberys color map and high
    # resolution etopo data
    $ hydro plot etopo --proj merc --bounds-cylindrical 130 30 150 45 \
        --cmap cberys --width 720 --any-file cruise_hy1.csv \
        --output-filename cruise.png 2

    # large plot of the south pole in grayscale and medium resolution etopo data
    $ hydro plot etopo --proj spstere --cmap gray --width 1024 \
        --output-filename map.png 5

    """
    from libcchdo.plot.etopo import plot, plot_line_dots

    bm = plot(args)
    if args.any_file:
        df = read_arbitrary(args.any_file)
        line, dots = plot_line_dots(
            df['LONGITUDE'].values, df['LATITUDE'].values, bm)

    bm.savefig(args.output_filename)


class LazyChoicesPlotColormaps(LazyChoices):
    """Lazy-load plot etopo for better startup performance."""
    def load(self):
        """lazy load plot.etopo.plot_colormaps."""
        from libcchdo.plot.etopo import colormaps as plot_colormaps
        return plot_colormaps.keys()


def _add_plot_etopo_arguments(p):
    p.add_argument(
        '--no-etopo', action='store_const', const=True,
        help='Do not draw ETOPO')
    p.add_argument(
        'minutes', type=int, nargs='?', default=5, choices=[1, 2, 5, 30, 60], 
        help='The desired resolution of the ETOPO grid data in minutes '
             '(default: 5)')
    p.add_argument(
        '--width', type=int, default=720, choices=[240, 320, 480, 720, 1024],
        help='The desired width in pixels of the resulting plot image '
             '(default: 720)')
    p.add_argument(
        '--fill_continents', type=bool, default=False,
        help='Whether to fill the continent interiors with solid black '
             '(default: False)')
    p.add_argument(
        '--projection', default='merc',
        choices=['merc', 'robin', 'npstere', 'spstere', 'tmerc', ],
        help='The projection of map to use (default: merc)')
    with lazy_choices(p):
        p.add_argument(
            '--cmap', default='cberys',
            choices=LazyChoicesPlotColormaps(),
            help='The colormap to use for the ETOPO data (default: cberys)')
    p.add_argument(
        '--title', type=str, 
        help='A title for the plot')
    p.add_argument(
        '--any-file', type=FileType('r'), nargs='?',
        help='Name of an input file to plot points for')
    p.add_argument(
        '--output-filename', default='etopo.png',
        help='Name of the output file (default: etopo.png)')

    llcrnrlat = -89
    # Chosen so that the date line will be centered
    llcrnrlon = 25
    p.add_argument(
        '--bounds-cylindrical', type=float, nargs=4,
        default=[llcrnrlon, llcrnrlat, 360 + llcrnrlon, -llcrnrlat],
        help='The boundaries of the map as '
             '[llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat]')
    # TODO these options need to be matched with the projection
    p.add_argument(
        '--bounds-elliptical', type=float, nargs=1,
        default=180,
        help='The center meridian of the map lon_0 (default: 180 centers the '
            'Pacific Ocean)')


with subcommand(plot_parsers, 'etopo', plot_etopo) as p:
    _add_plot_etopo_arguments(p)
    plot_etopo_parser = p


def plot_battery(args):
    """Plot a full battery of projections and colormaps.

    Used when matching style to GMT.

    """
    from libcchdo.plot.etopo import plt
    root = 'etopo_battery'
    try:
        os.mkdir(root)
    except OSError:
        pass
    projections = ['merc', 'robin', 'spstere', 'npstere']
    cmaps = ['gray', 'cberys']

    for proj in projections:
        iargs = copy(args)
        iargs.projection = proj
        if proj == 'merc':
            iargs.bounds_cylindrical = [25, -80, 385, 80]
        elif proj == 'spstere':
            iargs.minutes = 5
        elif proj == 'npstere':
            iargs.minutes = 2

        for cmap in cmaps:
            iargs.cmap = cmap
            iargs.output_filename = os.path.join(
                root, '{0}_{1}.png'.format(proj, cmap[0]))
            plot_etopo(iargs)
            plt.clf()

    iargs = copy(args)
    iargs.projection = 'merc'
    iargs.output_filename = os.path.join(root, 'merc_c_small.png')
    iargs.cmap = 'cberys'
    iargs.width = 480
    iargs.bounds_cylindrical = [110, -10, 160, 40]
    iargs.minutes = 2
    plot_etopo(iargs)
    plt.clf()

    iargs = copy(args)
    iargs.projection = 'merc'
    iargs.output_filename = os.path.join(root, 'plot.png')
    iargs.any_file = open('49MR0502_hy1.csv')
    iargs.width = 720
    iargs.bounds_cylindrical = [130, 30, 150, 45]
    iargs.minutes = 2
    plot_etopo(iargs)


with subcommand(plot_parsers, 'battery', plot_battery) as p:
    _add_plot_etopo_arguments(p)


def plot_cruise_json(args):
    """Plot using cruise.json to specify plotting parameters."""
    from json import load as json_load

    with closing(args.cruise_json) as jfile:
        cruise = json_load(jfile)
    if not cruise:
        return

    plot = cruise['plot']
    try:
        args = plot['args']
    except KeyError:
        args = []
    args += [
        u'--any-file=' + plot[u'source'],
        unicode(plot[u'etopo_degrees'])]
    args = plot_etopo_parser.parse_args(args)
    args.title = ' - '.join([plot[u'title'], cruise['cruise']['expocode']])
    args.projection = plot[u'projection']
    args.cmap = plot[u'cmap']
    args.width = plot[u'width']
    try:
        args.output_filename = plot[u'output_filename']
    except KeyError:
        args.output_filename = cruise['cruise']['expocode'] + '_trk.gif'
    try:
        args.bounds_cylindrical = plot[u'bounds']
    except KeyError:
        pass

    plot_etopo(args)


with subcommand(plot_parsers, 'cruise_json', plot_cruise_json) as p:
    p.add_argument(
        'cruise_json', type=FileType('r'), nargs='?',
        default='cruise.json',
         help='Path to cruise.json file. (default: ./cruise.json)')


def plot_goship(args):
    """Plot the GO-SHIP basemap.

    With CCHDO cruises overlaid.

    """
    from libcchdo.db.util import _tracks
    from libcchdo.plot import presets_goship

    color = gmt_color(0x7A, 0xCD, 0xE4)
    color = gmt_color(*[(x - 0x40) for x in [0x7A, 0xCD, 0xE4]])

    args, bm, gmt_style = presets_goship(
        color, args, draft=False)

    def bin_end():
        pass

    def track_points(track, expocode, date_start):
        lons = []
        lats = []
        for coord in track:
            lons.append(coord[0])
            lats.append(coord[1])
        if lons and lats:
            xs, ys = bm(lons, lats)
            dots = bm.scatter(xs, ys, **gmt_style)

    bin_end()
    _tracks(bin_end, track_points)
    bm.savefig(args.output_filename)


with subcommand(plot_parsers, 'goship', plot_goship) as p:
    p.add_argument(
        '--draft', action='store_true',
        help='Draft form is a small version of the plot')
    p.add_argument(
        '--output-filename', default='goship.png',
        help='Name of the output file (default: goship.png)')


def plot_ushydro(args):
    '''Rebuild all the ushydro maps with lines and years
    '''
    from libcchdo.plot.ushydro import genfrom_args
    from libcchdo.util import get_library_abspath
    default = os.path.join(get_library_abspath(), 'resources', 'ushydro.json')
    if args.config:
        f = args.config
    else:
        f = open(default, 'rb')

    if args.config_dump:
        print open(default, 'rb').read()
    else:
        genfrom_args(args, f)


with subcommand(plot_parsers, 'ushydro', plot_ushydro) as p:
    p.add_argument(
            '--config', type=FileType('r'),
            help='Override default config file')
    p.add_argument(
            '--config-dump', 
            action='store_true',
            help='Dump the default configureation to stdout for user editing')
    p.add_argument(
            '--save-dir', default=os.getcwd(),
            help="The directory the maps will be saved in, deaults to cwd",)
    p.add_argument(
            '--html-prefix',
            default="/images/map_images/", help=("Define the location the maps will"
            "exist on the server, this modifies the html output"),)


def plot_data_holdings_around(args):
    """Plot the CCHDO data holdings binned around a year."""
    from libcchdo.plot.etopo import plt, ETOPOBasemap, plot
    from libcchdo.db.util import _tracks

    args.no_etopo = True
    args.fill_continents = True
    args.no_etopo = False
    args.fill_continents = False

    args.minutes = 2
    args.projection = 'eck4'
    args.cmap = 'gray'
    args.title = ''
    args.width = 2048
    args.any_file = None
    args.bounds_elliptical = 200

    around = datetime(args.around, 12, 1)
    
    fig_eck4 = plt.figure(1)
    bm_eck4 = plot(
        args, label_font_size=24,
        draw_graticules_kwargs={'line_width': 1},
        graticule_ticks_kwargs={'parallel_spacing': 30, 'meridian_spacing': 30})

    args.projection = 'npstere'
    args.minutes = 1
    args.bounds_elliptical = 180
    fig_npstere = plt.figure(2)
    bm_npstere = plot(args,
        label_font_size=28,
        draw_graticules_kwargs={'line_width': 1},
        gmt_graticules_kwargs={})

    args.projection = 'spstere'
    fig_spstere = plt.figure(3)
    bm_spstere = plot(args,
        label_font_size=28,
        draw_graticules_kwargs={'line_width': 1},
        gmt_graticules_kwargs={'border_linewidth': 11, 'border_ratio': 0.008})

    gmt_style = copy(ETOPOBasemap.GMT_STYLE_DOTS)
    gmt_style['s'] = 2
    gmt_style['linewidth'] = 0

    colors = ['g', 'b', 'r', None, ]
    colors = colors[::-1]
    sizes = [6, 6, 6, None, ]
    sizes = sizes[::-1]

    def bin_end():
        # change color of dots
        gmt_style['c'] = colors.pop()
        gmt_style['s'] = sizes.pop()
        log.debug(gmt_style)

    def track_points(track, expocode, date_start):
        lons = []
        lats = []
        for coord in track:
            lons.append(coord[0])
            lats.append(coord[1])
        if lons and lats:
            plt.figure(fig_eck4.number)
            xs, ys = bm_eck4(lons, lats)
            dots = bm_eck4.scatter(xs, ys, **gmt_style)

        lons = []
        lats = []
        for coord in track:
            if coord[1] >= 60:
                lons.append(coord[0])
                lats.append(coord[1])
        if lons and lats:
            plt.figure(fig_npstere.number)
            npstere_gmt_style = copy(gmt_style)
            npstere_gmt_style['s'] = npstere_gmt_style['s'] + 12
            xs, ys = bm_npstere(lons, lats)
            dots = bm_npstere.scatter(xs, ys, **npstere_gmt_style)

        lons = []
        lats = []
        for coord in track:
            if coord[1] <= -30:
                lons.append(coord[0])
                lats.append(coord[1])
        if lons and lats:
            plt.figure(fig_spstere.number)
            spstere_gmt_style = copy(gmt_style)
            spstere_gmt_style['s'] = spstere_gmt_style['s'] + 14
            xs, ys = bm_spstere(lons, lats)
            dots = bm_spstere.scatter(xs, ys, **spstere_gmt_style)

    bin_end()
    _tracks(bin_end, track_points, around)

    plt.figure(fig_eck4.number)
    bm_eck4.savefig('data_holdings_around_{0}_eckert4.png'.format(args.around))
    plt.figure(fig_npstere.number)
    bm_npstere.savefig('data_holdings_around_{0}_npstere.png'.format(args.around))
    plt.figure(fig_spstere.number)
    bm_spstere.savefig('data_holdings_around_{0}_spstere.png'.format(args.around))


with subcommand(plot_parsers, 'data_holdings_around',
                plot_data_holdings_around) as p:
    p.add_argument(
        'around', type=int, help='The year to bin around')


def plot_woce_repr(args):
    """Plot WOCE lines with each represented by one or two ideal cruise tracks.

    """
    from libcchdo.plot.tools import plot_woce_representation
    from libcchdo.util import get_library_abspath
    default = os.path.join(
        get_library_abspath(), 'resources', 'woce_repr.csv')
    plot_woce_representation(args, default)


with subcommand(plot_parsers, 'woce_repr',
                plot_woce_repr) as p:
    p.add_argument(
        '--large-dots', action='store_true',
        help='Whether or not to use large dots')
    p.add_argument(
        '--draft', action='store_true',
        help='Draft form is a small version of the plot')
    p.add_argument(
        '--output-filename', default='woce.png',
        help='Name of the output file (default: woce.png)')


misc_parser = hydro_subparsers.add_parser(
    'misc', help='Miscellaneous')
misc_parsers = misc_parser.add_subparsers(title='miscellaneous')


def get_ctdex_name(args):
    """Get correct name of an Exchange CTD file."""
    from libcchdo.model.datafile import DataFile
    from libcchdo.formats.ctd.zip import exchange as ctdzipex

    print ctdzipex.get_ctdex_name(args.input_file)


with subcommand(misc_parsers, 'get_ctdex_name',
                get_ctdex_name) as p:
    p.add_argument(
            'input_file', type=FileType('r'),
            help='input CTD Exchange file')


def rename_ctd_zipfiles(args):
    from zipfile import ZipFile
    from tempfile import SpooledTemporaryFile
    from libcchdo.formats.ctd.zip.exchange import get_ctdex_name

    with closing(args.input_file) as inputctdzip:
        input_zip = ZipFile(inputctdzip, 'r')

        # We must create a new zip and copy the original files in with new
        # names because the python interface does not allow for renaming.
        with ZipFile(args.output_file, 'w') as newzip:
            for fname in input_zip.namelist():
                # Assuming we have enough memory to keep ~4MB in memory
                bytes = input_zip.read(fname)
                with SpooledTemporaryFile() as spooledfile:
                    spooledfile.write(bytes)
                    new_name = get_ctdex_name(spooledfile)
                newzip.writestr(new_name, bytes)


with subcommand(misc_parsers, 'rename_ctd_zipfiles',
                rename_ctd_zipfiles) as p:
    p.add_argument(
            'input_file', type=FileType('r'),
            help='input CTD ZIP Exchange file')
    p.add_argument(
            'output_file', type=FileType('w'), nargs='?', default=sys.stdout,
            help='output CTD ZIP Exchange file (default: stdout)')


def get_bounds(args):
    """Take any readable file and output the bounding box"""
    from libcchdo.model.navcoord import iter_coords, NavCoords, print_bounds

    df = read_arbitrary(args.cchdo_file)
    iter_coords(df, NavCoords, print_bounds)


with subcommand(misc_parsers, "get_bounds", get_bounds) as p:
    p.add_argument('cchdo_file', type=FileType('r'),
            help='any recognized CCHDO file')


def regen_db_cache(args):
    """Regenerate database cache"""
    from libcchdo.db.model import std
    std_session = std.session()
    std._regenerate_database_cache(std_session)
    std_session.commit()


with subcommand(misc_parsers, 'regen_db_cache', regen_db_cache) as p:
    pass


def csv_view(args):
    """Quick view a CSV exchange file."""
    from libcchdo.csv_view import view
    view(args.csv_file)


with subcommand(misc_parsers, 'csv_view', csv_view) as p:
    p.add_argument('csv_file', help='the CSV Exchange file to view')


def db_dump_tracks(args):
    """Dump the track points from the legacy database into a nav file.

    """
    from libcchdo.db.util import tracks
    tracks(args.output_file, args.date_from, args.date_to, args.around)


with subcommand(misc_parsers, 'db_dump_tracks', db_dump_tracks) as p:
    p.add_argument('-a', '--around',
        help='the year to bin around. Takes precedence over date-from and date-to.')
    p.add_argument('-df', '--date-from',
        help='the year to limit from')
    p.add_argument('-dt', '--date-to',
        help='the year to limit to')
    p.add_argument(
        'output_file', type=FileType('w'), nargs='?',
        default=sys.stdout,
        help='output file (default: stdout)')




def canon(args):
    """Rewrite a file with all parameters converted to canon.

    """
    from libcchdo.formats.formats import guess_ftype_dftype_format
    with closing(args.input_file) as in_file:
        _, dfile, format_module = guess_ftype_dftype_format(
            in_file, args.input_type)
        format_module.read(dfile, in_file)

    with closing(args.output_file) as out_file:
        format_module.write(dfile, out_file)


with subcommand(misc_parsers, 'canon', canon) as p:
    p.add_argument('-i', '--input-type',
        choices=known_formats,
        help='force the input file to be read as the specified type')
    p.add_argument(
        'input_file', type=FileType('r'),
        help='input file')
    p.add_argument(
        'output_file', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output (default: stdout)')


def reorder_columns(args):
    """Rewrite a file with columns reordered.

    """
    from libcchdo.formats.formats import guess_ftype_dftype_format
    from libcchdo.fns import uniquify
    with closing(args.input_file) as in_file:
        _, dfile, format_module = guess_ftype_dftype_format(
            in_file, args.input_type)
        format_module.read(dfile, in_file)

    def reorder_columns(dfile):
        missing = set(dfile.parameter_mnemonics_woce()) - set(mnemonics)
        for iii, param in enumerate(mnemonics):
            dfile[param].parameter.display_order = iii - len(mnemonics)
        for param in missing:
            del dfile[param]

    if args.order is not None:
        mnemonics = args.order.split(',')
        try:
            for df in dfile.files:
                reorder_columns(df)
        except AttributeError:
            reorder_columns(dfile)
        with closing(args.output_file) as out_file:
            format_module.write(dfile, out_file)
    else:
        try:
            params = []
            for df in dfile.files:
                params.extend(df.parameter_mnemonics_woce())
            params = uniquify(params)
        except AttributeError:
            params = dfile.parameter_mnemonics_woce()
        print ','.join(params)


with subcommand(misc_parsers, 'reorder_columns', reorder_columns) as p:
    p.add_argument('-i', '--input-type',
        choices=known_formats,
        help='force the input file to be read as the specified type')
    p.add_argument('-o', '--order', default=None,
        help='comma separated list of parameter mnemonics in order they should '
            'appear. If not listed, will not appear. (default: print '
            'column parameter order)')
    p.add_argument(
        'input_file', type=FileType('r'),
        help='input file')
    p.add_argument(
        'output_file', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output (default: stdout)')


def bottle_exchange_canon(args):
    """Rewrite a bottle exchange file with all parameters converted to canon.

    """
    log.critical(u'DEPRECATED use hydro convert misc canon instead')


with subcommand(misc_parsers, 'bottle_exchange_canon',
                bottle_exchange_canon) as p:
    p.add_argument(
        'input_botex', type=FileType('r'),
        help='input Bottle Exchange file')
    p.add_argument(
        'output_botex', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output Bottle Exchange file (default: stdout)')


def collect_into_archive(args):
    from libcchdo.tools import collect_into_archive

    collect_into_archive()


with subcommand(
        misc_parsers, 'collect_into_archive', collect_into_archive) as p:
    pass


def flatten_zip(args):
    """Flattens a ZIP archive that has directories.

    An Exchange ZIP file is not allowed to have directories. This utility will
    take files that exist in subdirectories of a zip and put them at the top
    level.

    """
    from libcchdo.tools import flatten_zip

    with closing(args.input) as infile:
        with closing(args.output) as outfile:
            output = flatten_zip(infile, outfile)


with subcommand(misc_parsers, 'flatten_zip', flatten_zip) as p:
    p.add_argument(
        'input', type=FileType('r'), help='input Zip file')
    p.add_argument(
        'output', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output Zip file (default: stdout)')



def reorder_surface_to_bottom(args):
    """Orders the data rows in a bottle file by pressure and bottle number

    Defaults to non-descending pressure, non-ascending bottle number order.

    """
    from libcchdo.model.datafile import DataFile
    import libcchdo.formats.bottle.exchange as botex

    df = DataFile()

    with closing(args.input_file) as f:
        botex.read(df, f)

    df.reorder_file_pressure(
        args.order_nondesc_pressure, args.order_nondesc_btlnbr)

    with closing(args.output_file) as f:
        botex.write(df, f)


with subcommand(misc_parsers, 'reorder_surface_to_bottom',
                reorder_surface_to_bottom) as p:
    p.add_argument(
        'input_file', type=FileType('r'),
        help='input Bottle Exchange file')
    p.add_argument(
        'output_file', type=FileType('w'), nargs='?', default=sys.stdout,
        help='output Bottle Exchange file')
    p.add_argument(
        '--order-nondesc-pressure', type=bool, nargs='?', default=True,
        help='Order by non-descending pressure (default: True)')
    p.add_argument(
        '--order-nondesc-btlnbr', type=bool, nargs='?', default=False,
        help='Order by non-descending bottle number (default: False)')


def shell(args):
    """Load libcchdo and drop into a REPL."""
    import libcchdo
    from libcchdo.tools import HistoryConsole
    console = HistoryConsole(locals=locals())
    console.interact('libcchdo')


with subcommand(hydro_subparsers, 'shell', shell) as p:
    pass


def edit_cfg(args):
    """Edit the most precedent configuration file."""
    from subprocess import call as subproc_call

    from libcchdo.fns import get_editor
    from libcchdo.config import get_config_path
    cfg_path = get_config_path()
    subproc_call([get_editor(), cfg_path])


# XXX HACK don't know why it doesn't work without the with statement
with subcommand(hydro_subparsers, 'edit_cfg', edit_cfg) as p:
    pass


def formats(args):
    """List file formats that are recognized.

    """
    from libcchdo.formats.formats import all_formats, file_extensions

    for sname, module in all_formats.items():
        print sname, '\t', module

    print

    for sname, exts in file_extensions.items():
        print sname, '\t', repr(exts)


with subcommand(hydro_subparsers, 'formats', formats) as p:
    pass


hydro_parser.add_argument(
    '--version', action='version',
    version='{0} {1}'.format(
        os.path.basename(sys.argv[0]), libcchdo.__version__))


def fix_perms(args):
    """Fix permissions."""
    import os
    from pwd import getpwnam

    if os.getuid() != 0:
        log.error(
            u'Please run with elevated privileges to change permissions.')
        return

    # drop privileges
    userpwd = getpwnam(os.getlogin())
    esc_gid = os.getegid()
    esc_uid = os.geteuid()
    low_gid = userpwd.pw_gid
    low_uid = userpwd.pw_uid
    os.setegid(low_gid)
    os.seteuid(low_uid)

    # Make all cruise directory level files 664 and dirs 775. Queue should be 777
    # everything in an original directory should be 660 and 770

    path = os.getcwd()

    for dirpath, dirnames, fnames in os.walk(path):
        fperms = 0664
        dperms = 0775

        working = 'original' in os.path.split(dirpath)
        if working:
            fperms = 0660
            dperms = 0770

        queue = 'Queue' in os.path.split(dirpath)
        if queue:
            dperms = 0777

        os.seteuid(esc_uid)
        os.setegid(esc_gid)
        os.chmod(path, dperms)
        os.setegid(low_gid)
        os.seteuid(low_uid)

        for fname in fnames:
            os.seteuid(esc_uid)
            os.setegid(esc_gid)
            os.chmod(os.path.join(dirpath, fname), fperms)
            os.setegid(low_gid)
            os.seteuid(low_uid)


with subcommand(hydro_subparsers, 'fix_permissions', fix_perms) as p:
    pass


def env(args):
    """Get or change libcchdo environment.

    """
    from libcchdo.config import (
        ENVIRONMENT_ENV_VARIABLE, get_libenv, get_merger_name, get_merger_email,
        stamp
        )
    if args.environment:
        print 'export {0}={1}'.format(
            ENVIRONMENT_ENV_VARIABLE, args.environment)
    else:
        print get_libenv()
        print get_merger_name()
        print get_merger_email()
        print stamp()


with subcommand(hydro_subparsers, 'env', env) as p:
    p.add_argument(
        'environment', nargs='?', 
        help='the environment to set')


def _subparsers(parser):
    """Get the subparsers for an ArgumentParser."""
    try:
        group_actions = parser._subparsers._group_actions
        subparsers = []
        for ga in group_actions:
            subparsers.extend(ga.choices.values())
        return subparsers
    except AttributeError:
        return []


def _format_parser_tree(parser, level=0):
    """Recursively print the parser tree with descriptions."""
    from libcchdo.ui import termcolor

    subparsers = _subparsers(parser)
    try:
        prog_name = parser.prog.split()[-1]
    except IndexError:
        prog_name = parser.prog
    try:
        description = parser.description.split('\n')[0]
    except AttributeError:
        description = ''

    if subparsers:
        color = termcolor('white', True)
    else:
        color = termcolor('green')

    string = ''
    lead_str = ''.join(['  ' * level, color, prog_name, termcolor('reset')])
    if description:
        spacing = ' ' * abs(len(lead_str) - 40)
        string += ''.join([lead_str, spacing, description]) + '\n'
    else:
        string += lead_str + '\n'
    for sp in subparsers:
        string += _format_parser_tree(sp, level + 1)
    return string


try:
    from argcomplete import autocomplete
    autocomplete(hydro_parser)
except ImportError:
    pass
    

def main():
    """The main program that wraps all subcommands."""
    from libcchdo.db.model import ignore_sa_warnings

    args = hydro_parser.parse_args()
    with ignore_sa_warnings():
        try:
            hydro_parser.exit(args.main(args))
        except Exception, err:
            log.critical(format_exc(err))
