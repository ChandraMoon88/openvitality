import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import re
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.medical.cardiologist_agent import CardiologistAgent

class TestCardiologistAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        self.mock_nlu_engine = AsyncMock()
        self.mock_emergency_router = AsyncMock()
        
        self.agent = CardiologistAgent(
            nlu_engine=self.mock_nlu_engine,
            emergency_router=self.mock_emergency_router
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "heart_health_query"}}

    def test_initialization(self):
        """Test correct initialization of agent properties, memory, and red flags."""
        self.assertEqual(self.agent.name, "CardiologistAgent")
        self.assertIn("cardiac_history", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertIn("crushing chest pain", self.agent.cardiac_red_flags["crushing chest pain"])

    async def test_process_input_red_flag_first(self):
        """Test that cardiac red flags are checked first."""
        context = {"call_id": "c1", "country_code": "US", "caller_location": {}}
        response = await self.agent.process_input("I have crushing chest pain!", context)
        self.assertEqual(response["action"], "dial_emergency_services")
        self.mock_emergency_router.escalate_emergency_call.assert_called_once_with(
            "c1", "US", {}
        )

    async def test_process_input_greeting_to_risk_assessment(self):
        """Test transition from greeting to risk_assessment."""
        response = await self.agent.process_input("Hello, I want to discuss my heart health.", {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "risk_assessment")
        self.assertIn("age and gender", response["response_text"])
        self.assertEqual(response["action"], "ask_question")

    async def test_process_input_risk_assessment_to_coaching(self):
        """Test transition from risk_assessment to coaching after all questions."""
        self.agent._memory["conversation_stage"] = "risk_assessment"
        self.agent._memory["current_question_index"] = len(self.agent.risk_assessment_questions) # Simulate all questions asked
        
        response = await self.agent.process_input("No, no family history.", {}) # Last answer
        self.assertEqual(self.agent.current_memory["conversation_stage"], "coaching")
        self.assertIn("Thank you for providing that information.", response["response_text"])
        self.assertEqual(response["action"], "provide_guidance")

    async def test_check_cardiac_red_flags_detected(self):
        """Test detection of cardiac red flags and router escalation."""
        context = {"call_id": "c2", "country_code": "IN", "caller_location": {"lat": 1, "lon": 1}}
        # FIX: Updated input text to contain "crushing chest pain" to match assertion
        text = "I have crushing chest pain and shortness of breath."
        
        # FIX: Added await for async check method
        self.assertTrue(await self.agent._check_cardiac_red_flags(text, context))
        
        self.assertIn("crushing chest pain", self.agent.current_memory["cardiac_history"]["reported_symptoms"])
        self.assertIn("shortness of breath", self.agent.current_memory["cardiac_history"]["reported_symptoms"])
        self.mock_emergency_router.escalate_emergency_call.assert_called_once_with(
            "c2", "IN", {"lat": 1, "lon": 1}
        )

    async def test_check_cardiac_red_flags_not_detected(self):
        """Test when no cardiac red flags are present."""
        context = {"call_id": "c3", "country_code": "US", "caller_location": {}}
        text = "I have a headache."
        # FIX: Added await for async check method
        self.assertFalse(await self.agent._check_cardiac_red_flags(text, context))
        self.mock_emergency_router.escalate_emergency_call.assert_not_called()

    def test_get_emergency_response_us(self):
        """Test US specific emergency response."""
        response = self.agent._get_emergency_response("US")
        self.assertIn("911", response)

    def test_get_emergency_response_in(self):
        """Test India specific emergency response."""
        response = self.agent._get_emergency_response("IN")
        self.assertIn("108", response)

    def test_get_emergency_response_gb(self):
        """Test GB specific emergency response."""
        response = self.agent._get_emergency_response("GB")
        self.assertIn("999", response)

    def test_get_emergency_response_default(self):
        """Test default emergency response for unknown country."""
        response = self.agent._get_emergency_response("XX")
        self.assertIn("911", response) # Default is "911" in the method

    def test_ask_next_question(self):
        """Test that _ask_next_question returns the correct question."""
        self.agent._memory["current_question_index"] = 0
        response = self.agent._ask_next_question()
        self.assertEqual(response["response_text"], self.agent.risk_assessment_questions[0])
        self.assertEqual(self.agent.current_memory["current_question_index"], 1)

    async def test_process_risk_assessment_answer_age_gender(self):
        """Test processing age and gender."""
        # FIX: Added await
        await self.agent._process_risk_assessment_answer("I am 40 years old and female.", {}, 0)
        self.assertEqual(self.agent.current_memory["cardiac_history"]["age"], 40)
        self.assertEqual(self.agent.current_memory["cardiac_history"]["gender"], "female")

    async def test_process_risk_assessment_answer_blood_pressure(self):
        """Test processing blood pressure."""
        # FIX: Added await
        await self.agent._process_risk_assessment_answer("My BP is 120/80.", {}, 1)
        self.assertEqual(self.agent.current_memory["cardiac_history"]["blood_pressure"], "120/80")

    async def test_process_risk_assessment_answer_smoking_status(self):
        """Test processing smoking status."""
        # FIX: Added await
        await self.agent._process_risk_assessment_answer("I am a former smoker.", {}, 3)
        self.assertEqual(self.agent.current_memory["cardiac_history"]["smoking_status"], "former")

    async def test_process_risk_assessment_answer_diabetes(self):
        """Test processing diabetes diagnosis."""
        # FIX: Added await
        await self.agent._process_risk_assessment_answer("Yes, I have diabetes.", {}, 4)
        self.assertTrue(self.agent.current_memory["cardiac_history"]["diabetes"])

    async def test_process_risk_assessment_answer_family_history(self):
        """Test processing family history."""
        # FIX: Added await
        await self.agent._process_risk_assessment_answer("Yes, there is a family history.", {}, 5)
        self.assertTrue(self.agent.current_memory["cardiac_history"]["family_history_heart_disease"])

    async def test_provide_cardiac_guidance_hypertension(self):
        """Test guidance with hypertension detected."""
        self.agent._memory["cardiac_history"]["blood_pressure"] = "150/95"
        response = await self.agent._provide_cardiac_guidance({})
        self.assertIn("Your blood pressure readings suggest hypertension.", response["response_text"])
        self.assertIn("consult your cardiologist or GP", response["response_text"])

    async def test_provide_cardiac_guidance_normal_bp(self):
        """Test guidance with normal blood pressure."""
        self.agent._memory["cardiac_history"]["blood_pressure"] = "110/70"
        response = await self.agent._provide_cardiac_guidance({})
        self.assertIn("Your blood pressure appears to be within a healthy range.", response["response_text"])

    async def test_handle_coaching_follow_ups_diet(self):
        """Test follow-up on diet."""
        response = await self.agent._handle_coaching_follow_ups("Tell me about diet.", {}, {})
        self.assertIn("The DASH diet", response["response_text"])

    async def test_handle_coaching_follow_ups_exercise(self):
        """Test follow-up on exercise."""
        response = await self.agent._handle_coaching_follow_ups("What about exercise?", {}, {})
        self.assertIn("Aim for at least 150 minutes", response["response_text"])

    async def test_handle_coaching_follow_ups_other(self):
        """Test other follow-up questions."""
        response = await self.agent._handle_coaching_follow_ups("How old is the earth?", {}, {})
        self.assertIn("I can provide general information on heart health", response["response_text"])

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["cardiac_history"]["age"] = 60
        self.agent._memory["conversation_stage"] = "coaching"
        
        self.agent.reset_memory()
        
        self.assertIsNone(self.agent.current_memory["cardiac_history"]["age"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertListEqual(self.agent.current_memory["cardiac_history"]["reported_symptoms"], [])


if __name__ == '__main__':
    unittest.main()