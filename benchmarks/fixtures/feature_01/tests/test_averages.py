import unittest

from averages import average


class AverageTests(unittest.TestCase):
    def test_average(self):
        self.assertEqual(average([1, 2, 6]), 3)

    def test_empty(self):
        with self.assertRaises(ValueError):
            average([])

    def test_generator(self):
        self.assertEqual(average(x for x in [2, 4]), 3)
