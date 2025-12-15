import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.medical.pediatrician_agent import PediatricianAgent
from src.agents.base_agent import BaseAgent

class TestPediatricianAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        self.mock_nlu_engine = MagicMock()
        self.mock_emergency_router = MagicMock()
        
        self.agent = PediatricianAgent(
            nlu_engine=self.mock_nlu_engine,
            emergency_router=self.mock_emergency_router
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "general_query"}}

    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "PediatricianAgent")
        self.assertIn("child_profile", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertEqual(self.agent.current_memory["child_profile"]["age_years"], None)
        self.assertEqual(self.agent.child_info_questions[0], "How old is the child (years and months)?")
        self.assertIn("lethargy", self.agent.pediatric_red_flags)

    async def test_process_input_pediatric_red_flag_detection(self):
        """Test immediate escalation on detecting pediatric red flags."""
        context = {"user_id": "test_user", "country_code": "US", "caller_location": "Home"}
        # Mock emergency_router.escalate_emergency_call since it's an AsyncMock
        self.mock_emergency_router.escalate_emergency_call = AsyncMock()

        response = await self.agent.process_input("My baby is very lethargic and hard to wake!", context)
        self.assertIn("serious medical emergency", response["response_text"])
        self.assertEqual(response["action"], "dial_emergency_services")
        self.assertTrue(self.agent.current_memory["child_profile"]["risk_factors"]["lethargy"])
        self.mock_emergency_router.escalate_emergency_call.assert_called_once_with(
            context.get("call_id"), context.get("country_code"), context.get("caller_location")
        )

    async def test_process_input_greeting_to_child_info(self):
        """Test transition from greeting to child_info stage."""
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("My child has a fever.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "child_info")
        self.assertEqual(self.agent.current_memory["current_question_index"], 1) # First question asked
        self.assertIn("How old is the child (years and months)?", response["response_text"])
        self.assertEqual(response["action"], "ask_question")

    async def test_process_child_info_answer_age(self):
        """Test processing of child's age."""
        self.agent._memory["conversation_stage"] = "child_info"
        self.agent._memory["current_question_index"] = 1 # Simulate that first question was asked

        self.agent._process_child_info_answer("My child is 2 years and 3 months old.", self.mock_nlu_engine.process_text("", {}), 0)
        self.assertEqual(self.agent.current_memory["child_profile"]["age_years"], 2)
        self.assertEqual(self.agent.current_memory["child_profile"]["age_months"], 3)

        # Clear previous state to test new input isolation
        self.agent._memory["child_profile"]["age_years"] = None
        self.agent._memory["child_profile"]["age_months"] = None
        
        self.agent._process_child_info_answer("1 year old.", self.mock_nlu_engine.process_text("", {}), 0)
        self.assertEqual(self.agent.current_memory["child_profile"]["age_years"], 1)
        self.assertEqual(self.agent.current_memory["child_profile"]["age_months"], None) # Should remain None

    async def test_process_child_info_answer_weight(self):
        """Test processing of child's weight in kg and lbs."""
        self.agent._memory["conversation_stage"] = "child_info"
        self.agent._memory["current_question_index"] = 2 # Simulate that second question was asked

        self.agent._process_child_info_answer("She weighs 15 kg.", self.mock_nlu_engine.process_text("", {}), 1)
        self.assertEqual(self.agent.current_memory["child_profile"]["weight_kg"], 15.0)

        self.agent._process_child_info_answer("He is 22 pounds.", self.mock_nlu_engine.process_text("", {}), 1)
        self.assertAlmostEqual(self.agent.current_memory["child_profile"]["weight_kg"], 9.98, places=2) # 22 lbs * 0.453592 kg/lb

    async def test_process_child_info_answer_symptoms(self):
        """Test processing of child's symptoms."""
        self.agent._memory["conversation_stage"] = "child_info"
        self.agent._memory["current_question_index"] = 3 # Simulate that third question was asked
        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "SYMPTOM", "text": "fever"}, {"type": "SYMPTOM", "text": "cough"}], "intent": {}}

        self.agent._process_child_info_answer("They have a fever and a cough.", self.mock_nlu_engine.process_text("", {}), 2)
        self.assertIn("fever", self.agent.current_memory["child_profile"]["symptoms"])
        self.assertIn("cough", self.agent.current_memory["child_profile"]["symptoms"])
        self.assertEqual(len(self.agent.current_memory["child_profile"]["symptoms"]), 2)

    async def test_provide_pediatric_advice_fever_with_dosage(self):
        """Test general advice for fever including dosage calculation."""
        context = {"user_id": "test_user"}
        self.agent._memory["child_profile"]["age_years"] = 3
        self.agent._memory["child_profile"]["weight_kg"] = 15.0
        self.agent._memory["child_profile"]["symptoms"] = ["fever"]
        self.agent._memory["conversation_stage"] = "symptom_assessment" # Should transition to advising after this

        response = await self.agent.process_input("What should I do for a fever?", context)
        self.assertIn("For fever, ensure your child is comfortable", response["response_text"])
        # FIX: Added space "225 mg"
        self.assertIn("For Paracetamol, a typical single dose for a child weighing 15.0 kg is 225 mg", response["response_text"])
        self.assertEqual(response["action"], "provide_pediatric_advice")

    async def test_provide_pediatric_advice_fever_without_weight(self):
        """Test advice for fever without weight (no dosage)."""
        context = {"user_id": "test_user"}
        self.agent._memory["child_profile"]["age_years"] = 3
        self.agent._memory["child_profile"]["symptoms"] = ["fever"]
        self.agent._memory["conversation_stage"] = "symptom_assessment"

        response = await self.agent.process_input("What should I do for a fever?", context)
        self.assertIn("Without your child's weight, I cannot recommend specific medication dosages.", response["response_text"])
        self.assertNotIn("Paracetamol", response["response_text"])

    def test_calculate_dosage_paracetamol(self):
        """Test paracetamol dosage calculation."""
        self.agent._memory["child_profile"]["weight_kg"] = 10.0 # 10 kg child
        dosage_info = self.agent._calculate_dosage("paracetamol")
        # FIX: Added space in "150 mg" and "750 mg"
        self.assertIn("For Paracetamol, a typical single dose for a child weighing 10.0 kg is 150 mg", dosage_info)
        self.assertIn("Do not exceed 750 mg in a 24-hour period.", dosage_info) # Max daily mg for 10kg child (10*75)
        self.assertIn("this would be approximately 6.2 ml per dose.", dosage_info) # 150mg / (120mg/5ml) = 6.25ml

    def test_calculate_dosage_ibuprofen(self):
        """Test ibuprofen dosage calculation."""
        self.agent._memory["child_profile"]["weight_kg"] = 12.0 # 12 kg child
        dosage_info = self.agent._calculate_dosage("ibuprofen")
        # FIX: Added space in "120 mg" and "480 mg"
        self.assertIn("For Ibuprofen, a typical single dose for a child weighing 12.0 kg is 120 mg", dosage_info)
        self.assertIn("Do not exceed 480 mg in a 24-hour period.", dosage_info) # Max daily mg for 12kg child (12*40)
        self.assertIn("this would be approximately 6.0 ml per dose.", dosage_info) # 120mg / (100mg/5ml) = 6ml

    def test_calculate_dosage_without_weight(self):
        """Test dosage calculation without child's weight."""
        self.agent._memory["child_profile"]["weight_kg"] = None
        dosage_info = self.agent._calculate_dosage("paracetamol")
        self.assertIn("To provide a safe dosage for paracetamol, I critically need your child's weight", dosage_info)

    def test_calculate_dosage_unknown_medication(self):
        """Test dosage calculation for an unknown medication."""
        self.agent._memory["child_profile"]["weight_kg"] = 10.0
        dosage_info = self.agent._calculate_dosage("unknown_med")
        self.assertIn("I don't have dosage information for unknown_med.", dosage_info)

    async def test_handle_advising_follow_ups_dosage(self):
        """Test follow-up question for medication dosage."""
        context = {"user_id": "test_user"}
        self.agent._memory["child_profile"]["weight_kg"] = 10.0
        self.agent._memory["conversation_stage"] = "advising"
        response = await self.agent.process_input("What is the paracetamol dosage?", context)
        # FIX: Added space "150 mg"
        self.assertIn("For Paracetamol, a typical single dose for a child weighing 10.0 kg is 150 mg", response["response_text"])
        self.assertEqual(response["action"], "answer_question")

    async def test_handle_advising_follow_ups_milestone(self):
        """Test follow-up question for developmental milestones."""
        context = {"user_id": "test_user"}
        self.agent._memory["conversation_stage"] = "advising"
        response = await self.agent.process_input("Tell me about milestones.", context)
        self.assertIn("Tracking developmental milestones is important.", response["response_text"])
        self.assertEqual(response["action"], "answer_question")

    async def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["child_profile"]["age_years"] = 5
        self.agent._memory["child_profile"]["weight_kg"] = 20.0
        self.agent._memory["child_profile"]["symptoms"] = ["cough"]
        self.agent._memory["conversation_stage"] = "advising"
        self.agent._memory["current_question_index"] = 3
        
        self.agent.reset_memory()
        
        self.assertEqual(self.agent.current_memory["child_profile"]["age_years"], None)
        self.assertEqual(self.agent.current_memory["child_profile"]["weight_kg"], None)
        self.assertEqual(self.agent.current_memory["child_profile"]["symptoms"], [])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertEqual(self.agent.current_memory["current_question_index"], 0)

if __name__ == '__main__':
    unittest.main()