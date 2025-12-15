import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.medical.lab_results_agent import LabResultsAgent
from src.agents.base_agent import BaseAgent 

class TestLabResultsAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        self.mock_nlu_engine = MagicMock()
        self.mock_medical_kg = MagicMock()
        
        self.agent = LabResultsAgent(
            nlu_engine=self.mock_nlu_engine,
            medical_kg=self.mock_medical_kg
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {}}

    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "LabResultsAgent")
        self.assertIn("patient_info", self.agent.current_memory)
        self.assertIn("previous_results", self.agent.current_memory)
        self.assertIn("current_lab_report", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "waiting_for_report")
        self.assertEqual(self.agent.current_memory["patient_info"], {"age": None, "gender": None})

    async def test_process_input_waiting_for_report_to_processing_report(self):
        """Test transition from waiting_for_report to processing_report."""
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("I want to upload my lab results.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "processing_report")
        self.assertIn("Please provide your lab results.", response["response_text"])
        self.assertEqual(response["action"], "request_lab_data")

    async def test_process_input_waiting_for_report_clarify(self):
        """Test clarification in waiting_for_report stage for irrelevant input."""
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("Hello there!", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "waiting_for_report")
        self.assertIn("To help you, please tell me you want to upload or discuss lab results.", response["response_text"])
        self.assertEqual(response["action"], "clarify_lab")

    async def test_extract_results_from_text(self):
        """Test extraction of lab results from unstructured text."""
        report_text = """
        Patient: John Doe
        Hemoglobin: 14.2 g/dL
        Glucose: 88 mg/dL (fasting)
        WBC: 6.5 x 10^3/uL
        Creatinine: 1.1 mg/dL
        TSH: 2.5 mIU/L
        """
        expected_results = [
            {"test_name": "Hemoglobin", "value": 14.2, "unit": "g/dL"},
            {"test_name": "Glucose", "value": 88.0, "unit": "mg/dL"},
            {"test_name": "WBC", "value": 6.5, "unit": "x 10^3/uL"},
            {"test_name": "Creatinine", "value": 1.1, "unit": "mg/dL"},
            {"test_name": "TSH", "value": 2.5, "unit": "mIU/L"},
        ]
        extracted = self.agent._extract_results_from_text(report_text)
        self.assertEqual(len(extracted), len(expected_results))
        for expected in expected_results:
            self.assertIn(expected, extracted)

    async def test_get_reference_range(self):
        """Test retrieval of reference ranges."""
        self.mock_medical_kg.get_reference_range.return_value = (13.5, 17.5, "g/dL")
        lower, upper, unit = self.agent._get_reference_range("Hemoglobin", 30, "male")
        self.assertEqual(lower, 13.5)
        self.assertEqual(upper, 17.5)
        self.assertEqual(unit, "g/dL")

        lower, upper, unit = self.agent._get_reference_range("Glucose", None, None)
        self.assertEqual(lower, 70.0)
        self.assertEqual(upper, 99.0)
        self.assertEqual(unit, "mg/dL")

    async def test_process_and_explain_results_normal(self):
        """Test processing and explanation for normal lab results."""
        context = {"user_id": "test_user", "patient_age": 30, "patient_gender": "female"}
        report_text = "Hemoglobin: 13.0 g/dL, Glucose: 90 mg/dL"
        self.agent._memory["conversation_stage"] = "processing_report" # Set stage for processing

        response = await self.agent.process_input(report_text, context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "explaining_results")
        
        # FIX: Check for key phrases individually to be robust against sentence structure
        self.assertIn("Hemoglobin level is 13.0 g/dL", response["response_text"])
        self.assertIn("within the normal range", response["response_text"])
        self.assertIn("Glucose level is 90.0 mg/dL", response["response_text"])
        
        self.assertFalse(response["context_update"]["red_flags_detected"])
        self.assertIn("All results appear within normal limits", response["response_text"])
        self.assertEqual(response["action"], "explain_results")

    async def test_process_and_explain_results_low(self):
        """Test processing and explanation for low lab results."""
        context = {"user_id": "test_user", "patient_age": 30, "patient_gender": "female"}
        report_text = "Hemoglobin: 10.0 g/dL" # Low for female (12.0-15.5)
        self.agent._memory["conversation_stage"] = "processing_report"

        response = await self.agent.process_input(report_text, context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "explaining_results")
        
        # FIX: Check for key phrases individually
        self.assertIn("Hemoglobin level is 10.0 g/dL", response["response_text"])
        self.assertIn("lower than normal", response["response_text"])
        self.assertIn("suggests anemia", response["response_text"])
        self.assertIn("Discuss with your doctor", response["response_text"])
        
        self.assertFalse(response["context_update"]["red_flags_detected"])

    async def test_process_and_explain_results_high(self):
        """Test processing and explanation for high lab results."""
        context = {"user_id": "test_user", "patient_age": 30, "patient_gender": "male"}
        report_text = "Glucose: 150 mg/dL" # High for normal (70.0-99.0)
        self.agent._memory["conversation_stage"] = "processing_report"

        response = await self.agent.process_input(report_text, context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "explaining_results")
        
        # FIX: Check for key phrases individually
        self.assertIn("Glucose level is 150.0 mg/dL", response["response_text"])
        self.assertIn("higher than normal", response["response_text"])
        self.assertIn("can indicate hyperglycemia", response["response_text"])
        
        self.assertFalse(response["context_update"]["red_flags_detected"])

    async def test_process_and_explain_results_critical_high_glucose(self):
        """Test detection and alert for critically high glucose."""
        context = {"user_id": "test_user", "patient_age": 40, "patient_gender": "male"}
        report_text = "Glucose: 450 mg/dL" # Critical high (>400)
        self.agent._memory["conversation_stage"] = "processing_report"

        response = await self.agent.process_input(report_text, context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "explaining_results")
        self.assertIn("CRITICAL ALERT: Glucose is dangerously high (450.0 mg/dL). Seek immediate medical attention.", response["response_text"])
        self.assertTrue(response["context_update"]["red_flags_detected"])

    async def test_process_and_explain_results_critical_low_glucose(self):
        """Test detection and alert for critically low glucose."""
        context = {"user_id": "test_user", "patient_age": 40, "patient_gender": "female"}
        report_text = "Glucose: 40 mg/dL" # Critical low (<50)
        self.agent._memory["conversation_stage"] = "processing_report"

        response = await self.agent.process_input(report_text, context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "explaining_results")
        self.assertIn("CRITICAL ALERT: Glucose is dangerously low (40.0 mg/dL). Seek immediate medical attention.", response["response_text"])
        self.assertTrue(response["context_update"]["red_flags_detected"])

    async def test_handle_follow_up_questions(self):
        """Test handling of follow-up questions."""
        context = {"user_id": "test_user", "patient_age": 30, "patient_gender": "female"}
        # Simulate initial processing to populate current_lab_report
        self.agent._process_and_explain_results("Hemoglobin: 13.0 g/dL", context, self.mock_nlu_engine.process_text("", {}))
        self.agent._memory["conversation_stage"] = "explaining_results"

        response = await self.agent.process_input("What does Hemoglobin mean?", context)
        self.assertIn("Your Hemoglobin level of 13.0 g/dL means that it is within the normal range", response["response_text"])
        self.assertEqual(response["action"], "answer_question")

        response = await self.agent.process_input("What does something else mean?", context)
        self.assertIn("Which specific test or term would you like me to explain?", response["response_text"])

    async def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["patient_info"]["age"] = 40
        self.agent._memory["previous_results"]["Hemoglobin"] = [{"value": 12.0}]
        self.agent._memory["current_lab_report"]["Glucose"] = {"value": 90}
        self.agent._memory["conversation_stage"] = "explaining_results"
        
        self.agent.reset_memory()
        
        self.assertEqual(self.agent.current_memory["patient_info"], {"age": None, "gender": None})
        self.assertEqual(self.agent.current_memory["previous_results"], {})
        self.assertEqual(self.agent.current_memory["current_lab_report"], {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "waiting_for_report")

if __name__ == '__main__':
    unittest.main()