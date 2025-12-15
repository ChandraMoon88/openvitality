import sys
import os
import unittest
import time

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.priority_queue import PriorityQueue, Priority

class TestPriorityQueue(unittest.TestCase):

    def setUp(self):
        """Create a new PriorityQueue for each test."""
        self.pq = PriorityQueue(max_wait_time_seconds=2) # Short wait time for testing promotion

    def test_push_and_pop(self):
        """Test basic pushing and popping of a single item."""
        self.pq.push("task1", Priority.MEDIUM)
        self.assertFalse(self.pq.is_empty())
        item = self.pq.pop()
        self.assertEqual(item, "task1")
        self.assertTrue(self.pq.is_empty())

    def test_priority_order(self):
        """Test that items are popped in correct priority order."""
        self.pq.push("low_task", Priority.LOW)
        self.pq.push("critical_task", Priority.CRITICAL)
        self.pq.push("medium_task", Priority.MEDIUM)
        self.pq.push("high_task", Priority.HIGH)

        self.assertEqual(self.pq.pop(), "critical_task")
        self.assertEqual(self.pq.pop(), "high_task")
        self.assertEqual(self.pq.pop(), "medium_task")
        self.assertEqual(self.pq.pop(), "low_task")
        self.assertTrue(self.pq.is_empty())

    def test_fifo_for_same_priority(self):
        """Test that items of the same priority are popped in FIFO order."""
        # The timestamp ensures FIFO for same-priority items
        self.pq.push("first_medium", Priority.MEDIUM)
        time.sleep(0.01)
        self.pq.push("second_medium", Priority.MEDIUM)
        time.sleep(0.01)
        self.pq.push("first_critical", Priority.CRITICAL)
        time.sleep(0.01)
        self.pq.push("second_critical", Priority.CRITICAL)


        self.assertEqual(self.pq.pop(), "first_critical")
        self.assertEqual(self.pq.pop(), "second_critical")
        self.assertEqual(self.pq.pop(), "first_medium")
        self.assertEqual(self.pq.pop(), "second_medium")

    def test_is_empty(self):
        """Test the is_empty method."""
        self.assertTrue(self.pq.is_empty())
        self.pq.push("some_task", Priority.LOW)
        self.assertFalse(self.pq.is_empty())
        self.pq.pop()
        self.assertTrue(self.pq.is_empty())

    def test_pop_from_empty_queue(self):
        """Test that popping from an empty queue returns None."""
        self.assertIsNone(self.pq.pop())

    def test_invalid_priority_type(self):
        """Test that pushing with an invalid priority raises a TypeError."""
        with self.assertRaises(TypeError):
            self.pq.push("task", "not_a_priority")
        with self.assertRaises(TypeError):
            self.pq.push("task", 1)

    def test_priority_promotion(self):
        """Test that a task's priority is promoted after the max wait time."""
        self.pq.push("medium_task", Priority.MEDIUM)
        self.pq.push("critical_task", Priority.CRITICAL)
        
        # Pop the critical task first
        self.assertEqual(self.pq.pop(), "critical_task")

        # Wait for the medium task to age and be promoted
        time.sleep(2.5)
        
        # Manually trigger promotion for testing purposes
        self.pq._promote_aged_tasks()

        # The medium task should have been promoted to HIGH.
        # We can't directly check the priority, but we can infer it.
        # Let's add a new HIGH priority task. The promoted one should come out first.
        self.pq.push("new_high_task", Priority.HIGH)

        popped_item = self.pq.pop()
        self.assertEqual(popped_item, "medium_task")
        
        popped_item = self.pq.pop()
        self.assertEqual(popped_item, "new_high_task")


    def test_get_wait_times(self):
        """Test the calculation of wait time statistics."""
        self.pq.push("task1", Priority.LOW)
        time.sleep(1)
        self.pq.push("task2", Priority.HIGH)
        
        wait_times = self.pq.get_wait_times()

        self.assertIsInstance(wait_times, dict)
        self.assertIn("LOW", wait_times)
        self.assertIn("HIGH", wait_times)
        
        # Wait times can be a bit variable, so check for a reasonable range
        self.assertGreater(wait_times["LOW"], 0.5)
        self.assertLess(wait_times["HIGH"], 0.5)
        self.assertEqual(wait_times["CRITICAL"], 0)


if __name__ == '__main__':
    unittest.main()
