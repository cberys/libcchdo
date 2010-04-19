#!/usr/bin/env python

from __future__ import with_statement
from sys import argv, exit, path, stdout
path.insert(0, '/'.join(path[0].split('/')[:-1]))
from libcchdo import DataFile
from formats.bottle.exchange import exchange

if len(argv) < 2:
  print 'Usage:', argv[0], '<exbot file>'
  exit(1)
with open(argv[1], 'r') as in_file:
  file = DataFile()
  exchange(file).read(in_file)

  placemarks = ['%f,%f' % coord for coord in zip(file.columns['LONGITUDE'].values, file.columns['LATITUDE'].values)]

  print """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
<Document>
<name></name>
<Style id="linestyle">
  <LineStyle>
    <width>4</width>
    <color>ff0000ff</color>
  </LineStyle>
</Style>
<Placemark>
<styleUrl>#linestyle</styleUrl>
<LineString>
  <tessellate>1</tessellate>
  <coordinates>%s</coordinates>
</LineString>
</Placemark>
</Document></kml>""" % ' '.join(placemarks)