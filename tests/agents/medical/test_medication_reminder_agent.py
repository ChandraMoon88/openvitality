import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import sys
import os
import re

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.medical.medication_reminder_agent import MedicationReminderAgent
from src.agents.base_agent import BaseAgent

class TestMedicationReminderAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        self.mock_task_scheduler = AsyncMock()
        self.mock_drug_db = AsyncMock()
        self.mock_notification_service = AsyncMock()
        
        self.agent = MedicationReminderAgent(
            task_scheduler=self.mock_task_scheduler,
            drug_db=self.mock_drug_db,
            notification_service=self.mock_notification_service
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "MedicationReminderAgent")
        self.assertIn("medications", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertEqual(self.agent.current_memory["medications"], {})

    async def test_process_input_greeting_to_main_menu(self):
        """Test transition from greeting to main_menu."""
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("Hello", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertIn("How can I help you today?", response["response_text"])
        self.assertEqual(response["action"], "prompt_main_menu")

    async def test_process_input_main_menu_add_medication(self):
        """Test main_menu to adding_med transition."""
        self.agent._memory["conversation_stage"] = "main_menu"
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("Add new medication.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "adding_med")
        self.assertIn("what is the name of the medication", response["response_text"])
        self.assertEqual(response["action"], "ask_med_name")

    async def test_process_input_main_menu_review_schedule(self):
        """Test main_menu to reviewing_schedule (via _review_medication_schedule)."""
        self.agent._memory["conversation_stage"] = "main_menu"
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("Review my schedule.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu") # Stays in main menu after review
        self.assertIn("You currently don't have any medications scheduled", response["response_text"])
        self.assertEqual(response["action"], "offer_add_med")

    async def test_process_input_main_menu_report_side_effect(self):
        """Test main_menu to side_effect_monitoring transition."""
        self.agent._memory["conversation_stage"] = "main_menu"
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("Report a side effect.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "side_effect_monitoring")
        self.assertIn("What new symptoms or side effects are you experiencing?", response["response_text"])
        self.assertEqual(response["action"], "ask_side_effect")
    
    async def test_process_input_main_menu_confirm_taken(self):
        """Test main_menu to confirm_medication_taken."""
        self.agent._memory["conversation_stage"] = "main_menu"
        self.agent._memory["medications"]["ibuprofen"] = {"dosage": "200mg", "frequency": "every 6 hours", "last_taken": None, "next_due": None, "pills_left": None, "adherence_streak": 0}
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("I took my Ibuprofen.", context)
        self.assertEqual(self.agent.current_memory["medications"]["ibuprofen"]["adherence_streak"], 1)
        self.assertIn("I've noted that you've taken your ibuprofen", response["response_text"])
        self.assertEqual(response["action"], "confirm_adherence")

    async def test_add_medication_flow_success(self):
        """Test successful step-by-step addition of a medication."""
        context = {"user_id": "test_user"}
        self.agent._memory["conversation_stage"] = "adding_med"
        self.agent._memory["add_med_step"] = "name"
        self.mock_drug_db.check_interaction.return_value = None # No interaction

        # Step 1: Provide name
        response = await self.agent.process_input("Aspirin", context)
        self.assertEqual(self.agent.current_memory["add_med_step"], "dosage")
        self.assertIn("What is the dosage (e.g., '200mg', 'one pill')?", response["response_text"])

        # Step 2: Provide dosage
        response = await self.agent.process_input("81mg", context)
        self.assertEqual(self.agent.current_memory["add_med_step"], "frequency")
        self.assertIn("And how often should you take Aspirin?", response["response_text"])

        # Step 3: Provide frequency (completes adding)
        response = await self.agent.process_input("Once a day", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertIn("I've added Aspirin to your schedule.", response["response_text"])
        self.assertEqual(response["action"], "medication_added")
        self.assertIn("aspirin", self.agent.current_memory["medications"])
        self.mock_task_scheduler.schedule_task.assert_called_once()
        self.assertNotIn("new_med_info", self.agent.current_memory)
        self.assertNotIn("add_med_step", self.agent.current_memory)

    async def test_add_medication_flow_with_interaction_confirm(self):
        """Test adding medication with interaction, user confirms."""
        context = {"user_id": "test_user"}
        self.agent._memory["medications"]["ibuprofen"] = {"dosage": "200mg", "frequency": "every 6 hours", "last_taken": None, "next_due": None, "pills_left": None, "adherence_streak": 0}
        self.agent._memory["conversation_stage"] = "adding_med"
        self.agent._memory["add_med_step"] = "name"
        self.mock_drug_db.check_interaction.return_value = "Increased risk of bleeding." # Mock interaction

        # Follow steps to frequency
        await self.agent.process_input("Aspirin", context)
        await self.agent.process_input("81mg", context)
        response = await self.agent.process_input("Once a day", context) # Triggers interaction check

        self.assertEqual(self.agent.current_memory["add_med_step"], "confirm_add_with_warning")
        self.assertIn("a potential interaction with ibuprofen was detected", response["response_text"].lower()) # Lowercase to be safe
        self.assertEqual(response["action"], "confirm_add_with_warning")

        # User confirms to add despite warning
        response = await self.agent.process_input("Yes, add it anyway.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertIn("Aspirin has been added", response["response_text"])
        self.assertEqual(response["action"], "medication_added_with_warning")
        self.assertIn("aspirin", self.agent.current_memory["medications"])
        self.assertEqual(self.mock_task_scheduler.schedule_task.call_count, 1)

    async def test_add_medication_flow_with_interaction_cancel(self):
        """Test adding medication with interaction, user cancels."""
        context = {"user_id": "test_user"}
        self.agent._memory["medications"]["ibuprofen"] = {"dosage": "200mg", "frequency": "every 6 hours", "last_taken": None, "next_due": None, "pills_left": None, "adherence_streak": 0}
        self.agent._memory["conversation_stage"] = "adding_med"
        self.agent._memory["add_med_step"] = "name"
        self.mock_drug_db.check_interaction.return_value = "Increased risk of bleeding."

        # Follow steps to frequency, triggers warning
        await self.agent.process_input("Aspirin", context)
        await self.agent.process_input("81mg", context)
        await self.agent.process_input("Once a day", context) 

        # User cancels
        response = await self.agent.process_input("No, don't add it.", context)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertIn("Aspirin was not added.", response["response_text"])
        self.assertEqual(response["action"], "medication_not_added")
        self.assertNotIn("aspirin", self.agent.current_memory["medications"])

    async def test_review_medication_schedule_empty(self):
        """Test reviewing an empty medication schedule."""
        context = {"user_id": "test_user"}
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Review schedule", context)
        self.assertIn("You currently don't have any medications scheduled", response["response_text"])
        self.assertEqual(response["action"], "offer_add_med")

    async def test_review_medication_schedule_with_meds(self):
        """Test reviewing a medication schedule with existing meds."""
        context = {"user_id": "test_user"}
        self.agent._memory["medications"]["ibuprofen"] = {
            "dosage": "200mg",
            "frequency": "every 6 hours",
            "last_taken": datetime.datetime.now() - datetime.timedelta(hours=7),
            "next_due": datetime.datetime.now() - datetime.timedelta(hours=1), # Make it due soon for test
            "pills_left": 10,
            "adherence_streak": 5
        }
        self.agent._memory["medications"]["aspirin"] = {
            "dosage": "81mg",
            "frequency": "once a day",
            "last_taken": datetime.datetime.now() - datetime.timedelta(days=1),
            "next_due": datetime.datetime.now() + datetime.timedelta(hours=5),
            "pills_left": 30,
            "adherence_streak": 10
        }
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Review my meds", context)
        self.assertIn("Here is your current medication schedule:", response["response_text"])
        self.assertIn("Ibuprofen: 200mg every 6 hours.", response["response_text"])
        self.assertIn("Aspirin: 81mg once a day.", response["response_text"])
        self.assertIn("Your adherence streak is 5 days!", response["response_text"])
        self.assertIn("Your adherence streak is 10 days!", response["response_text"])
        self.assertEqual(response["action"], "display_schedule")

    async def test_confirm_medication_taken_success(self):
        """Test successful confirmation of medication taken."""
        context = {"user_id": "test_user"}
        self.agent._memory["medications"]["ibuprofen"] = {"dosage": "200mg", "frequency": "every 6 hours", "last_taken": None, "next_due": None, "pills_left": None, "adherence_streak": 0}
        self.agent._memory["conversation_stage"] = "main_menu" # Can confirm from main menu
        response = await self.agent.process_input("I took my Ibuprofen.", context)
        self.assertEqual(self.agent.current_memory["medications"]["ibuprofen"]["adherence_streak"], 1)
        self.assertIsNotNone(self.agent.current_memory["medications"]["ibuprofen"]["last_taken"])
        self.assertIsNotNone(self.agent.current_memory["medications"]["ibuprofen"]["next_due"])
        self.assertIn("I've noted that you've taken your ibuprofen", response["response_text"])
        self.assertEqual(response["action"], "confirm_adherence")
        self.mock_task_scheduler.schedule_task.assert_called_once()

    async def test_confirm_medication_taken_unknown_med(self):
        """Test confirmation for an unknown medication."""
        context = {"user_id": "test_user"}
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("I took my unknown pill.", context)
        self.assertIn("Which medication did you take? Please tell me the name.", response["response_text"])
        self.assertEqual(response["action"], "clarify_med_taken")

    async def test_report_side_effect_success(self):
        """Test successful reporting of a side effect."""
        context = {"user_id": "test_user"}
        self.agent._memory["medications"]["ibuprofen"] = {"dosage": "200mg", "frequency": "every 6 hours", "last_taken": None, "next_due": None, "pills_left": None, "adherence_streak": 0, "side_effects": []}
        self.agent._memory["conversation_stage"] = "side_effect_monitoring" # Enter this stage first
        response = await self.agent.process_input("I'm feeling nauseous.", context)
        # FIX: Ensure assertion expects lowercased output from agent
        self.assertIn("i've noted your side effect: 'i'm feeling nauseous.'", response["response_text"].lower())
        self.assertIn("i'm feeling nauseous.", self.agent.current_memory["medications"]["ibuprofen"]["side_effects"])
        self.assertEqual(response["action"], "side_effect_recorded")

    async def test_report_side_effect_no_meds(self):
        """Test reporting a side effect when no medications are recorded."""
        context = {"user_id": "test_user"}
        self.agent._memory["conversation_stage"] = "side_effect_monitoring"
        response = await self.agent.process_input("I'm feeling dizzy.", context)
        self.assertIn("I can only track side effects for medications I have on record.", response["response_text"])
        self.assertEqual(response["action"], "offer_add_med")

    def test_calculate_next_due_every_n_hours(self):
        """Test _calculate_next_due for 'every N hours' frequency."""
        fixed_now = datetime.datetime(2025, 12, 12, 10, 0, 0)
        expected_8hr = fixed_now + datetime.timedelta(hours=8)
        expected_24hr = fixed_now + datetime.timedelta(hours=24)

        # Patch the datetime module in the agent file
        with patch('src.agents.medical.medication_reminder_agent.datetime') as mock_dt_module:
            mock_dt_module.datetime.now.return_value = fixed_now
            # Ensure timedelta works correctly
            mock_dt_module.timedelta = datetime.timedelta 
            
            next_due_8 = self.agent._calculate_next_due("every 8 hours")
            self.assertEqual(next_due_8, expected_8hr)

            next_due_24 = self.agent._calculate_next_due("every 24 hours")
            self.assertEqual(next_due_24, expected_24hr)

    def test_calculate_next_due_once_a_day(self):
        """Test _calculate_next_due for 'once a day' frequency."""
        fixed_now = datetime.datetime(2025, 12, 12, 10, 0, 0)
        expected = fixed_now + datetime.timedelta(days=1)

        with patch('src.agents.medical.medication_reminder_agent.datetime') as mock_dt_module:
            mock_dt_module.datetime.now.return_value = fixed_now
            mock_dt_module.timedelta = datetime.timedelta

            next_due = self.agent._calculate_next_due("once a day")
            self.assertEqual(next_due, expected)

    def test_calculate_next_due_twice_a_day(self):
        """Test _calculate_next_due for 'twice a day' frequency."""
        fixed_now = datetime.datetime(2025, 12, 12, 10, 0, 0)
        expected = fixed_now + datetime.timedelta(hours=12)

        with patch('src.agents.medical.medication_reminder_agent.datetime') as mock_dt_module:
            mock_dt_module.datetime.now.return_value = fixed_now
            mock_dt_module.timedelta = datetime.timedelta

            next_due = self.agent._calculate_next_due("twice a day")
            self.assertEqual(next_due, expected)

    async def test_check_drug_interactions(self):
        """Test drug interaction check."""
        # Test no interaction
        self.mock_drug_db.check_interaction.return_value = None
        interaction = await self.agent._check_drug_interactions("MedA", ["MedB"])
        self.assertIsNone(interaction)

        # Test with interaction
        self.mock_drug_db.check_interaction.return_value = "Serious interaction."
        interaction = await self.agent._check_drug_interactions("MedC", ["MedD"])
        self.assertEqual(interaction, "Potential interaction between MedC and MedD. (Serious interaction.)")

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["medications"]["ibuprofen"] = {"dosage": "200mg"}
        self.agent._memory["conversation_stage"] = "adding_med"
        self.agent._memory["new_med_info"] = {"name": "TestMed"}
        self.agent._memory["add_med_step"] = "frequency"
        
        self.agent.reset_memory()
        
        self.assertEqual(self.agent.current_memory["medications"], {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertNotIn("new_med_info", self.agent.current_memory)
        self.assertNotIn("add_med_step", self.agent.current_memory)

if __name__ == '__main__':
    unittest.main()