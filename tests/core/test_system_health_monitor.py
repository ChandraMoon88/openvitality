import sys
import os
import unittest
from unittest.mock import patch, AsyncMock
import asyncio

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.system_health_monitor import SystemHealthMonitor

class TestSystemHealthMonitor(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a SystemHealthMonitor instance for each test."""
        # Use a short interval for testing the loop
        self.monitor = SystemHealthMonitor(check_interval_seconds=0.01)

    async def asyncTearDown(self):
        """Ensure the monitor is stopped after each test."""
        self.monitor.stop()
        # Allow time for the task to be cancelled
        await asyncio.sleep(0.02)

    async def test_start_and_stop(self):
        """Test that the monitoring task starts and stops correctly."""
        self.assertIsNone(self.monitor._task)
        self.assertFalse(self.monitor._is_running)

        self.monitor.start()
        self.assertTrue(self.monitor._is_running)
        self.assertIsNotNone(self.monitor._task)
        
        await asyncio.sleep(0.02) # Let it run at least once

        self.monitor.stop()
        self.assertFalse(self.monitor._is_running)
        
        # Check if the task was cancelled
        with self.assertRaises(asyncio.CancelledError):
            await self.monitor._task

    @patch.object(SystemHealthMonitor, 'check_database', new_callable=AsyncMock)
    @patch.object(SystemHealthMonitor, 'check_memory_usage', new_callable=AsyncMock)
    async def test_run_checks_loop(self, mock_check_memory, mock_check_db):
        """Test that the main loop calls the check methods."""
        mock_check_db.return_value = {"status": "healthy"}
        mock_check_memory.return_value = {"status": "healthy", "used_percent": 50}

        self.monitor.start()
        await asyncio.sleep(0.02) # Allow the loop to run a couple of times

        self.assertGreaterEqual(mock_check_db.call_count, 1)
        self.assertGreaterEqual(mock_check_memory.call_count, 1)
        
        status = self.monitor.get_status()
        self.assertEqual(status["database"], {"status": "healthy"})
        self.assertEqual(status["memory"], {"status": "healthy", "used_percent": 50})

    @patch('psutil.disk_usage')
    async def test_check_disk_space(self, mock_disk_usage):
        """Test the disk space check logic."""
        # Healthy case
        mock_disk_usage.return_value = unittest.mock.MagicMock(percent=85) # 15% free
        result = await self.monitor.check_disk_space()
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["free_percent"], 15.0)

        # Unhealthy case
        mock_disk_usage.return_value = unittest.mock.MagicMock(percent=95) # 5% free
        result = await self.monitor.check_disk_space()
        self.assertEqual(result["status"], "unhealthy")
        self.assertEqual(result["free_percent"], 5.0)
        
    @patch('psutil.virtual_memory')
    async def test_check_memory_usage(self, mock_virtual_memory):
        """Test the memory usage check logic."""
        # Healthy case
        mock_virtual_memory.return_value = unittest.mock.MagicMock(percent=80)
        result = await self.monitor.check_memory_usage()
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["used_percent"], 80)
        
        # Unhealthy case
        mock_virtual_memory.return_value = unittest.mock.MagicMock(percent=95)
        result = await self.monitor.check_memory_usage()
        self.assertEqual(result["status"], "unhealthy")
        self.assertEqual(result["used_percent"], 95)
        
    @patch.object(SystemHealthMonitor, 'check_database', new_callable=AsyncMock)
    async def test_failing_check_is_handled(self, mock_check_db):
        """Test that a single failing check doesn't stop the monitor."""
        error_message = "Connection refused"
        mock_check_db.side_effect = ConnectionRefusedError(error_message)
        
        # We manually call _perform_one_check_cycle once to avoid dealing with the loop sleep
        await self.monitor._perform_one_check_cycle()
        
        status = self.monitor.get_status()
        self.assertIn("database", status)
        self.assertEqual(status["database"]["status"], "unhealthy")
        self.assertEqual(status["database"]["error"], error_message)
        
        # Check that other statuses are still populated (e.g., from the default checks)
        self.assertIn("disk", status)
        self.assertIn("memory", status)

if __name__ == '__main__':
    unittest.main()
