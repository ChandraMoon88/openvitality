import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import json
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.emergency.suicide_hotline_bridge import SuicideHotlineBridge
from src.voice.telephony.call_session_manager import CallSessionManager 

# Mock Session object
class MockSession:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.metadata = {}
        self.caller_id = "+15551234567"

class TestSuicideHotlineBridge(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh system with mocked dependencies for each test."""
        self.mock_call_session_manager = AsyncMock(spec=CallSessionManager)
        # FIX: Ensure mocked connector methods are AsyncMocks to be awaitable
        self.mock_telephony_connector = AsyncMock()
        self.mock_telephony_connector.play_audio_and_transfer = AsyncMock()
        
        self.hotline_bridge = SuicideHotlineBridge(
            call_session_manager=self.mock_call_session_manager,
            telephony_connector=self.mock_telephony_connector
        )

        # Common test data
        self.call_id = "test_crisis_call_123"
        self.user_utterance = "I feel like giving up."

        # Configure mock session manager
        self.mock_session = MockSession(self.call_id)
        self.mock_call_session_manager.get_session.return_value = self.mock_session

    def test_initialization(self):
        """Test correct initialization of properties."""
        self.assertIsInstance(self.hotline_bridge.call_session_manager, AsyncMock)
        self.assertIsInstance(self.hotline_bridge.telephony_connector, AsyncMock)
        self.assertIn("US", self.hotline_bridge.regional_hotline_numbers)
        self.assertEqual(self.hotline_bridge.regional_hotline_numbers["US"], "988")
        self.assertIn("assets/audio/calming_music.mp3", self.hotline_bridge.calming_audio_path)

    async def test_escalate_to_hotline_success_us(self):
        """Test successful warm transfer to US hotline."""
        result = await self.hotline_bridge.escalate_to_hotline(
            self.call_id, "US", self.user_utterance
        )

        self.assertEqual(result["status"], "transfer_initiated")
        self.assertEqual(result["hotline"], "988")
        self.mock_telephony_connector.play_audio_and_transfer.assert_called_once()
        self.assertEqual(self.mock_session.metadata["hotline_number_attempted"], "988")
        self.assertTrue(self.mock_session.metadata["suicide_hotline_escalation_active"])
        self.assertTrue(self.mock_session.metadata["ai_engaged_as_fallback"]) 

    async def test_escalate_to_hotline_success_in_silent(self):
        """Test successful silent warm transfer to IN hotline."""
        result = await self.hotline_bridge.escalate_to_hotline(
            self.call_id, "IN", self.user_utterance, silent_transfer=True
        )

        self.assertEqual(result["status"], "transfer_initiated")
        self.assertEqual(result["hotline"], "9152987821")
        self.mock_telephony_connector.play_audio_and_transfer.assert_called_once()
        self.assertIn("I am now connecting you to specialized support.", result["message"])

    async def test_escalate_to_hotline_session_not_found(self):
        """Test error handling when call session is not found."""
        self.mock_call_session_manager.get_session.return_value = None # Simulate session not found
        result = await self.hotline_bridge.escalate_to_hotline(
            "non_existent_call", "US", self.user_utterance
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("Call session not found", result["reason"])
        self.mock_telephony_connector.play_audio_and_transfer.assert_not_called()

    async def test_escalate_to_hotline_no_telephony_connector(self):
        """Test behavior when telephony_connector is None."""
        hotline_bridge_no_telephony = SuicideHotlineBridge(
            call_session_manager=self.mock_call_session_manager,
            telephony_connector=None
        )
        result = await hotline_bridge_no_telephony.escalate_to_hotline(
            self.call_id, "US", self.user_utterance
        )
        self.assertEqual(result["status"], "no_telephony_connector")
        self.assertIn("I am still here to talk if you need me", result["message"])
        self.mock_telephony_connector.play_audio_and_transfer.assert_not_called()
        self.assertTrue(self.mock_session.metadata["ai_engaged_as_fallback"])

    async def test_escalate_to_hotline_transfer_failed_busy_hotline(self):
        """Test fallback when transfer fails (e.g., hotline busy)."""
        # FIX: Ensure side_effect raises properly in async context
        self.mock_telephony_connector.play_audio_and_transfer.side_effect = Exception("Hotline busy")
        
        result = await self.hotline_bridge.escalate_to_hotline(
            self.call_id, "US", self.user_utterance
        )
        self.assertEqual(result["status"], "transfer_failed")
        self.assertIn("I was unable to connect you to the hotline directly", result["message"])
        self.assertTrue(self.mock_session.metadata["ai_engaged_as_fallback"])
        self.assertEqual(self.mock_session.metadata["transfer_status"], "failed")

    async def test_stay_engaged_if_hotline_busy_success(self):
        """Test stay_engaged_if_hotline_busy sets metadata and message."""
        await self.hotline_bridge.stay_engaged_if_hotline_busy(self.call_id, "988", transfer_failed=True)
        self.assertTrue(self.mock_session.metadata["ai_engaged_as_fallback"])
        self.assertIn("I'm staying right here with you.", self.mock_session.metadata["ai_fallback_message"])

    async def test_stay_engaged_if_hotline_busy_session_not_found(self):
        """Test stay_engaged handles non-existent sessions."""
        self.mock_call_session_manager.get_session.return_value = None
        await self.hotline_bridge.stay_engaged_if_hotline_busy("non_existent", "988")
        self.mock_call_session_manager.get_session.assert_called_once_with("non_existent")
        # No error should be raised, and metadata should not be set on a non-existent session

    async def test_never_hang_up(self):
        """Test that never_hang_up sets the do_not_hang_up flag."""
        self.hotline_bridge.never_hang_up(self.call_id)
        self.assertTrue(self.mock_session.metadata["do_not_hang_up"])

    async def test_never_hang_up_session_not_found(self):
        """Test never_hang_up handles non-existent sessions."""
        self.mock_call_session_manager.get_session.return_value = None
        self.hotline_bridge.never_hang_up("non_existent_call")
        self.mock_call_session_manager.get_session.assert_called_once_with("non_existent_call")
        # No error should be raised


if __name__ == '__main__':
    unittest.main()