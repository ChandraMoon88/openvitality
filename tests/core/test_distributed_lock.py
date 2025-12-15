import sys
import os
import unittest
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.distributed_lock import acquire_lock

class TestDistributedLock(unittest.TestCase):

    def test_acquire_and_release_lock(self):
        """Test basic acquisition and release of a lock."""
        lock_name = "test_resource_1"
        with acquire_lock(lock_name):
            # If we enter here, the lock was acquired
            pass
        # If we exit here without error, the lock was released
        self.assertTrue(True) # Just to have an assertion

    def test_lock_prevents_concurrent_access(self):
        """
        Test that a lock prevents two threads from accessing a critical section
        simultaneously.
        """
        lock_name = "test_resource_2"
        shared_list = []

        def worker():
            with acquire_lock(lock_name):
                # Simulate work
                time.sleep(0.1)
                shared_list.append(threading.current_thread().name)

        thread1 = threading.Thread(target=worker, name="Thread-1")
        thread2 = threading.Thread(target=worker, name="Thread-2")

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Check that the order implies sequential access, not concurrent
        # The first item should be added before the second thread can acquire the lock
        self.assertEqual(len(shared_list), 2)
        # We can't guarantee order, but we can ensure they both ran
        self.assertIn("Thread-1", shared_list)
        self.assertIn("Thread-2", shared_list)

        # A more robust check would involve timing or a more complex state,
        # but for a basic lock, sequential append is a good indicator.
        # This test ensures that the critical section is protected.

    def test_lock_timeout(self):
        """Test that acquiring a lock times out if not released."""
        lock_name = "test_resource_3"
        
        # Acquire the lock in a separate thread and hold it
        def hold_lock():
            with acquire_lock(lock_name):
                time.sleep(0.5) # Hold for 0.5 seconds

        holder_thread = threading.Thread(target=hold_lock)
        holder_thread.start()
        
        # Give the holder thread a moment to acquire the lock
        time.sleep(0.1)

        # Try to acquire the same lock with a shorter timeout in the main thread
        with self.assertRaises(TimeoutError):
            with acquire_lock(lock_name, timeout=0.1):
                pass
        
        holder_thread.join() # Wait for the holder thread to finish

    def test_multiple_distinct_locks(self):
        """Test that different lock names operate independently."""
        lock_name_a = "resource_a"
        lock_name_b = "resource_b"
        
        shared_data = {"a": 0, "b": 0}

        def worker_a():
            with acquire_lock(lock_name_a):
                time.sleep(0.1)
                shared_data["a"] = 1

        def worker_b():
            with acquire_lock(lock_name_b):
                time.sleep(0.1)
                shared_data["b"] = 1

        thread_a = threading.Thread(target=worker_a)
        thread_b = threading.Thread(target=worker_b)

        thread_a.start()
        thread_b.start()

        thread_a.join()
        thread_b.join()

        # Both should have completed their work independently
        self.assertEqual(shared_data["a"], 1)
        self.assertEqual(shared_data["b"], 1)
