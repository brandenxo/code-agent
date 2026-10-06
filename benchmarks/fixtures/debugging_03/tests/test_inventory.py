import unittest

from inventory import remove_stock


class InventoryTests(unittest.TestCase):
    def test_preserves_other_items(self):
        stock = {"pen": 5, "paper": 10}
        self.assertEqual(remove_stock(stock, "pen", 2), {"pen": 3, "paper": 10})

    def test_missing_item(self):
        with self.assertRaises(KeyError):
            remove_stock({}, "pen", 1)
