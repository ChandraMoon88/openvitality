import sys
import os
import unittest
import asyncio

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.orchestrator import Orchestrator

class TestOrchestrator(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up an Orchestrator instance for each test."""
        self.orchestrator = Orchestrator()

    async def test_handle_text_input_placeholder(self):
        """
        Tests the current placeholder implementation of the handle_text_input method.
        """
        test_data = {
            "session_id": "12345",
            "text": "Hello, I have a headache."
        }
        
        response = await self.orchestrator.handle_text_input(test_data)
        
        expected_response = {
            "response": "Processed by orchestrator.",
            "agent": "placeholder_agent"
        }
        
        self.assertEqual(response, expected_response)

    async def test_connect_and_close_services(self):
        """
        Tests the connect and close methods (currently they just print).
        This test mainly ensures they can be called without error.
        """
        # These methods are synchronous in the current implementation,
        # but we call them with await as they are defined as async.
        await self.orchestrator.connect_services()
        await self.orchestrator.close_services()
        # No assertion needed, we just want to make sure it runs without crashing.


if __name__ == '__main__':
    unittest.main()
