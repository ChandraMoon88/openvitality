import sys
import os
import unittest
import asyncio
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.thread_pool_manager import ThreadPoolManager, os

# Mock os.cpu_count to ensure consistent test environment
@patch('os.cpu_count', return_value=4)
class TestThreadPoolManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Initializing the manager will use the mocked os.cpu_count
        self.manager = ThreadPoolManager()
        # Suppress print statements during tests for cleaner output
        self.mock_print = patch('builtins.print').start()
        
    def tearDown(self):
        self.manager.shutdown()
        self.mock_print.stop()

    def test_initialization_default_workers(self, mock_cpu_count):
        """Test that pools are initialized with default worker counts."""
        # Default max_io_workers = cpu_cores * 2 = 4 * 2 = 8
        self.assertEqual(self.manager.io_pool._max_workers, 8)
        # Default max_cpu_workers = cpu_cores = 4
        self.assertEqual(self.manager.cpu_pool._max_workers, 4)
        mock_cpu_count.assert_called_once() # Ensure cpu_count was used

    @patch('src.core.thread_pool_manager.ThreadPoolExecutor')
    @patch('src.core.thread_pool_manager.ProcessPoolExecutor')
    def test_initialization_custom_workers(self, MockProcessPoolExecutor, MockThreadPoolExecutor, mock_cpu_count):
        """Test initialization with custom worker counts."""
        manager = ThreadPoolManager(max_io_workers=10, max_cpu_workers=5)
        MockThreadPoolExecutor.assert_called_once_with(max_workers=10)
        MockProcessPoolExecutor.assert_called_once_with(max_workers=5)
        manager.shutdown() # Clean up custom manager

    @patch('asyncio.get_running_loop')
    async def test_run_in_io_pool(self, mock_get_running_loop, mock_cpu_count):
        """Test that run_in_io_pool uses the correct executor."""
        mock_loop = MagicMock()
        mock_get_running_loop.return_value = mock_loop
        
        # Mock run_in_executor to return a future
        mock_loop.run_in_executor.return_value = asyncio.Future()
        mock_loop.run_in_executor.return_value.set_result("io_task_done")

        def mock_io_func():
            return "io_task_done"

        result = await self.manager.run_in_io_pool(mock_io_func, "arg1", "arg2")

        mock_get_running_loop.assert_called_once()
        mock_loop.run_in_executor.assert_called_once_with(
            self.manager.io_pool, mock_io_func, "arg1", "arg2"
        )
        self.assertEqual(result, "io_task_done")

    @patch('asyncio.get_running_loop')
    async def test_run_in_cpu_pool(self, mock_get_running_loop, mock_cpu_count):
        """Test that run_in_cpu_pool uses the correct executor."""
        mock_loop = MagicMock()
        mock_get_running_loop.return_value = mock_loop

        # Mock run_in_executor to return a future
        mock_loop.run_in_executor.return_value = asyncio.Future()
        mock_loop.run_in_executor.return_value.set_result("cpu_task_done")

        def mock_cpu_func():
            return "cpu_task_done"

        result = await self.manager.run_in_cpu_pool(mock_cpu_func, "cpu_arg")

        mock_get_running_loop.assert_called_once()
        mock_loop.run_in_executor.assert_called_once_with(
            self.manager.cpu_pool, mock_cpu_func, "cpu_arg"
        )
        self.assertEqual(result, "cpu_task_done")

    @patch('src.core.thread_pool_manager.ThreadPoolExecutor.shutdown')
    @patch('src.core.thread_pool_manager.ProcessPoolExecutor.shutdown')
    def test_shutdown(self, mock_cpu_shutdown, mock_io_shutdown, mock_cpu_count):
        """Test that shutdown calls shutdown on both pools."""
        self.manager.shutdown()
        mock_io_shutdown.assert_called_once_with(wait=True)
        mock_cpu_shutdown.assert_called_once_with(wait=True)
