#!/usr/bin/env python
"""
A small percentage of WOCE format hydro data is submitted with oxygens
(both bottle and CTD) in ML/L and with nutrients in UMOL/L.  This program
will detect and convert data in /L units and convert them to /KG units.
 
Program asks for:    input filename   (.HYD or .SEA file)
                     output filename:
                     if bottle oxygens:
                           were oxygens whole bottle or aliquot 
 
notes:
    Input format is assumed to be correctly formatted WHP data
    Data columns identifiers and units strings must be correct
      and in upper case.  ie.  oxygens are ML/L
    Oxygen conversion uses sigma T for density. T is set at
      25 C for aliquot oxygens and when T is missing.  
"""


from __future__ import with_statement
import sys

import implib
import libcchdo.model.datafile as datafile
import libcchdo.units.convert as cvt
import libcchdo.db.model.std as std
import libcchdo.formats.bottle.exchange as botex


LOG = libcchdo.LOG


def check_and_replace_parameters(self):
    for column in self.columns.values():
        parameter = column.parameter
        std_parameter = std.find_by_mnemonic(parameter.name)

        if not std_parameter and not parameter.name.startswith('_'):
            LOG.warn("Unknown parameter '%s'" % parameter.name)
            continue

        given_units = parameter.units.mnemonic if parameter.units else None
        expected_units = std_parameter.units.mnemonic \
            if std_parameter.units else None
        from_to = (given_units, expected_units)

        if given_units and expected_units and given_units != expected_units:
            LOG.warn(("Mismatched units for '%s'. "
                      "Found '%s' but expected '%s'") % \
                      ((parameter.name,) + from_to))
            try:
                unit_converter = self.unit_converters[from_to]
                convert = None
                while not convert or convert.lower() not in ('y', 'n'):
                    try:
                        convert = raw_input(
                            ("Convert from '%s' to '%s' for '%s'? (y/n)") % \
                            (from_to + (parameter.name,)))
                    except EOFError:
                        pass
                if convert == 'y':
                    LOG.info("Converting from '%s' -> '%s' for %s." % \
                             (from_to + (column.parameter.name,)))
                    column = unit_converter(self, column)
                else:
                    # Skip conversion and unit change.
                    continue
            except KeyError:
                LOG.info(("No unit converter registered with file for "
                          "'%s' -> '%s'. Skipping conversion.") % from_to)
                continue

        column.parameter = std_parameter


def main(argv):
    """Converts WOCE format /L units to /KG."""
    if len(argv) < 2:
        filename = raw_input(("Please give an input Exchange filename "
                              "(hy1.csv):")).strip()
    else:
        filename = argv[1]

    if len(argv) < 3:
        outputfile = raw_input(("Please give an output Exchange filename "
                                "(hy1.csv):")).strip()
    else:
        outputfile = argv[2]

    file = datafile.DataFile()

    with open(filename, 'r') as f:
        botex.read(file, f)

    file.unit_converters[('DEG C', u'ITS-90')] = cvt.equivalent

    file.unit_converters[('ML/L', u'UMOL/KG')] = \
        cvt.milliliter_per_liter_to_umol_per_kg
    file.unit_converters[('UMOL/L', u'UMOL/KG')] = \
        cvt.mol_per_liter_to_mol_per_kg
    file.unit_converters[('PMOL/L', u'PMOL/KG')] = \
        cvt.mol_per_liter_to_mol_per_kg
    file.unit_converters[('NMOL/L', u'NMOL/KG')] = \
        cvt.mol_per_liter_to_mol_per_kg
    # XXX YIKES but it's there in the fortran
    #file.unit_converters[('MMOL/L', u'UMOL/KG')] = \
    #    cvt.mol_per_liter_to_mol_per_kg
    check_and_replace_parameters(file)

    with open(outputfile, 'w') as f:
        botex.write(file, f)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
