#!/usr/bin/env python


from __future__ import with_statement
import getopt
import sys

import implib
import libcchdo.fns
from libcchdo.formats.google_wire import google_wire


def main(argv):
    opts, args = getopt.getopt(argv[1:], 'jt:h', ['json', 'type=', 'help'])
    usage = "Usage: %s [-j|--json,-t|--type] <any recognized CCHDO file>" % argv[0]

    if len(args) < 1:
        print >> sys.stderr, usage
        return 1

    flag_json = False
    file_type = None

    for o, a in opts:
        if o in ('-j', '--json'):
            flag_json = True
        elif o in ('-t', '--type'):
            file_type = a
        elif o in ('-h', '--help'):
        	print >> sys.stderr, usage
        	return 1
        else:
            assert False, "unhandled option"

    with open(args[0], 'r') as in_file:
        file = libcchdo.fns.read_arbitrary(in_file, file_type)
        google_wire.write(file, sys.stdout, json=flag_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
