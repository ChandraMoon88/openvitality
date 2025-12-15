import sys
import os
import unittest
import time

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.session_manager import (
    create_session,
    get_session,
    update_session,
    clear_session,
    SessionCache,
)

class TestSessionManager(unittest.TestCase):

    def setUp(self):
        """
        This method is called before each test.
        We clear the cache to ensure test isolation.
        """
        # We replace the global cache with a fresh instance for each test
        self.test_cache = SessionCache(capacity=10)
        # Monkey patch the global cache in the module
        import src.core.session_manager
        src.core.session_manager._session_cache = self.test_cache

    def test_create_session(self):
        """Test creating a new session."""
        user_hash = "test_user_123"
        session = create_session(user_hash, language="en")

        self.assertIn("session_id", session)
        self.assertEqual(session["user_phone_hash"], user_hash)
        self.assertEqual(session["language"], "en")
        self.assertIn("started_at", session)
        self.assertIn("last_active", session)
        self.assertEqual(session["context"], {})
        self.assertEqual(session["history"], [])

        # Check if it's actually in the cache
        retrieved_session = get_session(session["session_id"])
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session["session_id"], session["session_id"])

    def test_get_session(self):
        """Test retrieving an existing session."""
        user_hash = "test_user_456"
        session = create_session(user_hash)
        session_id = session["session_id"]

        retrieved_session = get_session(session_id)
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session["user_phone_hash"], user_hash)

    def test_get_nonexistent_session(self):
        """Test retrieving a session that does not exist."""
        retrieved_session = get_session("nonexistent-id")
        self.assertIsNone(retrieved_session)

    def test_update_session(self):
        """Test updating a session's data."""
        user_hash = "test_user_789"
        session = create_session(user_hash)
        session_id = session["session_id"]
        original_last_active = session["last_active"]

        time.sleep(0.01) # Ensure time progresses

        updated_data = session.copy()
        updated_data["context"]["new_key"] = "new_value"
        update_session(session_id, updated_data)

        retrieved_session = get_session(session_id)
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session["context"]["new_key"], "new_value")
        self.assertGreater(retrieved_session["last_active"], original_last_active)

    def test_clear_session(self):
        """Test deleting a session."""
        user_hash = "test_user_to_delete"
        session = create_session(user_hash)
        session_id = session["session_id"]

        # Ensure session exists first
        self.assertIsNotNone(get_session(session_id))

        clear_session(session_id)

        # Now it should be gone
        self.assertIsNone(get_session(session_id))

    def test_cache_capacity_lru(self):
        """Test if the LRU cache evicts the least recently used item."""
        self.test_cache = SessionCache(capacity=3)
        import src.core.session_manager
        src.core.session_manager._session_cache = self.test_cache
        
        # Create 3 sessions, filling the cache
        s1 = create_session("user1")
        s2 = create_session("user2")
        s3 = create_session("user3")

        # Access s1 and s2 to make them more recently used
        get_session(s1["session_id"])
        get_session(s2["session_id"])

        # Now create a 4th session, which should evict the least recently used (s3)
        s4 = create_session("user4")

        # s3 should now be None because it was the least recently used
        self.assertIsNotNone(get_session(s1["session_id"]))
        self.assertIsNotNone(get_session(s2["session_id"]))
        self.assertIsNotNone(get_session(s4["session_id"]))
        self.assertIsNone(get_session(s3["session_id"]))


if __name__ == '__main__':
    unittest.main()
