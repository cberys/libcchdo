#!/usr/bin/env python

import sys
sys.path.insert(0, '/'.join(sys.path[0].split('/')[:-1]))
from __future__ import with_statement
import libcchdo

from sys import argv, exit

if len(argv) < 3:
  print 'Usage:', argv[0], '<HOT Summary file>'
  exit(1)
file = libcchdo.SummaryFile()
with open(argv[1], 'r') as in_file:
  file.read_HOT_Summary(in_file)
file.write_nav(sys.stdout)
