import logging
import datetime
from typing import Dict, Any, List, Optional
import asyncio
import re

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class MedicationReminderAgent(BaseAgent):
    """
    A specialized AI agent for medication adherence tracking and management.
    It helps users remember to take their medication, checks for interactions,
    predicts refills, and monitors for side effects.
    """
    def __init__(self, task_scheduler: Any = None, drug_db: Any = None, notification_service: Any = None):
        super().__init__(
            name="MedicationReminderAgent",
            description="Manages medication reminders and adherence tracking.",
            persona={
                "role": "supportive and vigilant medication assistant",
                "directives": [
                    "Ensure users take medication as prescribed.",
                    "Provide timely reminders through preferred channels.",
                    "Warn about potential drug interactions.",
                    "Monitor for and report new side effects.",
                    "Encourage consistent adherence through positive reinforcement.",
                    "Emphasize consulting a doctor or pharmacist before changing medication regimens."
                ],
                "style": "encouraging, clear, persistent"
            }
        )
        self.task_scheduler = task_scheduler
        self.drug_db = drug_db
        self.notification_service = notification_service
        
        self._memory["medications"] = {} # {med_name: {dosage, frequency, last_taken, next_due, pills_left, adherence_streak}}
        self._memory["conversation_stage"] = "greeting" # greeting, adding_med, reviewing_schedule, side_effect_monitoring
        
        logger.info("MedicationReminderAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input related to medication reminders.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        text_lower = text.lower()
        
        if self._memory["conversation_stage"] == "greeting":
            self._memory["conversation_stage"] = "main_menu"
            return {
                "response_text": "Hello, I'm your medication assistant. How can I help you today? Would you like to add a new medication, review your schedule, or report a side effect?",
                "context_update": {"med_rem_stage": "main_menu"},
                "action": "prompt_main_menu"
            }
        
        elif self._memory["conversation_stage"] == "main_menu":
            if "add" in text_lower and ("medication" in text_lower or "new" in text_lower):
                self._memory["conversation_stage"] = "adding_med"
                return {"response_text": "Okay, what is the name of the medication you'd like to add?", "context_update": {"med_rem_stage": "add_name"}, "action": "ask_med_name"}
            elif "review" in text_lower and ("schedule" in text_lower or "meds" in text_lower):
                return self._review_medication_schedule()
            elif "side effect" in text_lower or "symptom" in text_lower:
                self._memory["conversation_stage"] = "side_effect_monitoring"
                return {"response_text": "I can help with that. What new symptoms or side effects are you experiencing?", "context_update": {"med_rem_stage": "report_side_effect"}, "action": "ask_side_effect"}
            elif "took" in text_lower or "taken" in text_lower:
                return self._confirm_medication_taken(text_lower)
            
        elif self._memory["conversation_stage"] == "adding_med":
            return await self._add_medication_flow(text_lower, context)
        
        elif self._memory["conversation_stage"] == "side_effect_monitoring":
            return self._report_side_effect(text_lower, context)
            
        return {"response_text": "I didn't quite understand that. Please tell me if you want to add a medication, review schedule, or report a side effect.", "context_update": {}, "action": "clarify_med_rem"}

    def _review_medication_schedule(self) -> Dict[str, Any]:
        """Reviews the user's current medication schedule."""
        if not self._memory["medications"]:
            return {"response_text": "You currently don't have any medications scheduled with me. Would you like to add one?", "context_update": {}, "action": "offer_add_med"}
        
        response_parts = ["Here is your current medication schedule:"]
        for med_name, details in self._memory["medications"].items():
            response_parts.append(f"- {med_name.capitalize()}: {details['dosage']} {details['frequency']}.")
            if details["next_due"]:
                response_parts.append(f" Next dose due on {details['next_due'].strftime('%A at %I:%M %p')}.")
            if details["adherence_streak"] > 0:
                response_parts.append(f" Your adherence streak is {details['adherence_streak']} days!")
        
        return {
            "response_text": " ".join(response_parts),
            "context_update": {"med_rem_stage": "reviewed_schedule"},
            "action": "display_schedule"
        }

    async def _add_medication_flow(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Manages the step-by-step process of adding a new medication."""
        current_step = self._memory.get("add_med_step", "name")
        new_med_info = self._memory.get("new_med_info", {})
        response_text = "I'm having trouble adding that medication. Please try again."
        action = "retry_add_med"
        
        text_lower = text.lower() # Normalize input

        if current_step == "name":
            new_med_info["name"] = text.title() 
            self._memory["new_med_info"] = new_med_info
            self._memory["add_med_step"] = "dosage"
            response_text = f"Okay, you're adding {new_med_info['name']}. What is the dosage (e.g., '200mg', 'one pill')?"
            action = "ask_dosage"
        elif current_step == "dosage":
            new_med_info["dosage"] = text
            self._memory["new_med_info"] = new_med_info
            self._memory["add_med_step"] = "frequency"
            response_text = f"And how often should you take {new_med_info['name']}? (e.g., 'twice a day', 'every 8 hours')"
            action = "ask_frequency"
        elif current_step == "frequency":
            new_med_info["frequency"] = text
            
            if self.drug_db:
                existing_meds = list(self._memory["medications"].keys())
                if existing_meds:
                    interaction_warning = await self._check_drug_interactions(new_med_info["name"], existing_meds)
                    if interaction_warning:
                        response_text = f"Before I add {new_med_info['name']}, a potential interaction with {', '.join(existing_meds)} was detected: {interaction_warning}. Please consult your doctor or pharmacist immediately. Should I still add it?"
                        self._memory["add_med_step"] = "confirm_add_with_warning"
                        # Save state so frequency is available in next step
                        self._memory["new_med_info"] = new_med_info 
                        return {"response_text": response_text, "context_update": {"med_rem_stage": "confirm_add_with_warning"}, "action": "confirm_add_with_warning"}

            # If no warning or confirmed, proceed to add
            self._memory["medications"][new_med_info["name"].lower()] = {
                "dosage": new_med_info["dosage"],
                "frequency": new_med_info["frequency"],
                "last_taken": None,
                "next_due": self._calculate_next_due(new_med_info["frequency"]),
                "pills_left": None, 
                "adherence_streak": 0,
                "side_effects": []
            }
            if self.task_scheduler:
                await self.task_scheduler.schedule_task(
                    "medication_reminder", 
                    self._memory["medications"][new_med_info["name"].lower()]["next_due"],
                    payload={"medication": new_med_info["name"], "user_id": context.get("user_id")}
                )

            response_text = f"Great! I've added {new_med_info['name']} to your schedule. I will remind you as per your frequency. Anything else?"
            action = "medication_added"
            self._memory["conversation_stage"] = "main_menu"
            self._memory.pop("new_med_info", None)
            self._memory.pop("add_med_step", None)
        
        elif current_step == "confirm_add_with_warning":
            # Prioritize negative check first
            if "no" in text_lower or "don't" in text_lower or "cancel" in text_lower:
                response_text = f"Understood. {new_med_info['name']} was not added. Anything else I can help with?"
                action = "medication_not_added"
            elif "yes" in text_lower or "add" in text_lower:
                self._memory["medications"][new_med_info["name"].lower()] = {
                    "dosage": new_med_info["dosage"], "frequency": new_med_info["frequency"],
                    "last_taken": None, "next_due": self._calculate_next_due(new_med_info["frequency"]),
                    "pills_left": None, "adherence_streak": 0, "side_effects": []
                }
                if self.task_scheduler:
                    await self.task_scheduler.schedule_task("medication_reminder", self._memory["medications"][new_med_info["name"].lower()]["next_due"], payload={"medication": new_med_info["name"], "user_id": context.get("user_id")})
                response_text = f"Okay, {new_med_info['name']} has been added. Please remember to consult a professional about the interaction. Anything else?"
                action = "medication_added_with_warning"
            else:
                return {"response_text": "Please answer yes or no. Should I add the medication?", "context_update": {}, "action": "ask_confirm_retry"}
            
            self._memory["conversation_stage"] = "main_menu"
            self._memory.pop("new_med_info", None)
            self._memory.pop("add_med_step", None)

        return {
            "response_text": response_text,
            "context_update": {"med_rem_stage": "adding_med_flow", "current_step": current_step},
            "action": action
        }

    async def _check_drug_interactions(self, new_med_name: str, existing_meds: List[str]) -> Optional[str]:
        """
        Conceptual method to check for drug-drug interactions.
        """
        if self.drug_db:
            for existing_med in existing_meds:
                interaction = await self.drug_db.check_interaction(new_med_name, existing_med)
                if interaction:
                    logger.warning(f"Potential interaction: {new_med_name} and {existing_med}. Details: {interaction}")
                    return f"Potential interaction between {new_med_name} and {existing_med}. ({interaction})"
        return None

    def _calculate_next_due(self, frequency: str) -> datetime.datetime:
        """
        Calculates the next due time for a medication based on its frequency.
        """
        now = datetime.datetime.now()
        text_lower = frequency.lower()
        
        match = re.search(r'every\s*(\d+)\s*hours', text_lower)
        if match:
            hours = int(match.group(1))
            return now + datetime.timedelta(hours=hours)
            
        if "once a day" in text_lower or "daily" in text_lower:
            return now + datetime.timedelta(days=1)
        if "twice a day" in text_lower:
            return now + datetime.timedelta(hours=12) 
            
        return now + datetime.timedelta(hours=24)

    def _confirm_medication_taken(self, text: str) -> Dict[str, Any]:
        """Confirms that a user has taken their medication."""
        matched_med = None
        for med_name in self._memory["medications"].keys():
            if med_name in text:
                matched_med = med_name
                break
        
        if matched_med:
            med_details = self._memory["medications"][matched_med]
            med_details["last_taken"] = datetime.datetime.now()
            med_details["next_due"] = self._calculate_next_due(med_details["frequency"])
            med_details["adherence_streak"] += 1 
            
            if self.task_scheduler:
                asyncio.create_task(self.task_scheduler.schedule_task(
                    "medication_reminder", 
                    med_details["next_due"],
                    payload={"medication": matched_med, "user_id": "current_user_id"}
                ))

            return {
                "response_text": f"Great! I've noted that you've taken your {matched_med}. Keep up the great work! Your adherence streak is now {med_details['adherence_streak']} days.",
                "context_update": {"med_rem_stage": "confirmed_taken"},
                "action": "confirm_adherence"
            }
        
        return {
            "response_text": "Which medication did you take? Please tell me the name.",
            "context_update": {"med_rem_stage": "clarify_med_taken"},
            "action": "clarify_med_taken"
        }

    def _report_side_effect(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Records reported side effects and potentially flags for review."""
        if self._memory["medications"]:
            first_med = next(iter(self._memory["medications"]))
            self._memory["medications"][first_med]["side_effects"].append(text)
            logger.warning(f"User reported side effect for {first_med}: '{text}'")
            return {
                "response_text": f"Thank you for reporting that. I've noted your side effect: '{text}'. Please monitor it, and if it worsens or is severe, contact your doctor immediately. Would you like to review your medications?",
                "context_update": {"med_rem_stage": "side_effect_recorded"},
                "action": "side_effect_recorded"
            }
        return {"response_text": "I can only track side effects for medications I have on record. Would you like to add one?", "context_update": {}, "action": "offer_add_med"}


    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["medications"] = {}
        self._memory["conversation_stage"] = "greeting"
        self._memory.pop("new_med_info", None)
        self._memory.pop("add_med_step", None)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    class MockTaskScheduler:
        async def schedule_task(self, task_type: str, due_time: datetime.datetime, payload: Dict[str, Any]):
            logger.info(f"MOCK: Scheduled {task_type} for {due_time} with payload {payload}")

    class MockFDADrugDB:
        async def check_interaction(self, med1: str, med2: str) -> Optional[str]:
            if "ibuprofen" in med1.lower() and "aspirin" in med2.lower():
                return "Increased risk of bleeding."
            return None

    class MockNotificationService:
        async def send_sms(self, to: str, message: str):
            logger.info(f"MOCK: Sending SMS to {to}: {message}")
        async def send_voice_call(self, to: str, message: str):
            logger.info(f"MOCK: Initiating voice call to {to}: {message}")

    task_scheduler_mock = MockTaskScheduler()
    drug_db_mock = MockFDADrugDB()
    notification_service_mock = MockNotificationService()
    
    med_agent = MedicationReminderAgent(
        task_scheduler=task_scheduler_mock,
        drug_db=drug_db_mock,
        notification_service=notification_service_mock
    )

    async def run_med_rem_flow():
        context = {"call_id": "med_rem_call", "user_id": "user_med", "language": "en"}

        print("\n--- Flow 1: Add Medication ---")
        resp1 = await med_agent.process_input("Hello, I need to add a new medication.", context)
        print(f"Agent: {resp1['response_text']}")

        resp2 = await med_agent.process_input("It's called Ibuprofen.", context)
        print(f"Agent: {resp2['response_text']}")

        resp3 = await med_agent.process_input("200mg.", context)
        print(f"Agent: {resp3['response_text']}")

        resp4 = await med_agent.process_input("Every 6 hours.", context)
        print(f"Agent: {resp4['response_text']}")
        
        print("\n--- Flow 2: Confirm Taken ---")
        resp5 = await med_agent.process_input("I just took my Ibuprofen.", context)
        print(f"Agent: {resp5['response_text']}")
        assert med_agent.current_memory["medications"]["ibuprofen"]["adherence_streak"] == 1

        print("\n--- Flow 3: Add Medication with Interaction ---")
        resp_add_other1 = await med_agent.process_input("I also take Aspirin.", context)
        print(f"Agent: {resp_add_other1['response_text']}")

        resp_add_other2 = await med_agent.process_input("81mg.", context)
        print(f"Agent: {resp_add_other2['response_text']}")

        resp_add_other3 = await med_agent.process_input("Once a day.", context)
        print(f"Agent: {resp_add_other3['response_text']}")

        resp_add_other4 = await med_agent.process_input("Yes, add it anyway.", context)
        print(f"Agent: {resp_add_other4['response_text']}")

        print("\n--- Flow 4: Review Schedule ---")
        resp_review = await med_agent.process_input("Can I review my medication schedule?", context)
        print(f"Agent: {resp_review['response_text']}")
        assert "Ibuprofen" in resp_review["response_text"]
        assert "Aspirin" in resp_review["response_text"]

        print("\n--- Flow 5: Report Side Effect ---")
        resp_se = await med_agent.process_input("I'm having some stomach upset.", context)
        print(f"Agent: {resp_se['response_text']}")
        assert "stomach upset" in med_agent.current_memory["medications"]["ibuprofen"]["side_effects"][0]
        
        med_agent.reset_memory()
        print(f"\nMemory after reset: {med_agent.current_memory}")

    import asyncio
    asyncio.run(run_med_rem_flow())