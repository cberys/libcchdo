""" Test case for libcchdo.Column """


from unittest import TestCase

import libcchdo
import libcchdo.model.datafile
import libcchdo.db.model.std as std


class TestColumn(TestCase):

   def setUp(self):
       self.column = libcchdo.model.datafile.Column('EXPOCODE')
 
   def test_initialization(self):
       parameter = std.find_by_mnemonic('EXPOCODE')
 
       # The column did not initialize to the correct parameter
       self.assertEqual(self.column.parameter.mnemonic_woce(), 'EXPOCODE')
 
       # Missing values array.
       self.assertEqual(self.column.values, [])

       # Missing WOCE flags array
       self.assertEqual(self.column.flags_woce, [])

       # Missing IGOSS flags array
       self.assertEqual(self.column.flags_igoss, [])
   
   def test_get(self):
       self.assertEqual(None, self.column.get(0))
       self.column[0] = 1
       self.assertEqual(self.column.get(0), 1)
       self.assertEqual(self.column[0], 1)
       self.assertEqual(None, self.column.get(1))
       self.assertEqual(None, self.column.__getitem__(1))
   
   def test_length(self):
       self.assertEqual(len(self.column), 0)
       self.column[0] = 1
       self.assertEqual(len(self.column), 1)
       self.column[2] = 2
       self.assertEqual(len(self.column), 3)
   
   def test_set(self):
       self.column.set(1, 2, 3, 4)
       self.assertEqual(self.column[1], 2)
       self.assertEqual(self.column.flags_woce[1], 3)
       self.assertEqual(self.column.flags_igoss[1], 4)
       self.assertEqual(len(self.column), 2)
   
   def test_flagged_woce(self):
       self.assertFalse(self.column.is_flagged_woce()) # Column has WOCE flags when there should not be
       self.column[0] = 1
       self.assertFalse(self.column.is_flagged_woce()) # Column has WOCE flags when there should not be
       self.column.set(0, 1, 2, 3)
       self.assertTrue(self.column.is_flagged_woce()) # Column did not have WOCE flags when there should have been
   
   def test_flagged_igoss(self):
       self.assertFalse(self.column.is_flagged_igoss()) # Column has IGOSS flags when there should not be
       self.column[0] = 1
       self.assertFalse(self.column.is_flagged_igoss()) # Column has IGOSS flags when there should not be
       self.column.set(0, 1, 2, 3)
       self.assertTrue(self.column.is_flagged_igoss()) # Column did not have IGOSS flags when there should have been


