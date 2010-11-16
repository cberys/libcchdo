#!/usr/bin/env python

from __future__ import with_statement
import sys

import implib
from libcchdo.model import datafile
from libcchdo.formats.ctd.zip import exchange as ctdzipex
from libcchdo.formats.ctd.zip import netcdf_andrex as ctdzipnc_andrex


def main(argv):
    if len(argv) < 2:
        print 'Usage:', argv[0], '<andrex netcdf tar.gz>'
        return 1
    
    file = datafile.DataFileCollection()
    with open(argv[1], 'r') as in_file:
        ctdzipnc_andrex.read(file, in_file)
    
    print >> sys.stderr, 'Done reading. Beginning CTD Zip write.'
    
    ctdzipex.write(file, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
