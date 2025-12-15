import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import re
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.engagement.feedback_collection import FeedbackCollectionAgent

class TestFeedbackCollectionAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        # FIX: Use MagicMock for synchronous calls
        self.mock_nlu_engine = MagicMock() 
        self.mock_sentiment_analyzer = MagicMock()
        self.mock_task_scheduler = AsyncMock()
        self.mock_human_review_system = AsyncMock()
        
        self.agent = FeedbackCollectionAgent(
            nlu_engine=self.mock_nlu_engine,
            sentiment_analyzer=self.mock_sentiment_analyzer,
            task_scheduler=self.mock_task_scheduler,
            human_review_system=self.mock_human_review_system
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU and sentiment mocks
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "feedback"}}
        self.mock_sentiment_analyzer.analyze_sentiment.return_value = {"label": "neutral", "score": 0.1}

    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "FeedbackCollectionAgent")
        self.assertIn("feedback_session", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "waiting_for_trigger")

    async def test_process_input_trigger_feedback(self):
        """Test transition from waiting_for_trigger to asking_nps."""
        context = {"session_id": "test_session_1"}
        response = await self.agent.process_input("I want to give feedback.", context)
        
        self.assertEqual(self.agent.current_memory["conversation_stage"], "asking_nps")
        self.assertIn("On a scale of 0 to 10", response["response_text"])
        self.assertEqual(self.agent.current_memory["feedback_session"]["session_id_to_rate"], "test_session_1")
        self.assertEqual(response["action"], "ask_nps_score")

    async def test_process_input_invalid_nps(self):
        """Test handling of invalid NPS scores."""
        self.agent._memory["conversation_stage"] = "asking_nps"
        
        response = await self.agent.process_input("score is eleven", {})
        self.assertEqual(response["response_text"], "Please provide a number between 0 and 10.")
        self.assertEqual(response["action"], "retry_nps")

        response = await self.agent.process_input("not a number", {})
        self.assertEqual(response["response_text"], "Please provide a number between 0 and 10.")
        self.assertEqual(response["action"], "retry_nps")

    async def test_process_input_valid_nps_promoter(self):
        """Test valid NPS score for promoter."""
        self.agent._memory["conversation_stage"] = "asking_nps"
        response = await self.agent.process_input("10", {})
        self.assertEqual(self.agent.current_memory["feedback_session"]["nps_score"], 10)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "asking_qualitative")
        self.assertIn("That's wonderful to hear!", response["response_text"])
        self.assertEqual(response["action"], "ask_qualitative_feedback")

    async def test_process_input_unrecognized_input_waiting(self):
        """Test handling of unrecognized input in waiting_for_trigger stage."""
        response = await self.agent.process_input("Hello there.", {})
        self.assertIn("I can help with feedback if you are ready.", response["response_text"])
        self.assertEqual(response["action"], "clarify_feedback")

    async def test_process_nps_score_detractor(self):
        """Test detractor NPS score logic."""
        # FIX: Manually set memory as _process_nps_score does not set it, but parent process_input does.
        # Since we are testing the private method logic, we just check the return values.
        # If testing memory state, we should simulate what process_input does or just check return dict.
        # Here we just verify the return dict content.
        response = self.agent._process_nps_score(5, {})
        # Note: self.agent.current_memory won't be updated by _process_nps_score for nps_score.
        # We assert the stage update which _process_nps_score DOES do.
        self.assertEqual(self.agent.current_memory["conversation_stage"], "asking_qualitative")
        self.assertIn("what we could do to improve your experience?", response["response_text"])

    async def test_process_nps_score_passive(self):
        """Test passive NPS score logic."""
        response = self.agent._process_nps_score(7, {})
        # Same as above, check stage and text
        self.assertEqual(self.agent.current_memory["conversation_stage"], "asking_qualitative")
        self.assertIn("What was missing from your experience", response["response_text"])

    async def test_process_qualitative_feedback_non_escalated(self):
        """Test qualitative feedback without escalation."""
        self.agent._memory["conversation_stage"] = "asking_qualitative"
        self.mock_sentiment_analyzer.analyze_sentiment.return_value = {"label": "positive", "score": 0.9}
        
        response = await self.agent.process_input("It was a good experience.", {})
        self.assertEqual(self.agent.current_memory["feedback_session"]["qualitative_feedback"], "It was a good experience.")
        self.assertEqual(self.agent.current_memory["feedback_session"]["sentiment_of_feedback"]["label"], "positive")
        self.assertFalse(self.agent.current_memory["feedback_session"]["escalated_for_review"])
        self.assertIn("Thank you for your valuable feedback.", response["response_text"])
        self.assertEqual(response["action"], "feedback_recorded")
        self.assertEqual(self.agent.current_memory["conversation_stage"], "processing_feedback")
        self.mock_human_review_system.escalate_feedback.assert_not_called()

    async def test_process_qualitative_feedback_escalated_sentiment(self):
        """Test qualitative feedback with escalation due to negative sentiment."""
        self.agent._memory["conversation_stage"] = "asking_qualitative"
        self.mock_sentiment_analyzer.analyze_sentiment.return_value = {"label": "negative", "score": -0.8}
        self.agent._memory["feedback_session"]["session_id_to_rate"] = "test_session_escalated"
        
        response = await self.agent.process_input("This was an absolutely terrible experience.", {})
        self.assertTrue(self.agent.current_memory["feedback_session"]["escalated_for_review"])
        self.assertIn("Your feedback has been escalated for immediate human review", response["response_text"])
        self.assertEqual(response["action"], "feedback_escalated")
        self.mock_human_review_system.escalate_feedback.assert_called_once()

    async def test_process_qualitative_feedback_escalated_keyword(self):
        """Test qualitative feedback with escalation due to trigger keyword."""
        self.agent._memory["conversation_stage"] = "asking_qualitative"
        self.mock_sentiment_analyzer.analyze_sentiment.return_value = {"label": "neutral", "score": 0.1} # Not negative enough on its own
        self.agent._memory["feedback_session"]["session_id_to_rate"] = "test_session_keyword"
        
        response = await self.agent.process_input("The system was completely broken.", {})
        self.assertTrue(self.agent.current_memory["feedback_session"]["escalated_for_review"])
        self.assertIn("Your feedback has been escalated for immediate human review", response["response_text"])
        self.assertEqual(response["action"], "feedback_escalated")
        self.mock_human_review_system.escalate_feedback.assert_called_once()
    
    async def test_request_feedback_externally(self):
        """Test scheduling of external feedback request."""
        # Use the new async method to allow testing of async mock call
        await self.agent.request_feedback_externally_async("external_session", {"email": "test@example.com"})
        self.mock_task_scheduler.schedule_task.assert_called_once()
        args, kwargs = self.mock_task_scheduler.schedule_task.call_args
        self.assertEqual(args[0], "request_feedback")
        self.assertIsInstance(args[1], datetime.datetime) # due_time
        self.assertEqual(kwargs["payload"]["session_id"], "external_session")

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["feedback_session"]["nps_score"] = 5
        self.agent._memory["conversation_stage"] = "processing_feedback"
        
        self.agent.reset_memory()
        
        self.assertIsNone(self.agent.current_memory["feedback_session"]["nps_score"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "waiting_for_trigger")

if __name__ == '__main__':
    unittest.main()