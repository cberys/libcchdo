import unittest

from ..model import datafile


class TestDataFile(unittest.TestCase):

    def setUp(self):
        self.file = datafile.DataFile()
        self.file.columns['EXPOCODE'] = datafile.Column('EXPOCODE')
        self.c = self.file.columns['EXPOCODE']
  
    def tearDown(self):
        self.file = None
  
    def test_init(self):
        self.assertEqual(len(self.file.columns), 1)
        self.assertEqual(self.file.footer, None)
        self.assertEqual(self.file.globals, {'stamp': '', 'header': ''})

    def test_expocodes(self):
        self.c.append('A')
        self.assertEqual(['A'], self.file.expocodes())
        self.c.append('B')
        self.assertEqual(['A', 'B'], self.file.expocodes())
        self.c.append('A')
        self.assertEqual(['A', 'B'], self.file.expocodes()) # Expocodes returns unique expocodes.
  
    def test_len(self):
        c = self.file.columns['EXPOCODE']
        del self.file.columns['EXPOCODE']
        self.assertEqual(len(self.file), 0)
        self.file.columns['EXPOCODE'] = c
        self.assertEqual(len(self.file), 0)
        self.c.append('A')
        self.assertEqual(len(self.file), 1)
        self.c.append('A')
        self.assertEqual(len(self.file), 2)
  
    def test_sorted_columns(self):
        self.file.columns['CASTNO'] = datafile.Column('CASTNO')
        self.file.columns['STNNBR'] = datafile.Column('STNNBR')
        expected = ['EXPOCODE', 'STNNBR', 'CASTNO']
        received = map(lambda c: c.parameter.mnemonic_woce(), self.file.sorted_columns())
        # If lengths are equal and all expected in received, then assume equal
        self.assertEqual(len(expected), len(received))
        self.assertTrue(all( [x in received for x in expected] ))
  
    def test_get_property_for_columns(self):
        pass # This is tested by the following tests.
  
    def test_column_headers(self):
        self.assertEqual(['EXPOCODE'], self.file.column_headers())
        self.file.columns['STNNBR'] = datafile.Column('STNNBR')
        expected = ['EXPOCODE', 'STNNBR']
        received = self.file.column_headers()
        # If lengths are equal and all expected in received, then assume equal
        self.assertEqual(len(expected), len(received))
        self.assertTrue(all( [x in received for x in expected] ))
  
    def test_formats(self):
        self.file.columns['CTDOXY'] = datafile.Column('CTDOXY')
        self.file.check_and_replace_parameters()
        self.assertEqual(['%11s', '%9.4f'], self.file.formats())
  
    def test_to_dict(self):
        self.file.to_dict()
        pass # TODO

    def test_str(self):
        str(self.file)
  
    def test_create_columns(self):
        parameters = ['CTDOXY']
        units = ['UMOL/KG']
        self.file.create_columns(parameters, units)