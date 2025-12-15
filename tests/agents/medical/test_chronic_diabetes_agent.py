import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import re
import statistics
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.medical.chronic_diabetes_agent import ChronicDiabetesAgent

class TestChronicDiabetesAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        self.mock_nlu_engine = AsyncMock()
        self.mock_task_scheduler = AsyncMock() # Changed to AsyncMock
        
        # Add mock methods to task_scheduler
        self.mock_task_scheduler.schedule_daily_reminder = AsyncMock()
        self.mock_task_scheduler.schedule_annual_reminder = AsyncMock()
        self.agent = ChronicDiabetesAgent(
            nlu_engine=self.mock_nlu_engine,
            task_scheduler=self.mock_task_scheduler
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "diabetes_query"}}

    def test_initialization(self):
        """Test correct initialization of agent properties, memory, and thresholds."""
        self.assertEqual(self.agent.name, "ChronicDiabetesAgent")
        self.assertIn("glucose_readings", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertEqual(self.agent.hypo_threshold, 70)
        self.assertEqual(self.agent.hyper_threshold, 250)

    async def test_process_input_greeting_to_main_menu(self):
        """Test transition from greeting to main_menu."""
        response = await self.agent.process_input("Hello", {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertIn("manage your diabetes", response["response_text"])
        self.assertEqual(response["action"], "prompt_main_menu")

    async def test_process_input_main_menu_log_glucose(self):
        """Test transition to logging_glucose from main_menu."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Log glucose.", {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "logging_glucose")
        self.assertIn("Please tell me your glucose reading", response["response_text"])
        self.assertEqual(response["action"], "ask_glucose")

    async def test_process_input_main_menu_trends(self):
        """Test trigger for glucose trends from main_menu."""
        self.agent._memory["conversation_stage"] = "main_menu"
        # Populate with some data to avoid "no data" response
        self.agent._memory["glucose_readings"].append({"timestamp": datetime.datetime.now(), "type": "fasting", "value": 100})
        
        response = await self.agent.process_input("Show me my trends.", {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertIn("average glucose reading", response["response_text"])
        self.assertEqual(response["action"], "display_trends")

    async def test_log_glucose_reading_normal(self):
        """Test logging a normal glucose reading."""
        self.agent._memory["conversation_stage"] = "logging_glucose"
        response = await self.agent.process_input("My fasting glucose was 120.", {})
        self.assertIn("Logged your fasting glucose reading of 120 mg/dL.", response["response_text"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertEqual(len(self.agent.current_memory["glucose_readings"]), 1)
        self.assertEqual(self.agent.current_memory["glucose_readings"][0]["value"], 120)
        self.assertEqual(response["action"], "glucose_logged")

    async def test_log_glucose_reading_hypoglycemic(self):
        """Test logging a hypoglycemic reading."""
        self.agent._memory["conversation_stage"] = "logging_glucose"
        response = await self.agent.process_input("My sugar was 60.", {})
        self.assertIn("This is a low blood sugar (hypoglycemic) reading.", response["response_text"])
        self.assertEqual(response["action"], "alert_hypoglycemia")

    async def test_log_glucose_reading_hyperglycemic(self):
        """Test logging a hyperglycemic reading."""
        self.agent._memory["conversation_stage"] = "logging_glucose"
        response = await self.agent.process_input("Glucose reading: 260.", {})
        self.assertIn("This is a high blood sugar (hyperglycemic) reading.", response["response_text"])
        self.assertEqual(response["action"], "alert_hyperglycemia")

    async def test_log_glucose_reading_invalid_value(self):
        """Test handling of invalid glucose value."""
        self.agent._memory["conversation_stage"] = "logging_glucose"
        response = await self.agent.process_input("My sugar was high.", {})
        self.assertIn("I couldn't find a clear glucose reading", response["response_text"])
        self.assertEqual(response["action"], "ask_glucose_retry")
        self.assertEqual(len(self.agent.current_memory["glucose_readings"]), 0)

    async def test_provide_glucose_trends_no_data(self):
        """Test trends when no data is available."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Show trends.", {})
        self.assertIn("I don't have enough glucose readings to provide trends.", response["response_text"])
        self.assertEqual(response["action"], "no_data")

    async def test_provide_glucose_trends_with_data(self):
        """Test trends with sufficient data."""
        self.agent._memory["conversation_stage"] = "main_menu"
        for i in range(35): # Enough for 30 and 90 day trends
            self.agent._memory["glucose_readings"].append({
                "timestamp": datetime.datetime.now() - datetime.timedelta(days=i), 
                "type": "fasting", 
                "value": 100 + i
            })
        
        response = await self.agent.process_input("What are my glucose trends?", {})
        self.assertIn("Over the last 30 days, your average glucose reading is", response["response_text"])
        self.assertIn("Over the last 90 days, your average glucose reading is", response["response_text"])
        self.assertEqual(response["action"], "display_trends")

    async def test_estimate_a1c_no_data(self):
        """Test A1C estimation with insufficient data."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Estimate A1C.", {})
        self.assertIn("I need at least two weeks of glucose readings", response["response_text"])
        self.assertEqual(response["action"], "no_a1c_data")

    async def test_estimate_a1c_with_data(self):
        """Test A1C estimation with sufficient data."""
        self.agent._memory["conversation_stage"] = "main_menu"
        for i in range(15): # Enough for A1C
            self.agent._memory["glucose_readings"].append({
                "timestamp": datetime.datetime.now() - datetime.timedelta(days=i), 
                "type": "fasting", 
                "value": 120 + i
            })
        
        response = await self.agent.process_input("Estimate A1C.", {})
        self.assertIn("estimated A1C is approximately", response["response_text"])
        self.assertEqual(response["action"], "display_a1c")
        self.assertGreater(len(self.agent.current_memory["a1c_estimates"]), 0)

    async def test_provide_diet_advice(self):
        """Test diet advice provision."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Give me diet advice.", {})
        self.assertIn("For diabetes management, focusing on balanced meals", response["response_text"])
        self.assertEqual(response["action"], "display_advice")

    async def test_provide_exercise_advice(self):
        """Test exercise advice provision."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Exercise tips.", {})
        self.assertIn("Regular physical activity is vital for diabetes management.", response["response_text"])
        self.assertEqual(response["action"], "display_advice")

    async def test_provide_reminders_foot_check(self):
        """Test setting a foot check reminder."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Remind me about foot checks.", {})
        self.assertIn("Daily foot checks are crucial", response["response_text"])
        self.assertIsNotNone(self.agent.current_memory["last_foot_check_reminder"])
        self.mock_task_scheduler.schedule_daily_reminder.assert_called_once() # Assuming this method exists and is mocked

    async def test_provide_reminders_eye_exam(self):
        """Test setting an eye exam reminder."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Remind me about my eye exam.", {})
        self.assertIn("An annual dilated eye exam is essential", response["response_text"])
        self.assertIsNotNone(self.agent.current_memory["last_eye_exam_reminder"])
        self.mock_task_scheduler.schedule_annual_reminder.assert_called_once() # Assuming this method exists and is mocked

    async def test_provide_reminders_unrecognized(self):
        """Test reminders with unrecognized type."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Remind me to call mom.", {})
        self.assertIn("What kind of reminder are you looking for?", response["response_text"])
        self.assertEqual(response["action"], "display_reminders")


    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["glucose_readings"].append({"value": 100})
        self.agent._memory["conversation_stage"] = "logging_glucose"
        
        self.agent.reset_memory()
        
        self.assertEqual(self.agent.current_memory["glucose_readings"], [])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")

if __name__ == '__main__':
    unittest.main()