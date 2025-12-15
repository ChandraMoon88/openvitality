import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import re
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.emergency.emergency_detection_engine import EmergencyDetectionEngine

class TestEmergencyDetectionEngine(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh engine with mocked dependencies for each test."""
        self.mock_nlu_engine = AsyncMock()
        self.mock_sentiment_analyzer = MagicMock()
        self.mock_emergency_router = MagicMock()
        self.mock_audio_analyzer = MagicMock()
        self.mock_vad_engine = MagicMock()
        
        self.detector = EmergencyDetectionEngine(
            nlu_engine=self.mock_nlu_engine,
            sentiment_analyzer=self.mock_sentiment_analyzer,
            emergency_router=self.mock_emergency_router,
            audio_analyzer=self.mock_audio_analyzer,
            vad_engine=self.mock_vad_engine
        )

        # Default sentiment analyzer behavior
        self.mock_sentiment_analyzer.analyze_sentiment.return_value = {"label": "neutral", "score": 0.1}

    def test_initialization(self):
        """Test correct initialization of properties and trigger patterns."""
        self.assertIsInstance(self.detector.nlu_engine, AsyncMock)
        self.assertIsInstance(self.detector.sentiment_analyzer, MagicMock)
        self.assertIsInstance(self.detector.emergency_router, MagicMock)
        self.assertIsInstance(self.detector.trigger_patterns["CARDAC"][0], re.Pattern)
        self.assertEqual(self.detector.audio_panic_threshold, 0.8)

    async def test_check_for_emergency_cardac(self):
        """Test detection of CARDAC emergencies."""
        text = "I have crushing chest pain radiating to my left arm!"
        self.assertTrue(await self.detector.check_for_emergency(text))
        self.mock_emergency_router.escalate_emergency_call.assert_called_once()
        self.assertIn("CARDAC", self.detector.get_emergency_classification(text))

    async def test_check_for_emergency_respiratory(self):
        """Test detection of RESPIRATORY emergencies."""
        text = "I can't breathe, I'm gasping for air!"
        self.assertTrue(await self.detector.check_for_emergency(text))
        self.mock_emergency_router.escalate_emergency_call.assert_called_once()
        self.assertIn("RESPIRATORY", self.detector.get_emergency_classification(text))

    async def test_check_for_emergency_neuro(self):
        """Test detection of NEURO emergencies."""
        text = "I think I'm having a stroke, my face is drooping."
        self.assertTrue(await self.detector.check_for_emergency(text))
        self.mock_emergency_router.escalate_emergency_call.assert_called_once()
        self.assertIn("NEURO", self.detector.get_emergency_classification(text))

    async def test_check_for_emergency_trauma(self):
        """Test detection of TRAUMA emergencies."""
        text = "I'm bleeding heavily from a head injury!"
        self.assertTrue(await self.detector.check_for_emergency(text))
        self.mock_emergency_router.escalate_emergency_call.assert_called_once()
        self.assertIn("TRAUMA", self.detector.get_emergency_classification(text))

    async def test_check_for_emergency_mental_health_crisis_keyword(self):
        """Test detection of MENTAL_HEALTH_CRISIS emergencies via keywords."""
        text = "I want to kill myself, I can't go on."
        self.assertTrue(await self.detector.check_for_emergency(text))
        self.mock_emergency_router.escalate_emergency_call.assert_called_once()
        self.assertIn("MENTAL_HEALTH_CRISIS", self.detector.get_emergency_classification(text))

    async def test_check_for_emergency_mental_health_crisis_sentiment(self):
        """Test detection of MENTAL_HEALTH_CRISIS via extreme negative sentiment."""
        self.mock_sentiment_analyzer.analyze_sentiment.return_value = {"label": "negative", "score": -0.9, "emotional_indicators": {"depression": True}}
        text = "I feel very sad and hopeless today."
        self.assertTrue(await self.detector.check_for_emergency(text))
        self.mock_emergency_router.escalate_emergency_call.assert_called_once()
        self.assertIn("MENTAL_HEALTH_CRISIS", self.detector.get_emergency_classification(text))

    async def test_check_for_emergency_general_keyword(self):
        """Test detection of GENERAL_EMERGENCY_KEYWORDS."""
        text = "Help me, it's an emergency, call 911!"
        self.assertTrue(await self.detector.check_for_emergency(text))
        self.mock_emergency_router.escalate_emergency_call.assert_called_once()
        self.assertIn("GENERAL_EMERGENCY_KEYWORDS", self.detector.get_emergency_classification(text))

    async def test_check_for_emergency_no_emergency(self):
        """Test cases where no emergency is detected."""
        text = "I have a slight cough."
        self.assertFalse(await self.detector.check_for_emergency(text))
        self.mock_emergency_router.escalate_emergency_call.assert_not_called()
        self.assertListEqual(self.detector.get_emergency_classification(text), [])

    async def test_check_for_emergency_router_not_provided(self):
        """Test behavior when emergency_router is not provided."""
        detector_no_router = EmergencyDetectionEngine(
            sentiment_analyzer=self.mock_sentiment_analyzer,
            emergency_router=None
        )
        text = "I have crushing chest pain."
        self.assertTrue(await detector_no_router.check_for_emergency(text))
        # Ensure no error and no call to a non-existent router
        self.mock_emergency_router.escalate_emergency_call.assert_not_called()

    async def test_check_for_emergency_audio_stream_placeholder(self):
        """Test with audio stream (conceptual placeholder)."""
        # The current implementation of audio analysis is a placeholder
        # This test ensures it doesn't break if audio_stream is provided
        text = "Normal speech."
        audio_stream = MagicMock()
        self.assertFalse(await self.detector.check_for_emergency(text, audio_stream=audio_stream))

    def test_get_emergency_classification(self):
        """Test get_emergency_classification returns correct categories."""
        text1 = "My chest hurts and I can't breathe."
        classification = self.detector.get_emergency_classification(text1)
        self.assertIn("CARDAC", classification)
        self.assertIn("RESPIRATORY", classification)

        text2 = "I'm feeling fine."
        self.assertListEqual(self.detector.get_emergency_classification(text2), [])

    def test_bypass_normal_flow_if_emergency(self):
        """Test that bypass_normal_flow_if_emergency returns the passed boolean."""
        self.assertTrue(self.detector.bypass_normal_flow_if_emergency(True))
        self.assertFalse(self.detector.bypass_normal_flow_if_emergency(False))

if __name__ == '__main__':
    unittest.main()