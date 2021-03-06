"""Functions used globally.

"""


try:
    from cdecimal import Decimal, getcontext, InvalidOperation
except ImportError:
    from decimal import Decimal, getcontext, InvalidOperation
import math
import os.path
import sys
from datetime import datetime, timedelta

from libcchdo import RADIUS_EARTH


# Define isnan for python <2.6
try:
    isnan = math.isnan
except AttributeError:
    def isnan(n):
        return n != n


def uniquify(seq):
    '''Order preserving uniquify.
       http://www.peterbe.com/plog/uniqifiers-benchmark/
         uniqifiers_benchmark.py (f8 by Dave Kirby)
    '''
    seen = set()
    a = seen.add
    return [x for x in seq if x not in seen and not a(x)]


def _ensure_list_len(L, i, fill=None):
    for x in xrange(i - len(L) + 1):
        L.append(fill)


def set_list(L, i, value, fill=None):
    """ Set a cell in a list. If the list is not long enough, extend it first.
        Args:
            L - the list
            i - the index
            value - the value to put at L[i]
            fill - the value to fill if the list is to be extended
    """
    _ensure_list_len(L, i, fill)
    L[i] = value


def strip_all(l):
    return [x.strip() for x in l]


def get_editor():
    """Return the command that is the local editor. Defaults to vi."""
    return (
        os.environ.get('LIBCCHDOEDITOR') or 
        os.environ.get('VISUAL') or 
        os.environ.get('EDITOR', 'vi')
        )


def great_circle_distance(lat_stand, lng_stand, lat_fore, lng_fore):
    delta_lng = lng_fore - lng_stand
    cos_lat_fore = math.cos(lat_fore)
    cos_lat_stand = math.cos(lat_stand)
    cos_lat_fore_cos_delta_lng = cos_lat_fore * math.cos(delta_lng)
    sin_lat_stand = math.sin(lat_stand)
    sin_lat_fore = math.sin(lat_fore)

    # Vicenty formula from Wikipedia
    # fraction_top = sqrt( (cos_lat_fore * sin(delta_lng)) ** 2 +
    #                      (cos_lat_stand * sin_lat_fore -
    #                       sin_lat_stand * cos_lat_fore_cos_delta_lng) ** 2)
    # fraction_bottom = sin_lat_stand * sin_lat_fore +
    #                   cos_lat_stand * cos_lat_fore_cos_delta_lng
    # central_angle = atan2(1.0, fraction_top/fraction_bottom)

    # simple formula from wikipedia
    central_angle = math.acos(cos_lat_stand * cos_lat_fore * \
                              math.cos(delta_lng) + \
                              sin_lat_stand * sin_lat_fore)

    arc_length = RADIUS_EARTH * central_angle
    return arc_length


def strftime_iso(dtime):
    return dtime.isoformat() + 'Z'


def ordinal_datetime_to_datetime(dtime):
    """Reverse of MATLAB's datenum.m.

    dtime is serial number of days elapsed since 0000-01-01.

    """
    start_dtime = datetime(1, 1, 1)
    extra_year = datetime(2, 1, 3) - start_dtime
    dtime_from_ordinal = start_dtime + timedelta(days=dtime)
    return dtime_from_ordinal - extra_year


def _decimal(x, *args):
    if len(args) > 0:
        x = [x] + list(args)
    if type(x) is Decimal:
        return x
    if isinstance(x, basestring):
        return Decimal(x)
    try:
        return map(_decimal, x)
    except TypeError:
        if type(x) is not str:
            x = str(x)
        return Decimal(x)


def decimal_to_str(val):
    """Convert Decimal to string intelligently or leave strings alone."""
    try:
        return format(val, '.{0}f'.format(-val.as_tuple().exponent))
    except AttributeError:
        return str(val)


def int_or_none(x):
    try:
        return int(x)
    except ValueError:
        return None


