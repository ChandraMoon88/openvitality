import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.medical.triage_agent import TriageAgent, TriageLevel
from src.agents.base_agent import BaseAgent

class TestTriageAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        self.mock_nlu_engine = MagicMock()
        self.mock_emergency_router = MagicMock()
        
        self.agent = TriageAgent(
            nlu_engine=self.mock_nlu_engine,
            emergency_router=self.mock_emergency_router
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "general_symptom"}}

    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "TriageAgent")
        self.assertIn("reported_symptoms", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["triage_state"], "initial")
        self.assertEqual(self.agent.triage_questions[0], "What brings you here today? Please describe your main concern.")
        self.assertIn("chest pain", self.agent.red_flags)

    async def test_process_input_red_flag_detection(self):
        """Test immediate RED triage and escalation on detecting red flags."""
        context = {"user_id": "test_user", "country_code": "US", "call_id": "test_call"}
        self.mock_emergency_router.escalate_emergency_call = AsyncMock()

        response = await self.agent.process_input("I have crushing chest pain and I can't breathe!", context)
        self.assertIn("medical emergency", response["response_text"])
        self.assertEqual(response["action"], "dial_emergency_services")
        self.assertEqual(response["context_update"]["triage_level"], TriageLevel.RED.name)
        # Now both should be true because the agent scans all flags
        self.assertTrue(self.agent.current_memory["urgency_factors"]["chest pain"])
        self.assertTrue(self.agent.current_memory["urgency_factors"]["breathing difficulty"])
        self.mock_emergency_router.escalate_emergency_call.assert_called_once_with(
            context.get("call_id"), context.get("country_code"), context.get("caller_location")
        )

    async def test_process_input_structured_questioning_flow_green(self):
        """Test the full structured questioning flow leading to GREEN triage."""
        context = {"user_id": "test_user"}

        # Question 0: Initial concern
        # FIX: Set up NLU response for this specific call to ensure symptom is recorded
        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "SYMPTOM", "text": "mild headache"}], "intent": {}}
        response = await self.agent.process_input("I have a mild headache.", context)
        self.assertIn(self.agent.triage_questions[1], response["response_text"]) # Asks Q1
        self.assertEqual(self.agent.current_memory["current_question_index"], 1)
        self.assertIn("mild headache", self.agent.current_memory["reported_symptoms"])

        # Question 1: When did symptoms start?
        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "DURATION", "text": "yesterday"}], "intent": {}}
        response = await self.agent.process_input("They started yesterday.", context)
        self.assertIn(self.agent.triage_questions[2], response["response_text"]) # Asks Q2
        self.assertEqual(self.agent.current_memory["current_question_index"], 2)
        self.assertEqual(self.agent.current_memory["urgency_factors"]["duration"], "yesterday")

        # Question 2: Severity
        response = await self.agent.process_input("The discomfort is about a 2.", context)
        self.assertIn(self.agent.triage_questions[3], response["response_text"]) # Asks Q3
        self.assertEqual(self.agent.current_memory["current_question_index"], 3)
        self.assertEqual(self.agent.current_memory["urgency_factors"]["severity"], 2)

        # Question 3: Other symptoms
        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "SYMPTOM", "text": "fatigue"}], "intent": {}}
        response = await self.agent.process_input("Just some fatigue.", context)
        self.assertIn(self.agent.triage_questions[4], response["response_text"]) # Asks Q4
        self.assertEqual(self.agent.current_memory["current_question_index"], 4)
        self.assertIn("fatigue", self.agent.current_memory["reported_symptoms"])

        # Question 4: Medication (Final question, should trigger decision)
        response = await self.agent.process_input("No, I haven't taken anything.", context)
        self.assertIn("We recommend scheduling a routine appointment", response["response_text"])
        self.assertEqual(response["context_update"]["triage_level"], TriageLevel.GREEN.name)
        self.assertEqual(response["action"], "suggest_routine_appointment")
        self.assertEqual(self.agent.current_memory["current_question_index"], 4) # Should not increment past max

    async def test_process_input_structured_questioning_flow_orange(self):
        """Test the full structured questioning flow leading to ORANGE triage."""
        context = {"user_id": "test_user"}

        # Simulate answers to lead to ORANGE decision
        await self.agent.process_input("I have severe abdominal pain.", context)
        await self.agent.process_input("It started an hour ago.", context)
        response = await self.agent.process_input("The pain is an 8.", context) # Severity 8
        self.agent._memory["current_question_index"] = 3 # Manually advance to bypass next question
        self.agent._process_answer("The pain is an 8.", self.mock_nlu_engine.process_text("", {}), 2) # Process severity
        self.assertEqual(self.agent.current_memory["urgency_factors"]["severity"], 8)

        response = await self.agent.process_input("No other symptoms, just the pain.", context) # Answer Q3
        self.agent._memory["current_question_index"] = 4
        self.agent._process_answer("No other symptoms, just the pain.", self.mock_nlu_engine.process_text("", {}), 3) # Process Q3

        response = await self.agent.process_input("No medication.", context) # Answer Q4, triggers decision
        self.assertIn("Your symptoms indicate an urgent concern that requires immediate medical attention", response["response_text"])
        self.assertEqual(response["context_update"]["triage_level"], TriageLevel.ORANGE.name)
        self.assertEqual(response["action"], "suggest_er_visit")
    
    async def test_process_input_structured_questioning_flow_yellow(self):
        """Test the full structured questioning flow leading to YELLOW triage."""
        context = {"user_id": "test_user"}

        # Simulate answers to lead to YELLOW decision
        await self.agent.process_input("I have a persistent cough.", context)
        await self.agent.process_input("It started 3 days ago.", context)
        response = await self.agent.process_input("The severity is about a 6.", context) # Severity 6
        self.agent._memory["current_question_index"] = 3
        self.agent._process_answer("The severity is about a 6.", self.mock_nlu_engine.process_text("", {}), 2)
        self.assertEqual(self.agent.current_memory["urgency_factors"]["severity"], 6)

        response = await self.agent.process_input("No other major issues.", context)
        self.agent._memory["current_question_index"] = 4
        self.agent._process_answer("No other major issues.", self.mock_nlu_engine.process_text("", {}), 3)

        response = await self.agent.process_input("I've taken some cough syrup.", context) # Answer Q4, triggers decision
        self.assertIn("We recommend seeing a doctor within the next hour", response["response_text"])
        self.assertEqual(response["context_update"]["triage_level"], TriageLevel.YELLOW.name)
        self.assertEqual(response["action"], "suggest_urgent_care")

    async def test_process_input_structured_questioning_flow_blue(self):
        """Test the full structured questioning flow leading to BLUE triage."""
        context = {"user_id": "test_user"}

        # Simulate answers to lead to BLUE decision
        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "SYMPTOM", "text": "mild rash"}], "intent": {}}
        await self.agent.process_input("I have a mild rash.", context)
        await self.agent.process_input("It appeared an hour ago.", context)
        response = await self.agent.process_input("It's a 1 on a scale of 10.", context) # Severity 1
        self.agent._memory["current_question_index"] = 3
        self.agent._process_answer("It's a 1 on a scale of 10.", self.mock_nlu_engine.process_text("", {}), 2)
        self.assertEqual(self.agent.current_memory["urgency_factors"]["severity"], 1)

        response = await self.agent.process_input("No other symptoms.", context)
        self.agent._memory["current_question_index"] = 4
        self.agent._process_answer("No other symptoms.", self.mock_nlu_engine.process_text("", {}), 3)

        response = await self.agent.process_input("No.", context) # Answer Q4, triggers decision
        self.assertIn("Your symptoms appear to be minor and can likely be managed with self-care", response["response_text"])
        self.assertEqual(response["context_update"]["triage_level"], TriageLevel.BLUE.name)
        self.assertEqual(response["action"], "suggest_self_care")

    def test_get_emergency_response_us(self):
        """Test US emergency response."""
        response = self.agent._get_emergency_response("US")
        self.assertIn("911", response)

    def test_get_emergency_response_india(self):
        """Test India emergency response."""
        response = self.agent._get_emergency_response("IN")
        self.assertIn("108", response)

    def test_get_emergency_response_gb(self):
        """Test UK emergency response."""
        response = self.agent._get_emergency_response("GB")
        self.assertIn("999", response)

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["triage_state"] = "asking_severity"
        self.agent._memory["reported_symptoms"] = ["cough"]
        self.agent._memory["urgency_factors"] = {"severity": 5}
        self.agent._memory["question_history"] = ["Q0", "Q1"]
        self.agent._memory["current_question_index"] = 2
        
        self.agent.reset_memory()
        
        self.assertEqual(self.agent.current_memory["triage_state"], "initial")
        self.assertEqual(self.agent.current_memory["reported_symptoms"], [])
        self.assertEqual(self.agent.current_memory["urgency_factors"], {})
        self.assertEqual(self.agent.current_memory["question_history"], [])
        self.assertEqual(self.agent.current_memory["current_question_index"], 0)

if __name__ == '__main__':
    unittest.main()