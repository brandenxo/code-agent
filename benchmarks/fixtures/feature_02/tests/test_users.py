import unittest

from users import validate_username


class UsernameTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(validate_username("Agent007"))

    def test_length(self):
        self.assertFalse(validate_username("ab"))
        self.assertFalse(validate_username("a" * 21))

    def test_characters(self):
        self.assertFalse(validate_username("agent_007"))
