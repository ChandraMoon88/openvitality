import sys
import os
import unittest
from cachetools import LRUCache

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.memory_manager import MemoryManager

class TestMemoryManager(unittest.TestCase):

    def setUp(self):
        """Initialize the MemoryManager for each test."""
        self.memory_manager = MemoryManager()
    
    def test_get_short_term_context_for_new_session(self):
        """Test that getting context for a new session returns an empty list."""
        context = self.memory_manager.get_short_term_context("new_session_id")
        self.assertEqual(context, [])

    def test_update_short_term_context(self):
        """Test adding a new exchange to the short-term memory."""
        session_id = "session1"
        exchange1 = {"user": "Hello", "ai": "Hi there!"}
        self.memory_manager.update_short_term_context(session_id, exchange1)
        
        context = self.memory_manager.get_short_term_context(session_id)
        self.assertEqual(len(context), 1)
        self.assertEqual(context[0], exchange1)

        exchange2 = {"user": "How are you?", "ai": "I am well."}
        self.memory_manager.update_short_term_context(session_id, exchange2)
        
        context = self.memory_manager.get_short_term_context(session_id)
        self.assertEqual(len(context), 2)
        self.assertEqual(context[-1], exchange2)

    def test_history_truncation(self):
        """Test that the history is truncated to the last 5 exchanges."""
        session_id = "session_truncate"
        
        # Add 7 exchanges
        for i in range(7):
            exchange = {"user": f"Message {i}", "ai": f"Response {i}"}
            self.memory_manager.update_short_term_context(session_id, exchange)
            
        context = self.memory_manager.get_short_term_context(session_id)
        
        # Check that only the last 5 are kept
        self.assertEqual(len(context), 5)
        # The first message should be "Message 2" now
        self.assertEqual(context[0]["user"], "Message 2")
        # The last message should be "Message 6"
        self.assertEqual(context[-1]["user"], "Message 6")

    def test_lru_cache_eviction(self):
        """Test that the LRU cache evicts the least recently used session."""
        # For this test, we create a manager with a small cache size
        self.memory_manager.short_term_memory = LRUCache(maxsize=2)
        
        session_id_1 = "lru_session_1"
        session_id_2 = "lru_session_2"
        session_id_3 = "lru_session_3"
        
        # Fill the cache
        self.memory_manager.update_short_term_context(session_id_1, {"user": "a", "ai": "b"})
        self.memory_manager.update_short_term_context(session_id_2, {"user": "c", "ai": "d"})
        
        # Access session 1 to make it more recently used
        self.memory_manager.get_short_term_context(session_id_1)
        
        # Now add session 3, which should evict session 2 (the least recently used)
        self.memory_manager.update_short_term_context(session_id_3, {"user": "e", "ai": "f"})

        # Session 1 should still be there
        self.assertIsNotNone(self.memory_manager.short_term_memory.get(session_id_1))
        # Session 3 should be there
        self.assertIsNotNone(self.memory_manager.short_term_memory.get(session_id_3))
        # Session 2 should have been evicted and now return the default empty list
        self.assertEqual(self.memory_manager.get_short_term_context(session_id_2), [])


if __name__ == '__main__':
    unittest.main()
