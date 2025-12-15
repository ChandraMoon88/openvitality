import logging
import datetime
from typing import Dict, Any, List, Optional
import asyncio
import re

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class AppointmentCancellationAgent(BaseAgent):
    """
    A specialized AI agent for handling the cancellation of appointments.
    It manages caller authentication, policy checks, refund processing,
    waitlist notifications, and re-booking offers.
    """
    def __init__(self, nlu_engine: Any = None, auth_service: Any = None, calendar_service: Any = None, notification_service: Any = None, payment_gateway: Any = None, waitlist_manager: Any = None):
        super().__init__(
            name="AppointmentCancellationAgent",
            description="Manages the cancellation of medical appointments.",
            persona={
                "role": "professional and understanding cancellation assistant",
                "directives": [
                    "Verify caller identity with 2FA before canceling sensitive appointments.",
                    "Collect the reason for cancellation for service improvement.",
                    "Process refunds according to clinic policy.",
                    "Release the canceled slot promptly to make it available for others.",
                    "Notify patients on the waitlist about newly available slots.",
                    "Offer options for re-booking or alternative services.",
                    "Provide clear information about cancellation charges if applicable."
                ],
                "style": "professional, empathetic, clear, efficient"
            }
        )
        self.nlu_engine = nlu_engine
        self.auth_service = auth_service
        self.calendar_service = calendar_service 
        self.notification_service = notification_service
        self.payment_gateway = payment_gateway
        self.waitlist_manager = waitlist_manager
        
        self._memory["cancellation_request"] = {
            "patient_id": None,
            "appointment_id": None,
            "appointment_details": None,
            "authentication_status": False,
            "cancellation_reason": None,
            "refund_due": 0.0,
            "cancellation_confirmed": False,
            "rebooking_offered": False,
            "exit_survey_offered": False
        }
        self._memory["conversation_stage"] = "authentication" 
        self._memory["current_question_index"] = 0

        self.cancellation_info_questions = [
            "To help me find your appointment, could you please tell me your full name or date of birth for verification?",
            "What is the date and time of the appointment you wish to cancel?"
        ]
        
        self.cancellation_policy = {
            "no_charge_window_hours": 24, 
            "cancellation_fee_amount": 50.00 
        }
        logger.info("AppointmentCancellationAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input for appointment cancellation.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = self.nlu_engine.process_text(text, context.get("language", "en"))
        
        text_lower = text.lower()

        if self._memory["conversation_stage"] == "authentication":
            return await self._authenticate_caller(text, context)
        
        elif not self._memory["cancellation_request"]["authentication_status"]:
            return {"response_text": "I need to verify your identity before I can cancel your appointment. Please provide your verification code.", "context_update": {}, "action": "request_authentication"}

        elif self._memory["conversation_stage"] == "identify_appointment":
            return await self._identify_appointment_to_cancel(text, nlu_output, context)
        
        elif self._memory["conversation_stage"] == "gathering_reason":
            self._memory["cancellation_request"]["cancellation_reason"] = text
            self._memory["conversation_stage"] = "confirming_cancellation"
            return self._ask_final_confirmation(context)
        
        elif self._memory["conversation_stage"] == "confirming_cancellation":
            if "yes" in text_lower or "confirm" in text_lower:
                return await self._finalize_cancellation(context)
            else:
                return {"response_text": "No problem, your appointment has not been canceled. Is there anything else I can help you with?", "context_update": {"cancellation_stage": "not_canceled"}, "action": "do_not_cancel"}
            
        return {"response_text": "I'm not sure how to handle your cancellation request at this moment.", "context_update": {}, "action": "clarify_cancellation"}

    async def _authenticate_caller(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conceptual caller authentication via 2FA.
        """
        if self._memory["cancellation_request"]["authentication_status"]:
            self._memory["conversation_stage"] = "identify_appointment"
            return {"response_text": "Your identity has already been verified. What is the date and time of the appointment you wish to cancel?", "context_update": {"cancellation_stage": "identify_appointment"}, "action": "ask_appointment_details"}

        if "my name is jane doe" in text.lower() or "my otp is 5678" in text.lower(): 
            self._memory["cancellation_request"]["patient_id"] = "patient_002"
            self._memory["cancellation_request"]["authentication_status"] = True
            self._memory["conversation_stage"] = "identify_appointment"
            self._memory["current_question_index"] = 1 
            logger.info(f"Caller authenticated for patient_id: {self._memory['cancellation_request']['patient_id']}")
            return self._ask_next_question_cancel()
        else:
            return {"response_text": "Could you please provide your full name and date of birth, or the one-time password sent to your phone, to securely verify your identity?", "context_update": {"cancellation_stage": "authentication_failed"}, "action": "request_authentication_retry"}

    async def _identify_appointment_to_cancel(self, text: str, nlu_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identifies the appointment to be cancelled from user input.
        """
        date_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2})[\s/,-]+(\d{1,2})(?:st|nd|rd|th)?[\s/,-]+(\d{4})', text, re.IGNORECASE)
        
        # FIX: Strict Time Regex to avoid matching date numbers. Requires Colon OR AM/PM.
        # Format 1: HH:MM (Group 1, 2)
        # Format 2: HH AM/PM (Group 3, 4)
        time_match = re.search(r'(?:(\d{1,2}):(\d{2}))|(?:(\d{1,2})\s*(am|pm))', text, re.IGNORECASE)

        if date_match and time_match:
            try:
                current_year = datetime.datetime.now().year
                year = int(date_match.group(3)) if date_match.group(3) else current_year
                
                if time_match.group(1): # Matched HH:MM
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))
                    ampm = None
                else: # Matched HH AM/PM
                    hour = int(time_match.group(3))
                    minute = 0
                    ampm = time_match.group(4)

                appt_dt = datetime.datetime(
                    year, 
                    self._month_to_int(date_match.group(1)), 
                    int(date_match.group(2)), 
                    hour, 
                    minute
                )
                
                if ampm and ampm.lower() == "pm" and hour < 12:
                    appt_dt += datetime.timedelta(hours=12)

                self._memory["cancellation_request"]["appointment_details"] = {
                    "appointment_id": "appt_456",
                    "doctor": "Dr. Miller",
                    "specialty": "Pediatrics",
                    "time": appt_dt,
                    "cost": 100.00, 
                    "paid": True 
                }
                self._memory["cancellation_request"]["appointment_id"] = "appt_456"
                
                now = datetime.datetime.now()
                time_until_appt = self._memory["cancellation_request"]["appointment_details"]["time"] - now
                
                if time_until_appt < datetime.timedelta(hours=self.cancellation_policy["no_charge_window_hours"]):
                    self._memory["cancellation_request"]["refund_due"] = 0.0 
                    return {
                        "response_text": f"Your appointment on {appt_dt.strftime('%B %d at %I:%M %p')} is less than {self.cancellation_policy['no_charge_window_hours']} hours away. A cancellation fee of ${self.cancellation_policy['cancellation_fee_amount']:.2f} will apply, meaning no refund on your payment of ${self._memory['cancellation_request']['appointment_details']['cost']:.2f}. Do you still wish to proceed with the cancellation?",
                        "context_update": {"cancellation_stage": "confirm_late_fee"},
                        "action": "confirm_late_fee"
                    }
                else:
                    self._memory["cancellation_request"]["refund_due"] = self._memory["cancellation_request"]["appointment_details"]["cost"]
                    # Explicitly update stage to prevent test mismatch
                    self._memory["conversation_stage"] = "gathering_reason"
                    return {
                        "response_text": f"You're canceling your appointment on {appt_dt.strftime('%B %d at %I:%M %p')}. A full refund of ${self._memory['cancellation_request']['refund_due']:.2f} will be processed. Why are you canceling today?",
                        "context_update": {"cancellation_stage": "gathering_reason"},
                        "action": "ask_cancellation_reason"
                    }

            except Exception as e:
                logger.error(f"Error parsing date/time for appointment to cancel: {e}")
                pass

        return {"response_text": "I couldn't find an appointment matching that information. Please provide the exact date and time of the appointment you wish to cancel.", "context_update": {"cancellation_stage": "identify_appointment_retry"}, "action": "retry_identify_appointment"}

    def _ask_next_question_cancel(self) -> Dict[str, Any]:
        """Returns the next question in the cancellation flow."""
        question_text = self.cancellation_info_questions[self._memory["current_question_index"]]
        self._memory["current_question_index"] += 1
        return {
            "response_text": question_text,
            "context_update": {"cancellation_stage": "identifying_appointment", "question_asked": question_text},
            "action": "ask_question"
        }
    
    def _ask_final_confirmation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Asks for final confirmation before canceling."""
        appt_details = self._memory["cancellation_request"]["appointment_details"]
        if self._memory["cancellation_request"]["refund_due"] > 0:
            refund_msg = f"A refund of ${self._memory['cancellation_request']['refund_due']:.2f} will be processed."
        else:
            refund_msg = "No refund is due for this late cancellation."

        return {
            "response_text": f"You are about to cancel your appointment with {appt_details['doctor']} on {appt_details['time'].strftime('%A, %B %d at %I:%M %p')}. {refund_msg} Do you wish to proceed?",
            "context_update": {"cancellation_stage": "confirm_final"},
            "action": "confirm_cancellation"
        }

    async def _finalize_cancellation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalizes the cancellation process.
        """
        appt_details = self._memory["cancellation_request"]["appointment_details"]
        patient_id = self._memory["cancellation_request"]["patient_id"]

        if not appt_details or not patient_id:
            return {"response_text": "An error occurred during cancellation. Please try again.", "context_update": {}, "action": "error_cancellation"}

        cancellation_successful = True # Mock success
        
        if cancellation_successful:
            self._memory["cancellation_request"]["cancellation_confirmed"] = True
            
            if self._memory["cancellation_request"]["refund_due"] > 0 and self.payment_gateway:
                await self.payment_gateway.process_refund(patient_id, self._memory["cancellation_request"]["refund_due"])
                logger.info(f"Processed refund of ${self._memory['cancellation_request']['refund_due']:.2f} for {patient_id}.")
            
            if self.waitlist_manager:
                await self.waitlist_manager.notify_available_slot(appt_details)
                logger.info(f"Notified waitlist for slot at {appt_details['time']}.")

            final_message = (
                f"Your appointment with {appt_details['doctor']} on "
                f"{appt_details['time'].strftime('%A, %B %d at %I:%M %p')} has been successfully canceled. "
            )
            if self._memory["cancellation_request"]["refund_due"] > 0:
                final_message += f"A refund of ${self._memory['cancellation_request']['refund_due']:.2f} has been processed. "
            else:
                final_message += "No refund was processed due to late cancellation. "
            
            final_message += f"Reason provided: '{self._memory['cancellation_request']['cancellation_reason']}'. "
            final_message += "Would you like to re-book, or provide feedback via a quick survey?"

            return {
                "response_text": final_message,
                "context_update": {"cancellation_stage": "canceled", "offer_rebook": True, "offer_survey": True},
                "action": "appointment_canceled"
            }
        else:
            return {"response_text": "I apologize, there was an issue finalizing your cancellation. Please try again or contact the clinic directly.", "context_update": {"cancellation_stage": "cancellation_failed"}, "action": "cancellation_failed"}

    def _month_to_int(self, month_name: str) -> int:
        """Converts month name to integer."""
        if month_name.isdigit():
            return int(month_name)
            
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
        }
        return months.get(month_name.lower(), datetime.datetime.now().month) 


    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["cancellation_request"] = {
            "patient_id": None, "appointment_id": None, "appointment_details": None,
            "authentication_status": False, "cancellation_reason": None,
            "refund_due": 0.0, "cancellation_confirmed": False,
            "rebooking_offered": False, "exit_survey_offered": False
        }
        self._memory["conversation_stage"] = "authentication"
        self._memory["current_question_index"] = 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    class MockNLUEngine:
        def process_text(self, text, lang):
            return {"entities": [], "intent": {"name": "cancel_appointment"}}

    nlu_mock = MockNLUEngine()
    
    cancellation_agent = AppointmentCancellationAgent(nlu_engine=nlu_mock)

    async def run_cancellation_flow():
        context = {"call_id": "cancel_call_789", "user_id": "patient_002", "language": "en"}

        print("\n--- Flow 1: Authentication ---")
        response1 = await cancellation_agent.process_input("I want to cancel my appointment.", context)
        print(f"Agent: {response1['response_text']}") 
        
        response2 = await cancellation_agent.process_input("My name is Jane Doe and my OTP is 5678.", context)
        print(f"Agent: {response2['response_text']}") 
        
        print("\n--- Flow 2: Identify Appointment & Early Cancellation ---")
        five_days_from_now = datetime.datetime.now() + datetime.timedelta(days=5)
        early_appt_text = f"My appointment is on {five_days_from_now.strftime('%B %d, %Y at 10 AM')}."
        response3 = await cancellation_agent.process_input(early_appt_text, context)
        print(f"Agent: {response3['response_text']}") 
        assert "full refund" in response3["response_text"]
        
        response4 = await cancellation_agent.process_input("I have a scheduling conflict.", context)
        print(f"Agent: {response4['response_text']}") 
        
        response5 = await cancellation_agent.process_input("Yes, proceed with cancellation.", context)
        print(f"Agent (Finalized Cancellation): {response5['response_text']}")
        assert "successfully canceled" in response5["response_text"]
        assert cancellation_agent.current_memory["cancellation_request"]["cancellation_confirmed"] == True
        assert cancellation_agent.current_memory["cancellation_request"]["refund_due"] > 0

        print("\n--- Flow 3: Late Cancellation (Mock) ---")
        cancellation_agent.reset_memory()
        await cancellation_agent.process_input("I need to cancel an appointment.", context)
        await cancellation_agent.process_input("Jane Doe, OTP 5678.", context)
        
        one_hour_from_now = datetime.datetime.now() + datetime.timedelta(minutes=60)
        late_appt_text = f"My appointment is on {one_hour_from_now.strftime('%B %d, %Y at %I:%M %p')}."
        response_late1 = await cancellation_agent.process_input(late_appt_text, context)
        print(f"Agent (Late Fee Warning): {response_late1['response_text']}")
        assert "cancellation fee" in response_late1["response_text"]
        
        response_late2 = await cancellation_agent.process_input("Yes, I understand and still want to cancel.", context)
        print(f"Agent: {response_late2['response_text']}") 
        assert cancellation_agent.current_memory["cancellation_request"]["refund_due"] == 0.0

        response_late3 = await cancellation_agent.process_input("I no longer need the appointment.", context)
        print(f"Agent: {response_late3['response_text']}")

        response_late4 = await cancellation_agent.process_input("Yes, cancel it.", context)
        print(f"Agent (Finalized Late Cancellation): {response_late4['response_text']}")
        assert "No refund was processed due to late cancellation" in response_late4["response_text"]

        cancellation_agent.reset_memory()
        print(f"\nMemory after reset: {cancellation_agent.current_memory}")

    import asyncio
    asyncio.run(run_cancellation_flow())