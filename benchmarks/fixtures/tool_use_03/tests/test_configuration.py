from pathlib import Path
import unittest

import client
import config
import report


class ConfigurationTests(unittest.TestCase):
    def test_new_setting_is_used_everywhere(self):
        self.assertEqual(config.SETTINGS["request_timeout"], 15)
        self.assertEqual(client.request_options()["timeout"], 15)
        self.assertEqual(report.describe(), "Timeout: 15 seconds")

    def test_old_name_is_removed(self):
        for path in (Path("config.py"), Path("client.py"), Path("report.py")):
            self.assertNotIn("timeout_seconds", path.read_text(encoding="utf-8"))