def equal_with_epsilon(a, b, epsilon=Decimal('1e-6')):
    delta = abs(_decimal(a) - _decimal(b))
    if delta.is_nan():
        return False
    return delta < _decimal(epsilon)


def is_list_global(lll):
    """Return whether the elements for the whole list are the same."""
    check = None
    for x in lll:
        if check is None:
            check = x
            continue
        if check != x:
            return False
    return True


def is_list_globally_equal(lll, value=0.0):
    """Return whether the given list is entirely composed of the same value."""
    if not is_list_global(lll):
        return False
    return lll[0] == value


def is_list_globally(lll, value=0.0, equal_func=equal_with_epsilon):
    """Return whether the given list is entirely composed of the same value."""
    if not is_list_global(lll):
        return False
    try:
        return equal_func(lll[0], value)
    except IndexError:
        return False
    return True


def out_of_band(value, oob=Decimal(-999),
                tolerance=Decimal('0.1')):
    try:
        number = _decimal(float(value))
    except ValueError:
        return False
    except TypeError:
        return True
    return equal_with_epsilon(oob, number, tolerance)


def in_band_or_none(x, oob=None, tolerance=None):
    """In band or none
       Args:
           x - anything
           oob - out-of-band value (defaults to out_of_band's default)
           tolerance - out-of-band tolerance (defaults to out_of_band's
                                              default)
       Returns:
           x or None if x is out of band
    """
    args = [x]
    if oob:
        args.append(oob)
    if tolerance:
        args.append(tolerance)
    return None if out_of_band(*args) else x


def identity_or_oob(x, oob=-999):
    """ Good for filling in lists that have Nones with oob values.
       Args:
           x - anything
           oob - out-of-band value (default -999)
       Returns:
           identity or out-of-band value.
    """
    return x if x else oob


def polynomial(x, coeffs):
    """Calculate a polynomial.
    
    Gives the result of calculating
    coeffs[n]*x**n + coeffs[n-1]*x**n-1 + ... + coeffs[0]
    """
    if len(coeffs) <= 0:
        return 0
    sum = _decimal(coeffs[0])
    degreed = x
    for coef in coeffs[1:]:
        sum += _decimal(coef) * degreed
        degreed *= x
    return sum


# The following are adapted from 
# http://docs.python.org/library/decimal.html#decimal-recipes


class IncreasedPrecision:

    def __init__(self, inc=2):
        self._inc = inc

    def __enter__(self):
        getcontext().prec += self._inc

    def __exit__(self, exc_type, exc_value, traceback):
        getcontext().prec -= self._inc


def exp(x):
    """Return e raised to the power of x.  Result type matches input type.

    >>> print exp(Decimal(1))
    2.718281828459045235360287471
    >>> print exp(Decimal(2))
    7.389056098930650227230427461
    >>> print exp(2.0)
    7.38905609893
    >>> print exp(2+0j)
    (7.38905609893+0j)

    """
    with IncreasedPrecision():
        i, lasts, s, fact, num = 0, 0, 1, 1, 1
        while s != lasts:
            lasts = s
            i += 1
            fact *= i
            num *= x
            s += num / fact
    return +s


def cos(x):
    """Return the cosine of x as measured in radians.

    >>> print cos(Decimal('0.5'))
    0.8775825618903727161162815826
    >>> print cos(0.5)
    0.87758256189
    >>> print cos(0.5+0j)
    (0.87758256189+0j)

    """
    with IncreasedPrecision():
        i, lasts, s, fact, num, sign = 0, 0, 1, 1, 1, 1
        while s != lasts:
            lasts = s
            i += 2
            fact *= i * (i-1)
            num *= x * x
            sign *= -1
            s += num / fact * sign
    return +s


