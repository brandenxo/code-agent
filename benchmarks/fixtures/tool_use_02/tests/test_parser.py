import unittest

from parser import parse_port


class ParserTests(unittest.TestCase):
    def test_valid_boundaries(self):
        self.assertEqual(parse_port("1"), 1)
        self.assertEqual(parse_port("65535"), 65535)

    def test_zero_is_invalid(self):
        with self.assertRaises(ValueError):
            parse_port("0")

    def test_too_large_is_invalid(self):
        with self.assertRaises(ValueError):
            parse_port("65536")
