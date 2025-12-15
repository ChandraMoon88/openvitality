import sys
import os
import unittest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.config_loader import get_config

class TestConfigLoader(unittest.TestCase):

    def test_import(self):
        """
        Tests that the config_loader module can be imported.
        """
        self.assertIsNotNone(get_config)

    def test_get_config_loads_defaults(self):
        """
        Tests if the get_config function correctly loads the default configuration
        when no region is specified.
        """
        config = get_config()

        self.assertIn("app", config)
        self.assertEqual(config["app"]["name"], "Healthcare AI Assistant")
        self.assertIn("region", config)
        self.assertEqual(config["region"]["name"], "Default")
        self.assertEqual(config["region"]["currency"], "USD")

if __name__ == '__main__':
    unittest.main()