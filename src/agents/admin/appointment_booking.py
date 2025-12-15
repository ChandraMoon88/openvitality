import logging
import datetime
from typing import Dict, Any, List, Optional, Tuple
import asyncio
import re

from src.agents.base_agent import BaseAgent
# Assuming NLU_Engine, TaskScheduler, and a hypothetical CalendarService/Database
# from src.language.nlu_engine import NLUEngine
# from src.core.task_scheduler import TaskScheduler # For scheduling reminders
# from src.core.distributed_lock import DistributedLock # For preventing double bookings

logger = logging.getLogger(__name__)

class AppointmentBookingAgent(BaseAgent):
    """
    A specialized AI agent acting as a virtual receptionist for booking appointments.
    It handles finding available slots, matching preferences, conflict detection,
    and integrates with calendar systems and reminder services.
    """
    def __init__(self, nlu_engine: Any = None, task_scheduler: Any = None, calendar_service: Any = None):
        super().__init__(
            name="AppointmentBookingAgent",
            description="Manages the booking of medical appointments.",
            persona={
                "role": "efficient and polite appointment receptionist",
                "directives": [
                    "Collect all necessary information for booking (patient name, doctor, reason, preferred time).",
                    "Find and propose available appointment slots based on criteria.",
                    "Ensure no double-bookings using a robust lock mechanism.",
                    "Integrate with calendar systems to confirm and add appointments.",
                    "Schedule automated reminders for upcoming appointments.",
                    "Clearly communicate cancellation policies.",
                    "Prioritize patient convenience while adhering to clinic schedules."
                ],
                "style": "professional, helpful, precise"
            }
        )
        self.nlu_engine = nlu_engine
        self.task_scheduler = task_scheduler
        self.calendar_service = calendar_service # Hypothetical service to query/book slots
        
        self._memory["booking_request"] = {
            "patient_name": None,
            "doctor_name": None,
            "specialty": None,
            "language_preference": None,
            "gender_preference": None,
            "reason": None,
            "preferred_date": None,
            "preferred_time_of_day": None, # "morning", "afternoon", "evening"
            "proposed_slots": [],
            "selected_slot": None,
            "confirmed": False
        }
        self._memory["conversation_stage"] = "greeting" # greeting, gathering_info, proposing_slots, confirming_booking
        self._memory["current_question_index"] = 0

        self.info_questions = [
            "What is the patient's full name for this appointment?",
            "What is the reason for this appointment?",
            "Do you have a preferred doctor, or a specialty you are looking for (e.g., Cardiology, Dermatology)?",
            "Do you have any preferences for the doctor's language or gender?",
            "What is your preferred date for the appointment? (e.g., 'next Tuesday', 'December 15th')",
            "And what time of day works best for you? (e.g., 'morning', 'afternoon', 'anytime')"
        ]

        # Define a cancellation policy (conceptual)
        self.cancellation_policy = "Appointments canceled less than 24 hours in advance may incur a cancellation fee of $50."
        logger.info("AppointmentBookingAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input for appointment booking.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = await self.nlu_engine.process_text(text, context.get("language", "en"))
        
        text_lower = text.lower()

        if self._memory["conversation_stage"] == "greeting":
            self._memory["conversation_stage"] = "gathering_info"
            self._memory["current_question_index"] = 0
            return self._ask_next_question()
        
        elif self._memory["conversation_stage"] == "gathering_info":
            await self._process_info_answer(text, nlu_output, self._memory["current_question_index"] - 1)
            
            if self._memory["current_question_index"] < len(self.info_questions):
                return self._ask_next_question()
            else:
                self._memory["conversation_stage"] = "proposing_slots"
                return await self._find_and_propose_slots(context)
        
        elif self._memory["conversation_stage"] == "proposing_slots":
            return await self._confirm_or_reschedule_slot(text_lower, context)
        
        elif self._memory["conversation_stage"] == "confirming_booking":
            if "yes" in text_lower or "confirm" in text_lower:
                return await self._finalize_booking(context)
            else:
                return {"response_text": "No problem. We can look for other times or you can contact us again when you're ready.", "context_update": {"booking_stage": "cancelled"}, "action": "cancel_booking"}
            
        return {"response_text": "I'm not sure how to handle your appointment request at this moment.", "context_update": {}, "action": "clarify_booking"}

    def _ask_next_question(self) -> Dict[str, Any]:
        """Returns the next question in the information gathering flow."""
        question_text = self.info_questions[self._memory["current_question_index"]]
        self._memory["current_question_index"] += 1
        return {
            "response_text": question_text,
            "context_update": {"booking_stage": "gathering_info", "question_asked": question_text},
            "action": "ask_question"
        }

    async def _process_info_answer(self, text: str, nlu_output: Dict[str, Any], question_index: int):
        """
        Processes answers to information gathering questions.
        """
        logger.debug(f"Processing answer to booking question {question_index}: '{text}'")
        text_lower = text.lower()
        entities = nlu_output.get("entities", [])

        if question_index == 0: # Patient name
            self._memory["booking_request"]["patient_name"] = text.title()
        elif question_index == 1: # Reason
            self._memory["booking_request"]["reason"] = text
        elif question_index == 2: # Doctor preference / Specialty
            if "doctor" in text_lower:
                name_match = re.search(r'(dr\.?\s+\w+)', text_lower)
                if name_match: self._memory["booking_request"]["doctor_name"] = name_match.group(1).title()
            for entity in entities:
                if entity["type"] == "SPECIALTY": # Hypothetical entity type
                    self._memory["booking_request"]["specialty"] = entity["text"]
        elif question_index == 3: # Language/Gender preference
            if "male" in text_lower: self._memory["booking_request"]["gender_preference"] = "male"
            elif "female" in text_lower: self._memory["booking_request"]["gender_preference"] = "female"
            if "spanish" in text_lower: self._memory["booking_request"]["language_preference"] = "es"
        elif question_index == 4: # Preferred Date
            for entity in entities:
                if entity["type"] == "DATE": # Hypothetical entity type for date
                    self._memory["booking_request"]["preferred_date"] = entity["text"] # e.g., "next Tuesday"
        elif question_index == 5: # Preferred Time of Day
            if "morning" in text_lower: self._memory["booking_request"]["preferred_time_of_day"] = "morning"
            elif "afternoon" in text_lower: self._memory["booking_request"]["preferred_time_of_day"] = "afternoon"
            elif "evening" in text_lower: self._memory["booking_request"]["preferred_time_of_day"] = "evening"
            else: self._memory["booking_request"]["preferred_time_of_day"] = "anytime"


    async def _find_and_propose_slots(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Queries the calendar service for available slots based on collected preferences.
        """
        request = self._memory["booking_request"]
        
        # Conceptual call to a calendar service
        # available_slots = await self.calendar_service.find_slots(request)
        
        # Mock available slots
        mock_slots = [
            {"doctor": "Dr. Smith", "specialty": "General Practice", "time": datetime.datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + datetime.timedelta(days=2)},
            {"doctor": "Dr. Jones", "specialty": "Cardiology", "time": datetime.datetime.now().replace(hour=14, minute=30, second=0, microsecond=0) + datetime.timedelta(days=3)},
            {"doctor": "Dr. Smith", "specialty": "General Practice", "time": datetime.datetime.now().replace(hour=11, minute=0, second=0, microsecond=0) + datetime.timedelta(days=2)},
        ]
        
        # Filter mock slots by preferences (simplified)
        filtered_slots = []
        for slot in mock_slots:
            if request["specialty"] and request["specialty"].lower() != slot["specialty"].lower():
                continue
            if request["doctor_name"] and request["doctor_name"].lower() != slot["doctor"].lower():
                continue
            # More complex logic for date/time/gender/language matching
            filtered_slots.append(slot)

        if not filtered_slots:
            return {"response_text": "I couldn't find any available slots matching your preferences. Would you like to try different criteria?", "context_update": {"booking_stage": "no_slots_found"}, "action": "no_slots"}
        
        self._memory["booking_request"]["proposed_slots"] = filtered_slots[:2] # Propose top 2
        response_parts = ["I found the following available appointment slots:"]
        for i, slot in enumerate(self._memory["booking_request"]["proposed_slots"]):
            response_parts.append(f"{i+1}. {slot['doctor']} ({slot['specialty']}) on {slot['time'].strftime('%A, %B %d at %I:%M %p')}")
        response_parts.append("Which one would you like to book? Please say the number (e.g., 'number one').")
        
        self._memory["conversation_stage"] = "proposing_slots"
        return {
            "response_text": " ".join(response_parts),
            "context_update": {"booking_stage": "slots_proposed"},
            "action": "propose_slots"
        }

    async def _confirm_or_reschedule_slot(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Confirms the selected slot or handles requests to reschedule.
        """
        slot_selection = None
        if "one" in text or "number 1" in text: slot_selection = 0
        elif "two" in text or "number 2" in text: slot_selection = 1
        
        if slot_selection is not None and slot_selection < len(self._memory["booking_request"]["proposed_slots"]):
            selected_slot = self._memory["booking_request"]["proposed_slots"][slot_selection]
            self._memory["booking_request"]["selected_slot"] = selected_slot
            
            # Conceptual lock mechanism
            # if not await DistributedLock.acquire(f"slot_{selected_slot['time'].isoformat()}"):
            #    return {"response_text": "That slot was just taken. Please choose another.", "context_update": {}, "action": "slot_taken"}

            self._memory["conversation_stage"] = "confirming_booking"
            confirmation_message = (
                f"You've selected an appointment with {selected_slot['doctor']} "
                f"on {selected_slot['time'].strftime('%A, %B %d at %I:%M %p')}. "
                f"The reason is '{self._memory['booking_request']['reason']}'. "
                f"Please confirm by saying 'yes' or 'confirm'."
            )
            return {
                "response_text": confirmation_message,
                "context_update": {"booking_stage": "awaiting_final_confirmation"},
                "action": "await_confirmation"
            }
        else:
            return {"response_text": "I didn't understand your selection. Please say 'number one' or 'number two' to choose a slot, or 'reschedule' to look for other times.", "context_update": {}, "action": "clarify_slot_selection"}

    async def _finalize_booking(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalizes the booking, integrates with calendar, and schedules reminders.
        """
        selected_slot = self._memory["booking_request"]["selected_slot"]
        if not selected_slot:
            return {"response_text": "It seems no slot was selected. Please try booking again.", "context_update": {}, "action": "error"}

        # Conceptual calendar integration
        # booking_successful = await self.calendar_service.book_slot(selected_slot)
        booking_successful = True # Mock success
        
        # Release the lock
        # await DistributedLock.release(f"slot_{selected_slot['time'].isoformat()}")

        if booking_successful:
            self._memory["booking_request"]["confirmed"] = True
            
            # Schedule reminders
            if self.task_scheduler:
                patient_id = context.get("user_id", "unknown")
                await self.task_scheduler.schedule_task(
                    "appointment_reminder", 
                    selected_slot['time'] - datetime.timedelta(days=1),
                    payload={"type": "1_day_before", "patient_id": patient_id, "slot": selected_slot}
                )
                await self.task_scheduler.schedule_task(
                    "appointment_reminder", 
                    selected_slot['time'] - datetime.timedelta(hours=1),
                    payload={"type": "1_hour_before", "patient_id": patient_id, "slot": selected_slot}
                )

            final_message = (
                f"Your appointment with {selected_slot['doctor']} on "
                f"{selected_slot['time'].strftime('%A, %B %d at %I:%M %p')} has been successfully booked. "
                "You will receive a confirmation message shortly, and reminders one day and one hour before your appointment. "
                f"Our cancellation policy is: {self.cancellation_policy} Is there anything else I can help you with?"
            )
            return {
                "response_text": final_message,
                "context_update": {"booking_stage": "booked", "appointment_details": selected_slot},
                "action": "appointment_booked"
            }
        else:
            return {"response_text": "I apologize, there was an issue finalizing your booking. Please try again or contact the clinic directly.", "context_update": {"booking_stage": "booking_failed"}, "action": "booking_failed"}

    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["booking_request"] = {
            "patient_name": None, "doctor_name": None, "specialty": None,
            "language_preference": None, "gender_preference": None,
            "reason": None, "preferred_date": None, "preferred_time_of_day": None,
            "proposed_slots": [], "selected_slot": None, "confirmed": False
        }
        self._memory["conversation_stage"] = "greeting"
        self._memory["current_question_index"] = 0

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock dependencies
    class MockNLUEngine:
        def process_text(self, text, lang):
            entities = []
            if "cardiology" in text.lower(): entities.append({"type": "SPECIALTY", "text": "Cardiology"})
            if "next tuesday" in text.lower(): entities.append({"type": "DATE", "text": "next Tuesday"})
            return {"entities": entities, "intent": {"name": "appointment_booking"}}

    class MockTaskScheduler:
        async def schedule_task(self, task_type: str, due_time: datetime.datetime, payload: Dict[str, Any]):
            logger.info(f"MOCK: Scheduled {task_type} for {due_time.strftime('%Y-%m-%d %H:%M')} with payload {payload}")

    class MockCalendarService:
        async def find_slots(self, request: Dict[str, Any]) -> List[Dict[str, Any]]:
            logger.info(f"MOCK: Finding slots for request: {request}")
            now = datetime.datetime.now()
            return [
                {"doctor": "Dr. House", "specialty": "Diagnostician", "time": now.replace(hour=9, minute=0, second=0, microsecond=0) + datetime.timedelta(days=7)},
                {"doctor": "Dr. Wilson", "specialty": "Oncology", "time": now.replace(hour=13, minute=0, second=0, microsecond=0) + datetime.timedelta(days=7)},
                {"doctor": "Dr. House", "specialty": "Diagnostician", "time": now.replace(hour=10, minute=0, second=0, microsecond=0) + datetime.timedelta(days=8)},
            ]
        async def book_slot(self, slot: Dict[str, Any]) -> bool:
            logger.info(f"MOCK: Booking slot: {slot}")
            return True # Always success in mock


    nlu_mock = MockNLUEngine()
    task_scheduler_mock = MockTaskScheduler()
    calendar_service_mock = MockCalendarService()
    
    booking_agent = AppointmentBookingAgent(
        nlu_engine=nlu_mock,
        task_scheduler=task_scheduler_mock,
        calendar_service=calendar_service_mock
    )

    async def run_booking_flow():
        context = {"call_id": "booking_call_123", "user_id": "patient_001", "language": "en"}

        print("\n--- Flow 1: Full Booking Process ---")
        response1 = await booking_agent.process_input("I want to book an appointment.", context)
        print(f"Agent: {response1['response_text']}") # Ask patient name
        
        response2 = await booking_agent.process_input("My name is John Doe.", context)
        print(f"Agent: {response2['response_text']}") # Ask reason
        
        response3 = await booking_agent.process_input("I have a persistent cough.", context)
        print(f"Agent: {response3['response_text']}") # Ask doctor/specialty
        
        response4 = await booking_agent.process_input("I'd like to see a general practitioner, preferably Dr. House.", context)
        print(f"Agent: {response4['response_text']}") # Ask preferences
        
        response5 = await booking_agent.process_input("No specific language or gender preference.", context)
        print(f"Agent: {response5['response_text']}") # Ask preferred date
        
        response6 = await booking_agent.process_input("Next Tuesday.", context)
        print(f"Agent: {response6['response_text']}") # Ask preferred time of day
        
        response7 = await booking_agent.process_input("Morning.", context)
        print(f"Agent (Proposes Slots): {response7['response_text']}")
        
        response8 = await booking_agent.process_input("I'll take number one.", context)
        print(f"Agent (Confirms Slot): {response8['response_text']}")
        
        response9 = await booking_agent.process_input("Yes, confirm.", context)
        print(f"Agent (Finalizes): {response9['response_text']}")
        assert "successfully booked" in response9["response_text"]
        assert booking_agent.current_memory["booking_request"]["confirmed"] == True

        booking_agent.reset_memory()
        print(f"\nMemory after reset: {booking_agent.current_memory}")

    import asyncio
    asyncio.run(run_booking_flow())
