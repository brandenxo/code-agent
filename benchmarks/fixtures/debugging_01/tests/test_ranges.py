import unittest

from ranges import inclusive_sum


class RangeTests(unittest.TestCase):
    def test_multiple_values(self):
        self.assertEqual(inclusive_sum(1, 3), 6)

    def test_single_value(self):
        self.assertEqual(inclusive_sum(5, 5), 5)


if __name__ == "__main__":
    unittest.main()
