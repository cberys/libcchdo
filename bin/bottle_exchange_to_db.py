#!/usr/bin/env python

from __future__ import with_statement
import sys

import abs_import_libcchdo
import libcchdo.model.datafile
import libcchdo.formats.bottle.database as db
import libcchdo.formats.bottle.exchange as botex


def main(argv):
    if len(argv) < 2:
        print 'Usage:', argv[0], '<exbot file>'
        return 1
    
    with open(argv[1], 'r') as in_file:
        file = libcchdo.model.datafile.DataFile()
        botex.read(file, in_file)
        db.write(file)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
