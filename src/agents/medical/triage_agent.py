import logging
from typing import Dict, Any, List, Tuple
from enum import Enum, auto
import re # FIX: Added missing import

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class TriageLevel(Enum):
    RED = auto()    # Immediate ambulance/ER
    ORANGE = auto() # ER within 10 minutes
    YELLOW = auto() # See doctor within 1 hour
    GREEN = auto()  # Routine appointment OK
    BLUE = auto()   # Self-care advice

class TriageAgent(BaseAgent):
    """
    The Triage Agent is the gatekeeper, deciding the urgency of a user's
    medical concern and routing them appropriately. It implements a simplified
    triage decision process based on reported symptoms.
    """
    def __init__(self, nlu_engine: Any = None, emergency_router: Any = None): 
        super().__init__(
            name="TriageAgent",
            description="Decides the urgency of a medical concern.",
            persona={
                "role": "compassionate medical triage assistant",
                "directives": [
                    "Prioritize patient safety above all else.",
                    "Never provide a diagnosis.",
                    "Never discourage seeking emergency care.",
                    "Ask clarifying questions to determine urgency.",
                    "Use clear, simple language."
                ],
                "style": "calm, empathetic, precise"
            }
        )
        self.nlu_engine = nlu_engine
        self.emergency_router = emergency_router
        self._memory["triage_state"] = "initial" # e.g., initial, asking_severity, asking_duration
        self._memory["reported_symptoms"] = []
        self._memory["urgency_factors"] = {}
        self._memory["question_history"] = []
        self._memory["current_question_index"] = 0

        self.triage_questions = [
            "What brings you here today? Please describe your main concern.",
            "When did these symptoms start?",
            "On a scale of 1 to 10, with 10 being the worst, how severe is your pain or discomfort?",
            "Are you experiencing any other symptoms, even if they seem minor?",
            "Have you taken any medication for this, and if so, what and when?"
        ]
        
        self.red_flags = {
            "chest pain": ["chest pain", "tightness", "pressure", "squeezing", "left arm"],
            "breathing difficulty": ["can't breathe", "shortness of breath", "gasping", "choking"],
            "severe bleeding": ["severe bleeding", "gushing blood", "uncontrollable bleeding"],
            "unconsciousness": ["unconscious", "passed out", "blacked out", "unresponsive"],
            "stroke symptoms": ["face drooping", "arm weakness", "speech difficulty", "slurred speech", "numbness one side"], # FAST test
            "sudden weakness": ["sudden weakness", "sudden paralysis"],
            "severe allergic reaction": ["swelling face", "difficulty swallowing", "hives widespread"],
            "seizure": ["seizure", "convulsions"]
        }
        logger.info("TriageAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input to determine the appropriate triage level and response.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = self.nlu_engine.process_text(text, context.get("language", "en"))
        
        if nlu_output.get("entities"):
            for entity in nlu_output["entities"]:
                if entity["type"] == "SYMPTOM" and entity["text"] not in self._memory["reported_symptoms"]:
                    self._memory["reported_symptoms"].append(entity["text"])
        
        # Check for red flags
        red_flags_found = False
        text_lower = text.lower()
        for flag_type, keywords in self.red_flags.items():
            if any(k in text_lower for k in keywords):
                self._memory["urgency_factors"][flag_type] = True
                logger.warning(f"Red flag detected: {flag_type} for text: '{text}'")
                red_flags_found = True
        
        # FIX: Scan all flags first, then escalate if any found
        if red_flags_found:
            if self.emergency_router:
                # FIX: Await the async escalation call
                await self.emergency_router.escalate_emergency_call(
                    context.get("call_id"), 
                    context.get("country_code", "US"), 
                    context.get("caller_location")
                )
            return {
                "response_text": self._get_emergency_response(context.get("country_code", "US")),
                "context_update": {"triage_level": TriageLevel.RED.name, "emergency_escalated": True},
                "action": "dial_emergency_services"
            }
        
        current_question_index = self._memory["current_question_index"]
        if current_question_index == 0:
            self._memory["question_history"].append(text)
            self._memory["current_question_index"] += 1
            return {
                "response_text": self.triage_questions[self._memory["current_question_index"]],
                "context_update": {"triage_state": "asking_details"},
                "action": "ask_question"
            }
        else:
            self._memory["question_history"].append(text)
            self._process_answer(text, nlu_output, current_question_index)
            
            if self._memory["current_question_index"] < len(self.triage_questions) -1 :
                self._memory["current_question_index"] += 1
                return {
                    "response_text": self.triage_questions[self._memory["current_question_index"]],
                    "context_update": {"triage_state": "asking_details"},
                    "action": "ask_question"
                }
            else:
                return self._make_triage_decision(context)

    def _process_answer(self, text: str, nlu_output: Dict[str, Any], question_index: int):
        """
        Processes the user's answer to a specific triage question.
        """
        logger.debug(f"Processing answer for question {question_index}: '{text}'")
        if question_index == 1: # When did it start? (Duration)
            for entity in nlu_output.get("entities", []):
                if entity["type"] == "DURATION":
                    self._memory["urgency_factors"]["duration"] = entity["text"]
                    break
        elif question_index == 2: # How severe is pain/discomfort?
            pain_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b', text, re.IGNORECASE)
            if pain_match:
                pain_val = pain_match.group(0).lower()
                num_map = {"one":1, "two":2, "three":3, "four":4, "five":5, "six":6, "seven":7, "eight":8, "nine":9, "ten":10}
                severity = num_map.get(pain_val, int(pain_val) if pain_val.isdigit() else 0)
                if 0 < severity <= 10:
                    self._memory["urgency_factors"]["severity"] = severity

    def _make_triage_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Makes the final triage decision based on all collected information.
        """
        severity = self._memory["urgency_factors"].get("severity", 0)
        reported_symptoms = " ".join(self._memory["reported_symptoms"]).lower()

        triage_level = TriageLevel.GREEN
        response_text = "Based on the information you've provided, your symptoms suggest a non-urgent concern. We recommend scheduling a routine appointment with your doctor."
        action = "suggest_routine_appointment"

        # Check for ORANGE level
        if severity >= 8 or ("severe" in reported_symptoms and "pain" in reported_symptoms):
            triage_level = TriageLevel.ORANGE
            response_text = "Your symptoms indicate an urgent concern that requires immediate medical attention. Please head to the nearest Emergency Room within the next 10 minutes."
            action = "suggest_er_visit"
        # Check for YELLOW level
        elif severity >= 5 or ("moderate" in reported_symptoms or "persistent" in reported_symptoms):
            if triage_level == TriageLevel.GREEN: 
                triage_level = TriageLevel.YELLOW
                response_text = "Your symptoms suggest an urgent but not life-threatening concern. We recommend seeing a doctor within the next hour, possibly at an urgent care clinic."
                action = "suggest_urgent_care"
        
        # Blue level for very minor, self-care
        elif severity < 3 and len(self._memory["reported_symptoms"]) == 1 and "mild" in reported_symptoms:
            triage_level = TriageLevel.BLUE
            response_text = "Your symptoms appear to be minor and can likely be managed with self-care at home. If symptoms worsen, please contact us again."
            action = "suggest_self_care"


        logger.info(f"Final Triage Decision for Call ID {context.get('call_id')}: {triage_level.name}")
        return {
            "response_text": response_text + " Please remember, I am an AI and cannot provide a diagnosis. Always consult a healthcare professional for medical advice.",
            "context_update": {"triage_level": triage_level.name, "triage_state": "completed"},
            "action": action
        }

    def _get_emergency_response(self, country_code: str) -> str:
        """Provides a location-specific emergency response."""
        emergency_number = "911"
        if country_code == "IN":
            emergency_number = "108"
        elif country_code == "GB":
            emergency_number = "999"
        
        return (f"This sounds like a medical emergency. I am immediately connecting you to emergency services. "
                f"Please stay on the line. The emergency number is {emergency_number}.")

    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["triage_state"] = "initial"
        self._memory["reported_symptoms"] = []
        self._memory["urgency_factors"] = {}
        self._memory["question_history"] = []
        self._memory["current_question_index"] = 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    class MockNLUEngine:
        def process_text(self, text, lang):
            entities = []
            if "fever" in text.lower(): entities.append({"type": "SYMPTOM", "text": "fever"})
            if "headache" in text.lower(): entities.append({"type": "SYMPTOM", "text": "headache"})
            if "3 days" in text.lower(): entities.append({"type": "DURATION", "text": "3 days"})
            if "pain" in text.lower(): entities.append({"type": "SYMPTOM", "text": "pain"})
            if "unbearable" in text.lower(): entities.append({"type": "SEVERITY_ADJ", "text": "unbearable"})
            return {"entities": entities, "intent": {"name": "symptom_inquiry"}}

    class MockEmergencyRouter:
        async def escalate_emergency_call(self, call_id, country_code, location):
            logger.info(f"MOCK: Escalating emergency call {call_id} to {country_code} at {location}. NEVER HANG UP!")

    nlu_mock = MockNLUEngine()
    emergency_mock = MockEmergencyRouter()
    
    triage_agent = TriageAgent(nlu_engine=nlu_mock, emergency_router=emergency_mock)

    async def run_triage_flow():
        context = {"call_id": "call_123", "user_id": "user_abc", "language": "en", "country_code": "US"}

        # Initial input - Red Flag
        print("\n--- Flow 1: Immediate Red Flag ---")
        response = await triage_agent.process_input("I have crushing chest pain radiating to my left arm! Call 911!", context)
        print(f"Agent Response: {response['response_text']}")
        assert response["context_update"]["triage_level"] == "RED"
        triage_agent.reset_memory()

        # Flow 2: Structured Triage - High Severity
        print("\n--- Flow 2: Structured Triage - High Severity ---")
        response1 = await triage_agent.process_input("I have a severe headache.", context)
        print(f"Agent: {response1['response_text']}") 
        
        response2 = await triage_agent.process_input("It started yesterday.", context)
        print(f"Agent: {response2['response_text']}") 
        
        response3 = await triage_agent.process_input("The pain is an 8 out of 10, unbearable.", context)
        print(f"Agent: {response3['response_text']}") 
        
        response4 = await triage_agent.process_input("No other major symptoms, just light sensitivity.", context)
        print(f"Agent: {response4['response_text']}") 
        
        response5 = await triage_agent.process_input("I took some ibuprofen a few hours ago.", context)
        print(f"Agent Response (Final): {response5['response_text']}")
        assert response5["context_update"]["triage_level"] == "ORANGE"
        triage_agent.reset_memory()

        # Flow 3: Structured Triage - Low Severity (Self-care)
        print("\n--- Flow 3: Structured Triage - Low Severity ---")
        response1_low = await triage_agent.process_input("I have a mild cough.", context)
        print(f"Agent: {response1_low['response_text']}")
        
        response2_low = await triage_agent.process_input("It started this morning.", context)
        print(f"Agent: {response2_low['response_text']}")
        
        response3_low = await triage_agent.process_input("The discomfort is about a 2.", context)
        print(f"Agent: {response3_low['response_text']}")
        
        response4_low = await triage_agent.process_input("No other symptoms.", context)
        print(f"Agent: {response4_low['response_text']}")
        
        response5_low = await triage_agent.process_input("No, I haven't taken anything yet.", context)
        print(f"Agent Response (Final): {response5_low['response_text']}")
        assert response5_low["context_update"]["triage_level"] == "BLUE"
        triage_agent.reset_memory()

    import asyncio
    asyncio.run(run_triage_flow())