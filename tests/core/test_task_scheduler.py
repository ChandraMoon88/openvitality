import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.task_scheduler import TaskScheduler

class TestTaskScheduler(unittest.TestCase):

    def setUp(self):
        self.db_url = "sqlite:///:memory:" # Use an in-memory SQLite for testing
        self.scheduler = TaskScheduler(self.db_url)

    @patch('builtins.print')
    def test_initialization(self, mock_print):
        """Test that TaskScheduler initializes correctly."""
        # The setUp already instantiates, so we just check the print output
        mock_print.assert_called_with("TaskScheduler initialized.")

    @patch('builtins.print')
    def test_start_method(self, mock_print):
        """Test the start method."""
        self.scheduler.start()
        mock_print.assert_called_with("Task scheduler started.")

    @patch('builtins.print')
    def test_stop_method(self, mock_print):
        """Test the stop method."""
        self.scheduler.stop()
        mock_print.assert_called_with("Task scheduler stopped.")

    @patch('builtins.print')
    def test_add_job_method(self, mock_print):
        """Test the add_job method."""
        def dummy_job():
            pass
        self.scheduler.add_job(dummy_job)
        mock_print.assert_called_with(f"Adding job {dummy_job} to scheduler.")

    @patch('builtins.print')
    def test_cancel_job_method(self, mock_print):
        """Test the cancel_job method."""
        job_id = "test_job_123"
        self.scheduler.cancel_job(job_id)
        mock_print.assert_called_with(f"Cancelling job {job_id}.")
