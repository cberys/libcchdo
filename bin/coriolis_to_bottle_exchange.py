#!/usr/bin/env python

from __future__ import with_statement
import sys

import implib
import libcchdo.model.datafile
import libcchdo.formats.coriolis.coriolis as coriolis
import libcchdo.formats.bottle.exchange as botex


def main(argv):
    if len(argv) < 2:
        print 'Usage:', argv[0], '<coriolis file>'
        return 1
    
    with open(argv[1], 'r') as in_file:
        file = libcchdo.model.datafile.DataFile()
        coriolis.read(file, in_file)
        botex.write(file, sys.stdout)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
