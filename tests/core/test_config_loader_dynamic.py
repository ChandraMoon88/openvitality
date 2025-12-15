import sys
import os
import unittest
from unittest.mock import Mock
import time
import tempfile
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.config_loader_dynamic import DynamicConfigLoader

class TestDynamicConfigLoader(unittest.TestCase):

    def setUp(self):
        """
        Set up a temporary directory and a mock callback for each test.
        """
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.mock_callback = Mock()
        self.loader = None

    def tearDown(self):
        """
        Clean up resources after each test.
        """
        if self.loader:
            self.loader.stop()
        self.temp_dir.cleanup()

    def test_init_with_nonexistent_dir(self):
        """
        Test that initializing with a non-existent directory raises ValueError.
        """
        non_existent_path = Path(self.temp_dir.name) / "non_existent"
        with self.assertRaises(ValueError):
            DynamicConfigLoader(non_existent_path, self.mock_callback)

    def test_file_modification_triggers_callback(self):
        """
        Test that modifying a file in the watched directory triggers the callback.
        """
        # Create a dummy config file
        config_file = self.config_dir / "settings.yaml"
        config_file.write_text("key: value\n")

        # Initialize and start the loader
        self.loader = DynamicConfigLoader(self.config_dir, self.mock_callback)
        self.loader.start()
        
        # Allow some time for the observer to start
        time.sleep(1) 

        # Modify the file
        config_file.write_text("key: new_value\n")

        # Allow time for the event to be processed
        time.sleep(1)

        # Check if the callback was called
        self.mock_callback.assert_called_once()

    def test_loader_start_and_stop(self):
        """
        Test the start and stop methods of the loader.
        """
        self.loader = DynamicConfigLoader(self.config_dir, self.mock_callback)
        
        # Check that the thread is not alive initially
        self.assertFalse(self.loader.thread.is_alive())

        self.loader.start()
        time.sleep(0.1)
        
        # Check that the thread is alive after starting
        self.assertTrue(self.loader.thread.is_alive())

        self.loader.stop()
        time.sleep(0.1) # Give thread time to join
        
        # Check that the thread is no longer alive after stopping
        # Note: The thread might not terminate instantly, so this could be flaky.
        # We check the stop event instead for reliability.
        self.assertTrue(self.loader._stop_event.is_set())
        
        # We can also join the thread in the test to be sure
        self.loader.thread.join(timeout=1)
        self.assertFalse(self.loader.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
