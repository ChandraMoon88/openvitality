import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.medical.general_practitioner_agent import GeneralPractitionerAgent
from src.agents.base_agent import BaseAgent

class TestGeneralPractitionerAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        # FIX: Use AsyncMock for nlu_engine because the agent awaits process_text
        self.mock_nlu_engine = AsyncMock()
        self.mock_rag_orchestrator = AsyncMock()
        
        self.agent = GeneralPractitionerAgent(
            nlu_engine=self.mock_nlu_engine,
            rag_orchestrator=self.mock_rag_orchestrator
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for mocks
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "general_inquiry"}}
        self.mock_rag_orchestrator.query.return_value = {"answer": "General medical advice.", "citation": "Mock Source."}

    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "GeneralPractitionerAgent")
        self.assertIn("patient_history", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertEqual(self.agent.current_memory["patient_history"]["symptoms"], [])
        self.assertEqual(len(self.agent.history_questions), 6)

    async def test_process_input_greeting_to_history_taking(self):
        """Test transition from greeting to history_taking stage."""
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("Hello, I need some medical advice.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "history_taking")
        self.assertEqual(self.agent.current_memory["current_question_index"], 1) # First question asked
        self.assertIn(self.agent.history_questions[0], response["response_text"])
        self.assertEqual(response["action"], "ask_question")

    async def test_process_input_full_history_taking_and_advice_self_care(self):
        """Test full history taking leading to self-care advice."""
        context = {"user_id": "test_user"}

        # Simulate initial greeting
        await self.agent.process_input("Hello", context)

        # Q0: Symptoms
        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "SYMPTOM", "text": "mild headache"}], "intent": {}}
        await self.agent.process_input("I have a mild headache.", context)
        self.assertEqual(self.agent.current_memory["patient_history"]["symptoms"], ["mild headache"])

        # Q1: Duration
        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "DURATION", "text": "2 days"}], "intent": {}}
        await self.agent.process_input("It started 2 days ago.", context)
        self.assertEqual(self.agent.current_memory["patient_history"]["duration"], "2 days")

        # Q2: Severity
        await self.agent.process_input("It's a 3 out of 10.", context)
        self.assertEqual(self.agent.current_memory["patient_history"]["severity"], 3)

        # Q3: Chronic conditions/meds
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {}}
        await self.agent.process_input("No, none.", context)

        # Q4: Pregnancy
        await self.agent.process_input("No, I'm not pregnant.", context)
        self.assertFalse(self.agent.current_memory["patient_history"]["risk_factors"]["pregnancy"])

        # Q5: Remedies (triggers advice)
        response = await self.agent.process_input("No, haven't tried anything.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "advising")
        self.assertIn("For self-care, focus on rest, hydration", response["response_text"])
        self.assertEqual(response["action"], "suggest_self_care")
        self.mock_rag_orchestrator.query.assert_called_once()


    async def test_process_input_full_history_taking_and_advice_doctor_visit(self):
        """Test full history taking leading to doctor visit recommendation."""
        context = {"user_id": "test_user"}

        await self.agent.process_input("Hello", context)

        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "SYMPTOM", "text": "severe stomach pain"}], "intent": {}}
        await self.agent.process_input("I have severe stomach pain.", context)

        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "DURATION", "text": "1 day"}], "intent": {}}
        await self.agent.process_input("It started yesterday.", context)

        await self.agent.process_input("It's an 8 out of 10.", context) # Severity 8
        self.assertEqual(self.agent.current_memory["patient_history"]["severity"], 8)

        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {}}
        await self.agent.process_input("No other conditions.", context)

        await self.agent.process_input("No.", context)

        response = await self.agent.process_input("No medication.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "advising")
        self.assertIn("highly recommend you see a doctor as soon as possible", response["response_text"])
        self.assertEqual(response["action"], "recommend_doctor_visit")

    async def test_process_input_full_history_taking_and_advice_emergency_care(self):
        """Test full history taking leading to emergency care recommendation."""
        context = {"user_id": "test_user"}

        await self.agent.process_input("Hello", context)

        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "SYMPTOM", "text": "sudden difficulty breathing"}], "intent": {}}
        await self.agent.process_input("I have sudden difficulty breathing.", context)

        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "DURATION", "text": "10 minutes"}], "intent": {}}
        await self.agent.process_input("It just started 10 minutes ago.", context)

        await self.agent.process_input("It's a 9 out of 10.", context)

        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {}}
        await self.agent.process_input("No.", context)

        await self.agent.process_input("No.", context)

        response = await self.agent.process_input("No medication.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "advising")
        self.assertIn("These are red flag symptoms. Please seek immediate medical attention", response["response_text"])
        self.assertEqual(response["action"], "recommend_emergency_care")

    async def test_process_input_full_history_taking_and_advice_otc_meds(self):
        """Test full history taking leading to OTC medication suggestion."""
        context = {"user_id": "test_user"}

        await self.agent.process_input("Hello", context)

        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "SYMPTOM", "text": "fever"}], "intent": {}}
        await self.agent.process_input("I have a fever.", context)

        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "DURATION", "text": "4 days"}], "intent": {}}
        await self.agent.process_input("It started 4 days ago.", context)

        await self.agent.process_input("It's a 5 out of 10.", context) # Severity 5
        self.assertEqual(self.agent.current_memory["patient_history"]["severity"], 5)

        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {}}
        await self.agent.process_input("No other conditions.", context)

        await self.agent.process_input("No.", context)

        response = await self.agent.process_input("No medication.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "advising")
        self.assertIn("consider over-the-counter pain relievers like ibuprofen or paracetamol", response["response_text"])
        self.assertEqual(response["action"], "suggest_otc_meds")

    async def test_handle_follow_up_questions(self):
        """Test handling follow-up questions during advising phase."""
        context = {"user_id": "test_user"}
        self.agent._memory["conversation_stage"] = "advising"
        self.agent._memory["patient_history"]["symptoms"] = ["headache"]

        self.mock_rag_orchestrator.query.return_value = {"answer": "Some side effects.", "citation": "Drug Info."}
        response = await self.agent.process_input("What are the side effects of ibuprofen?", context)
        self.assertIn("Some side effects.", response["response_text"])
        self.assertEqual(response["action"], "answer_question")
        self.mock_rag_orchestrator.query.assert_called_once()
        self.assertIn("User asks: 'What are the side effects of ibuprofen?'. Context of previous advice", self.mock_rag_orchestrator.query.call_args[0][0])

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["patient_history"]["symptoms"] = ["fever"]
        self.agent._memory["patient_history"]["duration"] = "1 day"
        self.agent._memory["conversation_stage"] = "advising"
        self.agent._memory["current_question_index"] = 3
        
        self.agent.reset_memory()
        
        self.assertEqual(self.agent.current_memory["patient_history"]["symptoms"], [])
        self.assertEqual(self.agent.current_memory["patient_history"]["duration"], None)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertEqual(self.agent.current_memory["current_question_index"], 0)

if __name__ == '__main__':
    unittest.main()