def sin(x):
    """Return the sine of x as measured in radians.

    >>> print sin(Decimal('0.5'))
    0.4794255386042030002732879352
    >>> print sin(0.5)
    0.479425538604
    >>> print sin(0.5+0j)
    (0.479425538604+0j)

    """
    with IncreasedPrecision():
        i, lasts, s, fact, num, sign = 1, 0, x, 1, x, 1
        while s != lasts:
            lasts = s
            i += 2
            fact *= i * (i-1)
            num *= x * x
            sign *= -1
            s += num / fact * sign
    return +s

def ddm_to_dd(ctoks, precision=None):
    """Converts a coordinate in DDD MM.mmm format to signed DDD.DDDDD
    
    Origionally adapted from the woce formats woce_lng_to_dec_lng. It has been
    generalized.

    Arguments:
    ctoks -- tokenized parts of the origional coordinate. Expected to be in the
             format of [ddd, mm.mmm, h] where h specifies the hemisphere (E, N,
             W, or S)
    precision -- integer to specify precision, if none, will guess based on the
                 value of h in the ctoks

    Returns a Decimal corrdinate
    """
    if precision:
        precision = precision + len(ctoks)
    else: # guess based on h
        if 'E' in ctoks[2] or 'W' in ctoks[2]:
            precision = 4 + len(ctoks)
        elif 'N' in ctoks[2] or 'S' in ctoks[2]:
            precision = 3 + len(ctoks)
        else:
            raise ValueError(('Expect E, W, N, or S in ctoks[2]'
                             'instead got:%s'), ctoks[2])
    with IncreasedPrecision(precision):
        cord = int(ctoks[0]) + Decimal(ctoks[1]) / Decimal('60.0')
        if ctoks[2] == 'W' or ctoks[2] == 'S':
            cord *= -1
        elif ctoks[2] == 'E' or ctoks[2] == 'N':
            pass
        else:
            raise ValueError(('Expect E, W, N, or S in ctoks[2]'
                             'instead got:%s'), ctoks[2])
        return cord.quantize(Decimal(10) ** -precision)

def create_expocode(nodc_ship_code, port_departure_date):
    """Generate an ExpoCode from an NODC ship code and port departure date.

    """
    return '{ship_code}{date}'.format(
        ship_code=nodc_ship_code, date=port_departure_date.strftime('%Y%m%d'))

known_file_types = {
    'hy.txt'   : 'Woce Bottle',
    'su.txt'   : 'Woce Sum',
    'ct.zip'   : 'Woce CTD (Zipped)',
    'sum'      : 'Sum File',
    'ctd$'     : 'CTD File',
    'ct1.zip'  : 'Exchange CTD (Zipped)',
    'ct1.csv'  : 'Exchange CTD',
    'hy1.zip'  : 'Exchange Bottle (Zipped)',
    'hy1.csv$' : 'Exchange Bottle',
    'ctd.zip$'  : 'NetCDF CTD',
    'hyd.zip'  : 'NetCDF Bottle',
    'do.txt'   : 'Documentation',
    'do.pdf'   : 'PDF Documentation',
    'xml'      : 'Directory Description',
    'na.txt'   : 'Coord info',
    'sea'      : 'SEA file',
    'detail.htm'    : 'Data History HTML',
    'person.htm'    : 'Person HTML',
    'type.htm'      : 'Type HTML',
    'datahist.htm'  : 'Data History HTML',
    'trk.jpg'       : 'Small Plot',
    'trk.gif'       : 'Large Plot',
    '.gof'          : 'JGOFS File',
    '.wct'          : 'WCT CTD File',
    'index.htm'     : 'Index HTML File',
    'index_OLD.htm' : 'Old Index HTML File',
    '.gmt'          : 'GMT info File',
    '[^(inv_)]hyd.txt'   : 'Exchange Bottle',
    '.ecp'   : 'French data file',
    '.nav'   : 'Coordinates?',
    '.asc'   : 'Encrypted file',
    '.ps'    : 'Postscript file',
    '.mat'   : 'Matlab file',
    '.lv'    : 'Large Volume file',
    '.lvs'   : 'Large Volume file',
    '$00_README.*/.txt' : 'Citation file',
}
