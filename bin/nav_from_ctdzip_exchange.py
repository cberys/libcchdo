#!/usr/bin/env python

import sys
sys.path.insert(0, '/'.join(sys.path[0].split('/')[:-1]))
from __future__ import with_statement
import libcchdo

from sys import argv, exit

if len(argv) < 3:
  print 'Usage:', argv[0], '<CTDZip Exchange file>'
  exit(1)
file = libcchdo.DataFileCollection()
with open(argv[1], 'r') as in_file:
  file.read_CTDZip_Exchange(in_file)
file.write_nav(sys.stdout)
