import ast
import unittest

import accounts


class AccountTests(unittest.TestCase):
    def test_both_kinds_normalize_identically(self):
        self.assertEqual(accounts.create_user(" A@B.COM ")["email"], "a@b.com")
        self.assertEqual(accounts.create_admin(" A@B.COM ")["email"], "a@b.com")

    def test_shared_helper_exists(self):
        tree = ast.parse(open("accounts.py", encoding="utf-8").read())
        functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        self.assertGreaterEqual(len(functions), 3)
