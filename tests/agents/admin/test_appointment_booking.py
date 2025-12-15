import sys
import os
import unittest
from unittest.mock import AsyncMock, patch
import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.admin.appointment_booking import AppointmentBookingAgent

class TestAppointmentBookingAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        self.mock_nlu_engine = AsyncMock()
        self.mock_task_scheduler = AsyncMock()
        self.mock_calendar_service = AsyncMock()
        
        # Set a default return value for the NLU engine mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "any_intent"}}
        self.agent = AppointmentBookingAgent(
            nlu_engine=self.mock_nlu_engine,
            task_scheduler=self.mock_task_scheduler,
            calendar_service=self.mock_calendar_service
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

    async def test_initial_greeting(self):
        """Test the first interaction which should move from greeting to gathering info."""
        response = await self.agent.process_input("I need an appointment.", {})
        
        self.assertEqual(self.agent._memory["conversation_stage"], "gathering_info")
        self.assertEqual(response["action"], "ask_question")
        self.assertEqual(response["response_text"], self.agent.info_questions[0]) # Ask for name

    async def test_information_gathering_flow(self):
        """Test the sequence of questions for gathering information."""
        context = {}
        # Start the conversation
        await self.agent.process_input("Hi", context)
        
        # Test each question in the flow
        for i in range(len(self.agent.info_questions)):
            question_text = self.agent.info_questions[i]
            # The agent asks the question
            self.assertEqual(self.agent._memory["conversation_stage"], "gathering_info")
            self.assertEqual(self.agent._memory["current_question_index"], i + 1)
            
            # Simulate a user answer
            response = await self.agent.process_input(f"Answer for question {i}", context)
            
            # If there are more questions, it should ask the next one
            if i < len(self.agent.info_questions) - 1:
                self.assertEqual(response["response_text"], self.agent.info_questions[i+1])

    async def test_proposing_slots(self):
        """Test that the agent finds and proposes slots after gathering info."""
        # Manually set the state to the end of information gathering
        self.agent._memory["conversation_stage"] = "gathering_info"
        self.agent._memory["current_question_index"] = len(self.agent.info_questions)
        self.agent._memory["booking_request"] = {"specialty": "Cardiology", "doctor_name": None} # Example preference

        # Mock the calendar service response
        mock_slot_time = datetime.datetime.now()
        self.mock_calendar_service.find_slots.return_value = [
            {"doctor": "Dr. Jones", "specialty": "Cardiology", "time": mock_slot_time}
        ]
        
        # This input triggers the transition to proposing slots
        response = await self.agent.process_input("Anytime is fine.", {})
        
        self.assertEqual(self.agent._memory["conversation_stage"], "proposing_slots")
        self.assertEqual(response["action"], "propose_slots")
        self.assertIn("Dr. Jones", response["response_text"])
        self.assertIn("Cardiology", response["response_text"])
        
    async def test_slot_confirmation(self):
        """Test the user selecting a proposed slot."""
        # Manually set the state to proposing slots
        self.agent._memory["conversation_stage"] = "proposing_slots"
        mock_slot_time = datetime.datetime.now()
        proposed_slots = [
            {"doctor": "Dr. Test", "specialty": "Testing", "time": mock_slot_time}
        ]
        self.agent._memory["booking_request"]["proposed_slots"] = proposed_slots
        
        response = await self.agent.process_input("number one", {})

        self.assertEqual(self.agent._memory["conversation_stage"], "confirming_booking")
        self.assertEqual(response["action"], "await_confirmation")
        self.assertIn("You've selected an appointment with Dr. Test", response["response_text"])
        self.assertEqual(self.agent._memory["booking_request"]["selected_slot"], proposed_slots[0])

    async def test_final_booking_confirmation(self):
        """Test the final 'yes' which finalizes the booking."""
        # Manually set the state to awaiting final confirmation
        self.agent._memory["conversation_stage"] = "confirming_booking"
        selected_slot = {"doctor": "Dr. Final", "time": datetime.datetime.now()}
        self.agent._memory["booking_request"]["selected_slot"] = selected_slot
        self.agent._memory["booking_request"]["reason"] = "Checkup"
        
        # Mock calendar booking success
        self.mock_calendar_service.book_slot.return_value = True
        
        response = await self.agent.process_input("Yes, confirm", {"user_id": "patient123"})
        
        self.assertEqual(response["action"], "appointment_booked")
        self.assertIn("successfully booked", response["response_text"])
        self.assertTrue(self.agent._memory["booking_request"]["confirmed"])
        
        # Check if reminder tasks were scheduled
        self.mock_task_scheduler.schedule_task.assert_called()
        self.assertEqual(self.mock_task_scheduler.schedule_task.call_count, 2)

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        # Change some memory values
        self.agent._memory["conversation_stage"] = "booked"
        self.agent._memory["booking_request"]["patient_name"] = "John Doe"
        
        self.agent.reset_memory()
        
        self.assertEqual(self.agent._memory["conversation_stage"], "greeting")
        self.assertIsNone(self.agent._memory["booking_request"]["patient_name"])


if __name__ == '__main__':
    unittest.main()
