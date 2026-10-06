import ast
import unittest

import names


class NameTests(unittest.TestCase):
    def test_labels_are_consistent(self):
        self.assertEqual(names.customer_label("  ada", "LOVELACE "), "Customer: Ada Lovelace")
        self.assertEqual(names.employee_label("  ada", "LOVELACE "), "Employee: Ada Lovelace")

    def test_shared_helper_exists(self):
        tree = ast.parse(open("names.py", encoding="utf-8").read())
        self.assertGreaterEqual(
            len([node for node in tree.body if isinstance(node, ast.FunctionDef)]), 3
        )
