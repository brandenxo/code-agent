import unittest

from catalog import Catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog([{"name": "Red Pen"}, {"name": "Notebook"}])

    def test_case_insensitive_partial_match(self):
        self.assertEqual(self.catalog.search("PEN"), [{"name": "Red Pen"}])

    def test_no_match(self):
        self.assertEqual(self.catalog.search("pencil"), [])
