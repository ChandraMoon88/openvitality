import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.admin.cancellation_handler import AppointmentCancellationAgent

class TestAppointmentCancellationAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        # Use MagicMock for synchronous NLU calls
        self.mock_nlu_engine = MagicMock()
        self.mock_auth_service = AsyncMock()
        self.mock_calendar_service = AsyncMock()
        self.mock_notification_service = AsyncMock()
        self.mock_payment_gateway = AsyncMock()
        self.mock_waitlist_manager = AsyncMock()
        
        self.agent = AppointmentCancellationAgent(
            nlu_engine=self.mock_nlu_engine,
            auth_service=self.mock_auth_service,
            calendar_service=self.mock_calendar_service,
            notification_service=self.mock_notification_service,
            payment_gateway=self.mock_payment_gateway,
            waitlist_manager=self.mock_waitlist_manager
        )
        self.agent._check_safety = AsyncMock(return_value=True)
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "cancel_appointment"}}

    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "AppointmentCancellationAgent")
        self.assertIn("cancellation_request", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "authentication")
        self.assertEqual(self.agent.current_memory["cancellation_request"]["authentication_status"], False)
        self.assertEqual(self.agent.cancellation_policy["no_charge_window_hours"], 24)
        self.assertEqual(self.agent.cancellation_policy["cancellation_fee_amount"], 50.00)

    async def test_authenticate_caller_success(self):
        """Test successful authentication flow."""
        context = {"user_id": "test_user"}
        await self.agent.process_input("I want to cancel my appointment.", context)
        response = await self.agent.process_input("My name is Jane Doe and my OTP is 5678.", context)
        
        self.assertTrue(self.agent.current_memory["cancellation_request"]["authentication_status"])
        self.assertEqual(self.agent.current_memory["cancellation_request"]["patient_id"], "patient_002")
        self.assertEqual(self.agent.current_memory["conversation_stage"], "identify_appointment")
        self.assertIn("What is the date and time of the appointment", response["response_text"])

    async def test_authenticate_caller_already_authenticated(self):
        """Test handling of already authenticated caller."""
        context = {"user_id": "test_user"}
        self.agent._memory["cancellation_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "authentication" 
        
        response = await self.agent.process_input("I want to cancel.", context)
        self.assertIn("Your identity has already been verified.", response["response_text"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "identify_appointment")

    async def test_authenticate_caller_failure(self):
        """Test failed authentication attempt."""
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("Invalid credentials.", context)
        
        self.assertFalse(self.agent.current_memory["cancellation_request"]["authentication_status"])
        self.assertIn("Could you please provide your full name and date of birth", response["response_text"])
        self.assertEqual(response["action"], "request_authentication_retry")

    async def test_identify_appointment_early_cancellation(self):
        """Test identification of an appointment that qualifies for a full refund."""
        context = {"user_id": "test_user"}
        self.agent._memory["cancellation_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "identify_appointment"
        
        now = datetime.datetime.now()
        future_date = now + datetime.timedelta(days=5) 
        
        # Test input must match the strict time regex (HH:MM or HH AM/PM)
        test_input = future_date.strftime("My appointment is on %B %d, %Y at 10 AM.")
        
        response = await self.agent.process_input(test_input, context)
        
        self.assertIsNotNone(self.agent.current_memory["cancellation_request"]["appointment_details"])
        self.assertEqual(self.agent.current_memory["cancellation_request"]["refund_due"], 100.00)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "gathering_reason")
        self.assertIn("A full refund of $100.00 will be processed. Why are you canceling today?", response["response_text"])

    async def test_identify_appointment_late_cancellation(self):
        """Test identification of an appointment that triggers a cancellation fee."""
        context = {"user_id": "test_user"}
        self.agent._memory["cancellation_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "identify_appointment"
        
        now = datetime.datetime.now()
        soon_date = now + datetime.timedelta(hours=1) 
        
        test_input = soon_date.strftime("My appointment is on %B %d, %Y at %I:%M %p.")
        
        response = await self.agent.process_input(test_input, context)
        
        self.assertEqual(self.agent.current_memory["cancellation_request"]["refund_due"], 0.0)
        self.assertIn("A cancellation fee of $50.00 will apply, meaning no refund", response["response_text"])
        self.assertEqual(response["action"], "confirm_late_fee")

    async def test_identify_appointment_not_found(self):
        """Test scenario where appointment cannot be identified."""
        context = {"user_id": "test_user"}
        self.agent._memory["cancellation_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "identify_appointment"
        
        response = await self.agent.process_input("My appointment is on an unknown date.", context)
        
        self.assertIsNone(self.agent.current_memory["cancellation_request"]["appointment_details"])
        self.assertIn("I couldn't find an appointment matching that information", response["response_text"])
        self.assertEqual(response["action"], "retry_identify_appointment")

    def test_ask_next_question_cancel(self):
        """Test that the agent asks the next question in the cancellation flow."""
        self.agent._memory["conversation_stage"] = "authentication" 
        self.agent._memory["current_question_index"] = 0
        response = self.agent._ask_next_question_cancel()
        self.assertIn("To help me find your appointment", response["response_text"])
        self.assertEqual(self.agent.current_memory["current_question_index"], 1)

    async def test_ask_final_confirmation(self):
        """Test that the final confirmation message is correctly constructed."""
        self.agent._memory["cancellation_request"]["appointment_details"] = {
            "doctor": "Dr. Test", 
            "time": datetime.datetime(2025, 1, 1, 10, 0)
        }
        self.agent._memory["cancellation_request"]["refund_due"] = 50.00
        
        response = self.agent._ask_final_confirmation({})
        self.assertIn("You are about to cancel your appointment with Dr. Test", response["response_text"])
        self.assertIn("A refund of $50.00 will be processed.", response["response_text"])
        self.assertEqual(response["action"], "confirm_cancellation")

        self.agent._memory["cancellation_request"]["refund_due"] = 0.0
        response = self.agent._ask_final_confirmation({})
        self.assertIn("No refund is due for this late cancellation.", response["response_text"])
    
    async def test_finalize_cancellation_success_with_refund(self):
        """Test successful finalization with a refund."""
        context = {"user_id": "test_user"}
        self.agent._memory["cancellation_request"]["patient_id"] = "patient_002"
        self.agent._memory["cancellation_request"]["appointment_details"] = {
            "appointment_id": "appt_456", "doctor": "Dr. Test", "time": datetime.datetime.now(), "cost": 100.00
        }
        self.agent._memory["cancellation_request"]["refund_due"] = 100.00
        self.agent._memory["cancellation_request"]["cancellation_reason"] = "Test reason"
        self.agent._memory["cancellation_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "confirming_cancellation"

        self.mock_calendar_service.cancel_appointment.return_value = True
        self.mock_payment_gateway.process_refund = AsyncMock(return_value=True)

        response = await self.agent.process_input("yes", context)
        self.assertTrue(self.agent.current_memory["cancellation_request"]["cancellation_confirmed"])
        self.assertIn("successfully canceled", response["response_text"])
        self.assertIn("A refund of $100.00 has been processed.", response["response_text"])
        self.mock_payment_gateway.process_refund.assert_called_once_with("patient_002", 100.00)
        self.assertEqual(response["action"], "appointment_canceled")

    async def test_finalize_cancellation_success_no_refund(self):
        """Test successful finalization with no refund (late cancellation)."""
        context = {"user_id": "test_user"}
        self.agent._memory["cancellation_request"]["patient_id"] = "patient_002"
        self.agent._memory["cancellation_request"]["appointment_details"] = {
            "appointment_id": "appt_456", "doctor": "Dr. Test", "time": datetime.datetime.now(), "cost": 100.00
        }
        self.agent._memory["cancellation_request"]["refund_due"] = 0.0
        self.agent._memory["cancellation_request"]["cancellation_reason"] = "Late reason"
        self.agent._memory["cancellation_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "confirming_cancellation"

        self.mock_calendar_service.cancel_appointment.return_value = True

        response = await self.agent.process_input("yes", context)
        self.assertIn("No refund was processed due to late cancellation.", response["response_text"])
        self.mock_payment_gateway.process_refund.assert_not_called()

    async def test_finalize_cancellation_missing_details(self):
        """Test finalization when appointment details are missing."""
        context = {"user_id": "test_user"}
        self.agent._memory["cancellation_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "confirming_cancellation"
        # appointment_details is None
        response = await self.agent.process_input("yes", context)
        self.assertIn("An error occurred during cancellation", response["response_text"])
        self.assertEqual(response["action"], "error_cancellation")

    async def test_process_input_do_not_cancel(self):
        """Test processing of 'no' to final confirmation."""
        context = {"user_id": "test_user"}
        self.agent._memory["cancellation_request"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "confirming_cancellation"
        self.agent._memory["cancellation_request"]["appointment_details"] = {"doctor": "Dr. Test", "time": datetime.datetime.now()}
        
        response = await self.agent.process_input("no", context)
        self.assertIn("No problem, your appointment has not been canceled.", response["response_text"])
        self.assertEqual(response["action"], "do_not_cancel")

    def test_month_to_int(self):
        """Test month name to integer conversion."""
        self.assertEqual(self.agent._month_to_int("January"), 1)
        self.assertEqual(self.agent._month_to_int("december"), 12)
        self.assertEqual(self.agent._month_to_int("Unknown"), datetime.datetime.now().month)

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["cancellation_request"]["patient_id"] = "some_id"
        self.agent._memory["conversation_stage"] = "confirming_cancellation"
        self.agent._memory["cancellation_request"]["authentication_status"] = True
        
        self.agent.reset_memory()
        
        self.assertIsNone(self.agent.current_memory["cancellation_request"]["patient_id"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "authentication")
        self.assertFalse(self.agent.current_memory["cancellation_request"]["authentication_status"])

if __name__ == '__main__':
    unittest.main()