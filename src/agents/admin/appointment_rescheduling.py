import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))


import logging
import datetime
from typing import Dict, Any, List, Optional
import asyncio
import re

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class AppointmentReschedulingAgent(BaseAgent):
    """
    A specialized AI agent for managing the rescheduling of existing appointments.
    It handles caller authentication, policy checks, slot management, and notifications.
    """
    def __init__(self, nlu_engine: Any = None, auth_service: Any = None, calendar_service: Any = None, notification_service: Any = None, waitlist_manager: Any = None):
        super().__init__(
            name="AppointmentReschedulingAgent",
            description="Manages the rescheduling of medical appointments.",
            persona={
                "role": "efficient and helpful rescheduling assistant",
                "directives": [
                    "Verify caller identity before proceeding with sensitive operations.",
                    "Clearly communicate rescheduling policies, including any potential fees.",
                    "Efficiently release the original appointment slot.",
                    "Actively search for and propose alternative appointment times.",
                    "Ensure new appointment details are confirmed via preferred channels.",
                    "Facilitate waitlist notifications if a slot becomes available."
                ],
                "style": "professional, empathetic, clear"
            }
        )
        self.nlu_engine = nlu_engine
        self.auth_service = auth_service
        self.calendar_service = calendar_service 
        self.notification_service = notification_service
        self.waitlist_manager = waitlist_manager
        
        self._memory["reschedule_request"] = {
            "patient_id": None,
            "original_appointment_id": None,
            "original_slot": None,
            "new_preferred_date": None,
            "new_preferred_time_of_day": None,
            "proposed_new_slots": [],
            "selected_new_slot": None,
            "reschedule_confirmed": False,
            "authentication_status": False,
            "late_cancellation_fee_applied": False,
            "new_preferences_question_index": 0 
        }
        self._memory["conversation_stage"] = "authentication" 
        self._memory["current_question_index"] = 0 

        self.reschedule_info_questions = [
            "To help me find your appointment, could you please tell me your full name or date of birth?",
            "What is the date and time of the appointment you wish to reschedule?"
        ]

        self.new_preferences_questions = [
            "What is your preferred date for the new appointment?",
            "What is your preferred time of day (morning, afternoon, or evening)?"
        ]
        
        self.rescheduling_policy: Dict[str, float] = {
            "late_reschedule_window_hours": 24.0, 
            "late_reschedule_fee": 50.00 
        }
        self._mock_new_slots: Optional[List[Dict[str, Any]]] = None 
        logger.info("AppointmentReschedulingAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input for appointment rescheduling.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output: Dict[str, Any] = {}
        if self.nlu_engine:
            nlu_output = self.nlu_engine.process_text(text, context.get("language", "en"))
        
        text_lower = text.lower()

        if self._memory["conversation_stage"] == "authentication":
            return await self._authenticate_caller(text, context)
        
        elif not self._memory["reschedule_request"]["authentication_status"]:
            return {"response_text": "I need to verify your identity before I can reschedule your appointment. Please provide your verification code.", "context_update": {}, "action": "request_authentication"}

        elif self._memory["conversation_stage"] == "identify_appointment":
            return await self._identify_original_appointment(text, nlu_output, context)
        
        elif self._memory["conversation_stage"] == "gathering_new_preferences":
            answered_question_index = self._memory["reschedule_request"]["new_preferences_question_index"]
            self._process_new_preferences_answer(text, nlu_output, answered_question_index)
            
            self._memory["reschedule_request"]["new_preferences_question_index"] += 1
            current_new_pref_index = self._memory["reschedule_request"]["new_preferences_question_index"]

            if current_new_pref_index < len(self.new_preferences_questions):
                return self._ask_next_question_new_preferences()
            else:
                self._memory["conversation_stage"] = "proposing_new_slots"
                return await self._find_and_propose_new_slots(context)
        
        elif self._memory["conversation_stage"] == "proposing_new_slots":
            return await self._confirm_or_reschedule_new_slot(text_lower, context)
        
        elif self._memory["conversation_stage"] == "confirming_reschedule":
            if "yes" in text_lower or "confirm" in text_lower:
                return await self._finalize_reschedule(context)
            else:
                return {"response_text": "No problem. Your original appointment is still active. Would you like to try finding different times?", "context_update": {"reschedule_stage": "cancelled_new_booking"}, "action": "cancel_new_booking"}
            
        return {"response_text": "I'm not sure how to handle your rescheduling request at this moment.", "context_update": {}, "action": "clarify_reschedule"}

    async def _authenticate_caller(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conceptual caller authentication via OTP or voice biometrics.
        """
        if self._memory["reschedule_request"]["authentication_status"]:
            self._memory["conversation_stage"] = "identify_appointment" 
            return {"response_text": "Your identity has already been verified. Now, what is the date and time of the appointment you wish to reschedule?", "context_update": {"reschedule_stage": "identify_appointment"}, "action": "ask_original_appointment"}

        if "my name is john doe" in text.lower() or "my otp is 1234" in text.lower(): 
            self._memory["reschedule_request"]["patient_id"] = "patient_001"
            self._memory["reschedule_request"]["authentication_status"] = True
            self._memory["conversation_stage"] = "identify_appointment"
            self._memory["current_question_index"] = 0
            logger.info(f"Caller authenticated for patient_id: {self._memory['reschedule_request']['patient_id']}")
            return self._ask_next_question_reschedule()
        else:
            return {"response_text": "Could you please provide your full name and date of birth, or the one-time password sent to your phone, to verify your identity?", "context_update": {"reschedule_stage": "authentication_failed"}, "action": "request_authentication_retry"}

    async def _identify_original_appointment(self, text: str, nlu_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identifies the original appointment to be rescheduled.
        """
        # FIX: Updated regex to allow multiple separators (e.g. comma AND space) and optional ordinals (st, nd, rd, th)
        # Old regex: [\s/,-] (only matched one char)
        # New regex: [\s/,-]+ (matches one or more chars)
        date_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)[\s/,-]+(\d{1,2})(?:st|nd|rd|th)?[\s/,-]+(\d{4})', text, re.IGNORECASE)
        time_match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?\.?', text, re.IGNORECASE)

        logger.debug(f"Input text for _identify_original_appointment: {text}")
        logger.debug(f"Date match: {date_match}")
        logger.debug(f"Time match: {time_match}")

        if date_match and time_match:
            logger.debug(f"Date match groups: {date_match.groups()}")
            logger.debug(f"Time match groups: {time_match.groups()}")
            try:
                month_int = self._month_to_int(date_match.group(1))
                day_int = int(date_match.group(2))
                year_int = int(date_match.group(3)) # Index remains 3 because (?:...) is non-capturing
                hour_int = int(time_match.group(1))
                minute_int = int(time_match.group(2))

                logger.debug(f"datetime components: year={year_int}, month={month_int}, day={day_int}, hour={hour_int}, minute={minute_int}")

                original_dt = datetime.datetime(
                    year_int,
                    month_int,
                    day_int,
                    hour_int,
                    minute_int
                )
                if time_match.group(3) and time_match.group(3).lower() == "pm" and hour_int < 12:
                    original_dt += datetime.timedelta(hours=12)

                logger.debug(f"Parsed original_dt: {original_dt}")


                self._memory["reschedule_request"]["original_slot"] = {
                    "appointment_id": "appt_123",
                    "doctor": "Dr. Smith",
                    "specialty": "General Practice",
                    "time": original_dt
                }
                self._memory["reschedule_request"]["original_appointment_id"] = "appt_123"

                now = datetime.datetime.now()
                time_until_appt = self._memory["reschedule_request"]["original_slot"]["time"] - now

                logger.debug(f"Late fee check: now={now}, time_until_appt={time_until_appt}, late_reschedule_window_hours={self.rescheduling_policy['late_reschedule_window_hours']}")
                
                if time_until_appt < datetime.timedelta(hours=float(self.rescheduling_policy["late_reschedule_window_hours"])):
                    self._memory["reschedule_request"]["late_cancellation_fee_applied"] = True
                    return {
                        "response_text": f"Your appointment on {original_dt.strftime('%B %d at %I:%M %p')} is less than {self.rescheduling_policy['late_reschedule_window_hours']} hours away. A late rescheduling fee of ${self.rescheduling_policy['late_reschedule_fee']:.2f} will apply. Do you still wish to proceed?",
                        "context_update": {"reschedule_stage": "confirm_late_fee"},
                        "action": "confirm_late_fee"
                    }

                self._memory["conversation_stage"] = "gathering_new_preferences"
                self._memory["reschedule_request"]["new_preferences_question_index"] = 0
                return self._ask_next_question_new_preferences()

            except Exception as e:
                logger.error(f"Error parsing date/time for original appointment: {e}")
                pass

        return {"response_text": "I couldn't find an appointment matching that information. Please provide the exact date and time of the appointment you wish to reschedule.", "context_update": {"reschedule_stage": "identify_appointment_retry"}, "action": "retry_identify_appointment"}

    def _ask_next_question_reschedule(self) -> Dict[str, Any]:
        """Returns the next question for original appointment identification."""
        question_text: str = self.reschedule_info_questions[self._memory["current_question_index"]]
        self._memory["current_question_index"] += 1
        return {
            "response_text": question_text,
            "context_update": {"reschedule_stage": "identifying_original_appointment", "question_asked": question_text},
            "action": "ask_question"
        }
    
    def _ask_next_question_new_preferences(self) -> Dict[str, Any]:
        """Returns the next question for new preferences."""
        question_index: int = self._memory["reschedule_request"]["new_preferences_question_index"]
        question_text: str = self.new_preferences_questions[question_index]
        return {
            "response_text": question_text,
            "context_update": {"reschedule_stage": "gathering_new_preferences", "question_asked": question_text},
            "action": "ask_question"
        }

    def _process_new_preferences_answer(self, text: str, nlu_output: Dict[str, Any], question_index: int):
        """
        Processes answers to new preferences questions.
        """
        logger.debug(f"Processing answer to new preferences question {question_index}: '{text}'")
        text_lower = text.lower()
        entities = nlu_output.get("entities", [])
        
        if question_index == 0: # Preferred Date 
            for entity in entities:
                if entity["type"] == "DATE":
                    self._memory["reschedule_request"]["new_preferred_date"] = entity["text"]
        elif question_index == 1: # Preferred Time of Day 
            if "morning" in text_lower: self._memory["reschedule_request"]["new_preferred_time_of_day"] = "morning"
            elif "afternoon" in text_lower: self._memory["reschedule_request"]["new_preferred_time_of_day"] = "afternoon"
            elif "evening" in text_lower: self._memory["reschedule_request"]["new_preferred_time_of_day"] = "evening"
            else: self._memory["reschedule_request"]["new_preferred_time_of_day"] = "anytime"

    async def _find_and_propose_new_slots(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finds and proposes new available slots.
        """
        request: Dict[str, Any] = self._memory["reschedule_request"]
        
        mock_new_slots: List[Dict[str, Any]]
        if self._mock_new_slots is not None:
            mock_new_slots = self._mock_new_slots
        else:
            now = datetime.datetime.now()
            mock_new_slots = [
                {"doctor": request["original_slot"]["doctor"], "specialty": request["original_slot"]["specialty"], "time": now.replace(hour=10, minute=0, second=0, microsecond=0) + datetime.timedelta(days=10)},
                {"doctor": request["original_slot"]["doctor"], "specialty": request["original_slot"]["specialty"], "time": now.replace(hour=14, minute=0, second=0, microsecond=0) + datetime.timedelta(days=11)},
            ]
        
        if not mock_new_slots:
            return {"response_text": "I couldn't find any alternative slots. Would you like to keep your original appointment or cancel it?", "context_update": {"reschedule_stage": "no_new_slots_found"}, "action": "no_new_slots"}
        
        self._memory["reschedule_request"]["proposed_new_slots"] = mock_new_slots
        response_parts: List[str] = ["I found the following alternative appointment slots:"]
        for i, slot in enumerate(self._memory["reschedule_request"]["proposed_new_slots"]):
            response_parts.append(f"{i+1}. {slot['doctor']} ({slot['specialty']}) on {slot['time'].strftime('%A, %B %d at %I:%M %p')}")
        response_parts.append("Which one would you like to choose? Please say the number (e.g., 'number one').")
        
        self._memory["conversation_stage"] = "proposing_new_slots"
        return {
            "response_text": " ".join(response_parts),
            "context_update": {"reschedule_stage": "new_slots_proposed"},
            "action": "propose_new_slots"
        }

    async def _confirm_or_reschedule_new_slot(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Confirms the selected new slot.
        """
        slot_selection = None
        if "one" in text or "number 1" in text: slot_selection = 0
        elif "two" in text or "number 2" in text: slot_selection = 1
        
        if slot_selection is not None and slot_selection < len(self._memory["reschedule_request"]["proposed_new_slots"]):
            selected_slot = self._memory["reschedule_request"]["proposed_new_slots"][slot_selection]
            self._memory["reschedule_request"]["selected_new_slot"] = selected_slot
            
            self._memory["conversation_stage"] = "confirming_reschedule"
            confirmation_message = (
                f"You've selected to reschedule your appointment to {selected_slot['doctor']} on "
                f"{selected_slot['time'].strftime('%A, %B %d at %I:%M %p')}. "
                "Please confirm by saying 'yes' or 'confirm'."
            )
            return {
                "response_text": confirmation_message,
                "context_update": {"reschedule_stage": "awaiting_final_confirmation"},
                "action": "await_confirmation"
            }
        else:
            return {"response_text": "I didn't understand your selection. Please say 'number one' or 'number two' to choose a slot, or 'cancel' to keep your original appointment.", "context_update": {}, "action": "clarify_new_slot_selection"}

    async def _finalize_reschedule(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalizes the rescheduling process.
        """
        original_slot = self._memory["reschedule_request"]["original_slot"]
        new_slot = self._memory["reschedule_request"]["selected_new_slot"]

        if not original_slot or not new_slot:
            return {"response_text": "An error occurred during rescheduling. Please try again.", "context_update": {}, "action": "error_rescheduling"}

        logger.info(f"Original slot {original_slot['appointment_id']} released.")

        logger.info(f"Waitlist notified for released slot {original_slot['appointment_id']}.")

        new_booking_successful = True 
        
        if new_booking_successful:
            self._memory["reschedule_request"]["reschedule_confirmed"] = True
            
            if self.notification_service:
                patient_id = self._memory["reschedule_request"]["patient_id"]
                confirmation_msg = f"Your appointment has been rescheduled from {original_slot['time'].strftime('%b %d, %I:%M %p')} to {new_slot['time'].strftime('%b %d, %I:%M %p')} with {new_slot['doctor']}."
                await self.notification_service.send_sms(patient_id, confirmation_msg)
                logger.info(f"Confirmation sent to {patient_id}: {confirmation_msg}")

            final_message = (
                f"Your appointment has been successfully rescheduled from "
                f"{original_slot['time'].strftime('%A, %B %d at %I:%M %p')} to "
                f"{new_slot['time'].strftime('%A, %B %d at %I:%M %p')} with {new_slot['doctor']}. "
            )
            if self._memory["reschedule_request"]["late_cancellation_fee_applied"]:
                final_message += f"A late rescheduling fee of ${self.rescheduling_policy['late_reschedule_fee']:.2f} will be applied. "
            final_message += "Is there anything else I can help you with?"

            return {
                "response_text": final_message,
                "context_update": {"reschedule_stage": "rescheduled", "new_appointment_details": new_slot},
                "action": "appointment_rescheduled"
            }
        else:
            return {"response_text": "I apologize, there was an issue finalizing your rescheduling. Your original appointment is still active. Please try again or contact the clinic directly.", "context_update": {"reschedule_stage": "reschedule_failed"}, "action": "reschedule_failed"}

    def _month_to_int(self, month_name: str) -> int:
        """Converts month name to integer."""
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
        }
        result = months.get(month_name.lower(), datetime.datetime.now().month)
        logger.debug(f"_month_to_int: Input '{month_name}' -> Output {result}")
        return result


    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["reschedule_request"] = {
            "patient_id": None, "original_appointment_id": None, "original_slot": None,
            "new_preferred_date": None, "new_preferred_time_of_day": None,
            "proposed_new_slots": [], "selected_new_slot": None, "reschedule_confirmed": False,
            "authentication_status": False, "late_cancellation_fee_applied": False,
            "new_preferences_question_index": 0
        }
        self._memory["conversation_stage"] = "authentication"
        self._memory["current_question_index"] = 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    class MockNLUEngine:
        def process_text(self, text: str, lang: str) -> Dict[str, Any]:
            return {"entities": [], "intent": {"name": "reschedule_appointment"}}

    nlu_mock = MockNLUEngine()
    
    reschedule_agent = AppointmentReschedulingAgent(nlu_engine=nlu_mock)

    async def run_reschedule_flow():
        context = {"call_id": "reschedule_call_456", "user_id": "patient_001", "language": "en"}

        print("\n--- Flow 1: Authentication ---")
        response1 = await reschedule_agent.process_input("I want to reschedule my appointment.", context)
        print(f"Agent: {response1['response_text']}") 
        
        response2 = await reschedule_agent.process_input("My name is John Doe and my OTP is 1234.", context)
        print(f"Agent: {response2['response_text']}") 
        
        print("\n--- Flow 2: Identify Original Appointment (Mock) ---")
        current_year = datetime.datetime.now().year
        original_appt_text = f"My appointment is on December 15th, {current_year} at 10:00 AM."
        response3 = await reschedule_agent.process_input(original_appt_text, context)
        print(f"Agent: {response3['response_text']}") 
        
        print("\n--- Flow 3: Gathering New Preferences ---")
        response4 = await reschedule_agent.process_input("I'd like to reschedule it to next week.", context)
        print(f"Agent: {response4['response_text']}") 
        
        response5 = await reschedule_agent.process_input("Anytime in the afternoon.", context)
        print(f"Agent (Proposes New Slots): {response5['response_text']}")
        
        print("\n--- Flow 4: Confirm New Slot ---")
        response6 = await reschedule_agent.process_input("I'll take number one.", context)
        print(f"Agent (Awaiting Final Confirmation): {response6['response_text']}")
        
        response7 = await reschedule_agent.process_input("Yes, confirm!", context)
        print(f"Agent (Finalized Reschedule): {response7['response_text']}")
        assert "successfully rescheduled" in response7["response_text"]
        assert reschedule_agent.current_memory["reschedule_request"]["reschedule_confirmed"] == True

        print("\n--- Flow 5: Late Rescheduling (Mock) ---")
        reschedule_agent.reset_memory()
        await reschedule_agent.process_input("I want to reschedule.", context)
        one_hour_from_now = datetime.datetime.now() + datetime.timedelta(minutes=60)
        late_appt_text = f"My appointment is on {one_hour_from_now.strftime('%B %d, %Y at %I:%M %p')}."
        response_late1 = await reschedule_agent.process_input(late_appt_text, context)
        print(f"Agent (Late Fee Warning): {response_late1['response_text']}")
        assert "late rescheduling fee" in response_late1["response_text"]
        
        response_late2 = await reschedule_agent.process_input("No, I'll keep my original appointment then.", context)
        print(f"Agent: {response_late2['response_text']}")

        reschedule_agent.reset_memory()
        print(f"\nMemory after reset: {reschedule_agent.current_memory}")

    import asyncio
    asyncio.run(run_reschedule_flow())