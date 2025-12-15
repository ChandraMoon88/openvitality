import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.admin.appointment_rescheduling import AppointmentReschedulingAgent

class TestAppointmentReschedulingAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        self.mock_nlu_engine = MagicMock()
        self.mock_auth_service = AsyncMock()
        self.mock_calendar_service = AsyncMock()
        self.mock_notification_service = AsyncMock()
        self.mock_waitlist_manager = AsyncMock()
        
        self.agent = AppointmentReschedulingAgent(
            nlu_engine=self.mock_nlu_engine,
            auth_service=self.mock_auth_service,
            calendar_service=self.mock_calendar_service,
            notification_service=self.mock_notification_service,
            waitlist_manager=self.mock_waitlist_manager
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "reschedule_appointment"}}

    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "AppointmentReschedulingAgent")
        self.assertIn("reschedule_request", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "authentication")
        self.assertEqual(self.agent.current_memory["reschedule_request"]["authentication_status"], False)
        self.assertEqual(self.agent.rescheduling_policy["late_reschedule_window_hours"], 24)
        self.assertEqual(self.agent.rescheduling_policy["late_reschedule_fee"], 50.00)

    async def test_authenticate_caller_success(self):
        """Test successful authentication flow."""
        context = {"user_id": "test_user"}
        
        # Simulate initial request to reschedule
        await self.agent.process_input("I need to reschedule my appointment.", context)
        
        # Simulate successful authentication
        response = await self.agent.process_input("My name is John Doe and my OTP is 1234.", context)
        
        self.assertTrue(self.agent.current_memory["reschedule_request"]["authentication_status"])
        self.assertEqual(self.agent.current_memory["reschedule_request"]["patient_id"], "patient_001")
        self.assertEqual(self.agent.current_memory["conversation_stage"], "identify_appointment")
        self.assertIn("To help me find your appointment", response["response_text"])

    async def test_authenticate_caller_already_authenticated(self):
        """Test handling of already authenticated caller."""
        context = {"user_id": "test_user"}
        self.agent._memory["reschedule_request"]["authentication_status"] = True
        
        response = await self.agent.process_input("I want to reschedule.", context)
        self.assertIn("Your identity has already been verified", response["response_text"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "identify_appointment")

    async def test_authenticate_caller_failure(self):
        """Test failed authentication attempt."""
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("Invalid credentials.", context)
        
        self.assertFalse(self.agent.current_memory["reschedule_request"]["authentication_status"])
        self.assertIn("Could you please provide your full name and date of birth", response["response_text"])
        self.assertEqual(response["action"], "request_authentication_retry")

    async def test_identify_original_appointment_success(self):
        """Test successful identification of an original appointment."""
        context = {"user_id": "test_user"}
        self.agent._memory["reschedule_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "identify_appointment"
        
        now = datetime.datetime.now()
        future_date = now + datetime.timedelta(days=7) # Far enough not to trigger late fee
        
        test_input = future_date.strftime("My appointment is on %B %d, %Y at %I:%M %p.")
        
        response = await self.agent.process_input(test_input, context)
        
        self.assertIsNotNone(self.agent.current_memory["reschedule_request"]["original_slot"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "gathering_new_preferences")
        # FIX: Updated assertion string to match the actual agent response "new appointment"
        self.assertIn("What is your preferred date for the new appointment?", response["response_text"])

    async def test_identify_original_appointment_not_found(self):
        """Test scenario where original appointment cannot be identified."""
        context = {"user_id": "test_user"}
        self.agent._memory["reschedule_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "identify_appointment" # Ensure correct stage
        
        response = await self.agent.process_input("My appointment is on an unknown date.", context)
        
        self.assertIsNone(self.agent.current_memory["reschedule_request"]["original_slot"])
        self.assertIn("I couldn't find an appointment matching that information", response["response_text"])
        self.assertEqual(response["action"], "retry_identify_appointment")

    async def test_identify_original_appointment_late_fee(self):
        """Test identification of an appointment that triggers a late rescheduling fee."""
        context = {"user_id": "test_user"}
        self.agent._memory["reschedule_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "identify_appointment"
        
        now = datetime.datetime.now()
        soon_date = now + datetime.timedelta(hours=1) # Within late rescheduling window
        
        test_input = soon_date.strftime("My appointment is on %B %d, %Y at %I:%M %p.")
        
        response = await self.agent.process_input(test_input, context)
        
        self.assertTrue(self.agent.current_memory["reschedule_request"]["late_cancellation_fee_applied"])
        self.assertIn("A late rescheduling fee of $50.00 will apply.", response["response_text"])
        self.assertEqual(response["action"], "confirm_late_fee")

    async def test_ask_next_question_reschedule(self):
        """Test that the agent asks the next question for new preferences."""
        self.agent._memory["conversation_stage"] = "gathering_new_preferences"
        self.agent._memory["current_question_index"] = 0
        response = self.agent._ask_next_question_reschedule()
        self.assertIn("To help me find your appointment", response["response_text"])
        self.assertEqual(self.agent.current_memory["current_question_index"], 1)

    async def test_process_new_preferences_answer(self):
        """Test processing of new preferred date and time."""
        # Mock nlu_output for date
        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "DATE", "text": "next Monday"}], "intent": {}}
        self.agent._process_new_preferences_answer("next Monday", self.mock_nlu_engine.process_text("", {}), 0) # Index 0 for preferred date
        self.assertEqual(self.agent.current_memory["reschedule_request"]["new_preferred_date"], "next Monday")

        # Mock nlu_output for time
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {}}
        self.agent._process_new_preferences_answer("morning", self.mock_nlu_engine.process_text("", {}), 1) # Index 1 for preferred time
        self.assertEqual(self.agent.current_memory["reschedule_request"]["new_preferred_time_of_day"], "morning")

    async def test_find_and_propose_new_slots_success(self):
        """Test finding and proposing new slots."""
        context = {"user_id": "test_user"}
        self.agent._memory["reschedule_request"]["original_slot"] = {"doctor": "Dr. Smith", "specialty": "General Practice", "time": datetime.datetime.now()}
        self.agent._memory["reschedule_request"]["authentication_status"] = True # Added authentication status
        self.agent._memory["conversation_stage"] = "gathering_new_preferences"
        self.agent._memory["reschedule_request"]["new_preferences_question_index"] = 0 # Start at the first new preference question

        # Mock NLU for "next week" to return a DATE entity
        self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "DATE", "text": "next week"}], "intent": {}}
        # Simulate answering the first new preference question (preferred date)
        response = await self.agent.process_input("next week", context) # This input answers the date preference
        self.assertIn("What is your preferred time of day", response["response_text"])
        self.assertEqual(self.agent.current_memory["reschedule_request"]["new_preferences_question_index"], 1)

        # Mock NLU for "Anytime is fine." to return no specific entity for time
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {}}
        # Simulate answering the second new preference question (preferred time of day)
        response = await self.agent.process_input("Anytime is fine.", context) # This input answers the time preference
        
        self.assertEqual(self.agent.current_memory["conversation_stage"], "proposing_new_slots")
        self.assertIn("I found the following alternative appointment slots", response["response_text"])
        self.assertGreater(len(self.agent.current_memory["reschedule_request"]["proposed_new_slots"]), 0)

    async def test_find_and_propose_new_slots_no_slots(self):
        """Test scenario where no new slots are found."""
        context = {"user_id": "test_user"}
        self.agent._memory["reschedule_request"]["original_slot"] = {"doctor": "Dr. Smith", "specialty": "General Practice", "time": datetime.datetime.now()}
        self.agent._memory["reschedule_request"]["authentication_status"] = True # Added authentication status
        
        # Patch the _mock_new_slots to be empty
        with patch.object(self.agent, '_mock_new_slots', []):
            self.agent._memory["conversation_stage"] = "gathering_new_preferences"
            self.agent._memory["reschedule_request"]["new_preferences_question_index"] = 0 # Start at the first new preference question
            
            # Mock NLU for "next week" to return a DATE entity
            self.mock_nlu_engine.process_text.return_value = {"entities": [{"type": "DATE", "text": "next week"}], "intent": {}}
            # Simulate answering the first new preference question (preferred date)
            await self.agent.process_input("next week", context)

            # Mock NLU for "Anytime is fine." to return no specific entity for time
            self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {}}
            # Simulate answering the second new preference question (preferred time of day)
            response = await self.agent.process_input("Anytime is fine.", context)

            self.assertIn("I couldn't find any alternative slots", response["response_text"])
            self.assertEqual(response["action"], "no_new_slots")

    async def test_confirm_or_reschedule_new_slot_success(self):
        """Test successful selection of a new proposed slot."""
        context = {"user_id": "test_user"}
        mock_slot_time = datetime.datetime.now() + datetime.timedelta(days=10)
        self.agent._memory["reschedule_request"]["proposed_new_slots"] = [
            {"doctor": "Dr. Smith", "specialty": "GP", "time": mock_slot_time}
        ]
        self.agent._memory["conversation_stage"] = "proposing_new_slots"
        self.agent._memory["reschedule_request"]["authentication_status"] = True

        response = await self.agent.process_input("number one", context)
        self.assertEqual(response["action"], "await_confirmation")
        self.assertIn("You've selected to reschedule your appointment", response["response_text"])
        self.assertIsNotNone(self.agent.current_memory["reschedule_request"]["selected_new_slot"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "confirming_reschedule")

        context = {"user_id": "test_user"}
        mock_slot_time = datetime.datetime.now() + datetime.timedelta(days=10)
        self.agent._memory["reschedule_request"]["proposed_new_slots"] = [
            {"doctor": "Dr. Smith", "specialty": "GP", "time": mock_slot_time}
        ]
        self.agent._memory["reschedule_request"]["authentication_status"] = True # Added authentication status
        self.agent._memory["conversation_stage"] = "proposing_new_slots"

        response = await self.agent.process_input("number three", context)
        self.assertIn("I didn't understand your selection", response["response_text"])
        self.assertEqual(response["action"], "clarify_new_slot_selection")
    
    async def test_finalize_reschedule_success(self):
        """Test successful finalization of rescheduling."""
        context = {"user_id": "test_user"}
        original_slot_time = datetime.datetime.now() + datetime.timedelta(days=2)
        new_slot_time = datetime.datetime.now() + datetime.timedelta(days=10)
        self.agent._memory["reschedule_request"]["original_slot"] = {"appointment_id": "orig_appt", "doctor": "Dr. Original", "time": original_slot_time}
        self.agent._memory["reschedule_request"]["selected_new_slot"] = {"appointment_id": "new_appt", "doctor": "Dr. New", "time": new_slot_time}
        self.agent._memory["reschedule_request"]["patient_id"] = "test_patient_id"
        self.agent._memory["reschedule_request"]["authentication_status"] = True # Added
        self.agent._memory["conversation_stage"] = "confirming_reschedule"

        # Mock calendar service booking success
        self.mock_calendar_service.book_slot.return_value = True
        
        response = await self.agent.process_input("yes", context)
        self.assertTrue(self.agent.current_memory["reschedule_request"]["reschedule_confirmed"])
        self.assertIn("successfully rescheduled", response["response_text"])
        self.assertEqual(response["action"], "appointment_rescheduled")
        self.mock_notification_service.send_sms.assert_called_once() # Assuming send_sms exists

    async def test_finalize_reschedule_late_fee_applied(self):
        """Test finalization when a late rescheduling fee is applied."""
        context = {"user_id": "test_user"}
        original_slot_time = datetime.datetime.now() + datetime.timedelta(hours=1)
        new_slot_time = datetime.datetime.now() + datetime.timedelta(days=10)
        self.agent._memory["reschedule_request"]["original_slot"] = {"appointment_id": "orig_appt", "doctor": "Dr. Original", "time": original_slot_time}
        self.agent._memory["reschedule_request"]["selected_new_slot"] = {"appointment_id": "new_appt", "doctor": "Dr. New", "time": new_slot_time}
        self.agent._memory["reschedule_request"]["patient_id"] = "test_patient_id"
        self.agent._memory["reschedule_request"]["late_cancellation_fee_applied"] = True
        self.agent._memory["reschedule_request"]["authentication_status"] = True # Added
        self.agent._memory["conversation_stage"] = "confirming_reschedule"

        self.mock_calendar_service.book_slot.return_value = True
        
        response = await self.agent.process_input("yes", context)
        self.assertIn("A late rescheduling fee of $50.00 will be applied.", response["response_text"])

    async def test_finalize_reschedule_missing_slots(self):
        """Test finalization when original or new slot is missing."""
        context = {"user_id": "test_user"}
        self.agent._memory["reschedule_request"]["authentication_status"] = True # Added
        self.agent._memory["conversation_stage"] = "confirming_reschedule"
        # original_slot is None
        response = await self.agent.process_input("yes", context)
        self.assertIn("An error occurred during rescheduling", response["response_text"])
        self.assertEqual(response["action"], "error_rescheduling")

    def test_month_to_int(self):
        """Test month name to integer conversion."""
        self.assertEqual(self.agent._month_to_int("January"), 1)
        self.assertEqual(self.agent._month_to_int("december"), 12)
        # Test case for unknown month, should default to current month
        self.assertEqual(self.agent._month_to_int("Unknown"), datetime.datetime.now().month)

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["reschedule_request"]["patient_id"] = "some_id"
        self.agent._memory["conversation_stage"] = "proposing_new_slots"
        
        self.agent.reset_memory()
        
        self.assertIsNone(self.agent.current_memory["reschedule_request"]["patient_id"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "authentication")

if __name__ == '__main__':
    unittest.main()