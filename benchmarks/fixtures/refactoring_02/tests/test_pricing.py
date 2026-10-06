import ast
import unittest

import pricing


class PricingTests(unittest.TestCase):
    def test_prices_are_consistent(self):
        self.assertEqual(pricing.retail_price(100, 20), 80)
        self.assertEqual(pricing.vip_price(100, 20), 80)

    def test_shared_helper_exists(self):
        tree = ast.parse(open("pricing.py", encoding="utf-8").read())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        self.assertGreaterEqual(len(functions), 3)
