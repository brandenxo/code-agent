import unittest

from formatter import format_notification


class FormatterTests(unittest.TestCase):
    def test_formats_notification(self):
        self.assertEqual(format_notification("  alice ", "Hello"), "[ALICE] Hello")

    def test_empty_message(self):
        self.assertEqual(format_notification("ops", ""), "[OPS] ")
