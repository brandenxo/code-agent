import unittest

from stats import mean


class MeanTests(unittest.TestCase):
    def test_values(self):
        self.assertEqual(mean([2, 4, 6]), 4)

    def test_empty(self):
        self.assertEqual(mean([]), 0.0)
