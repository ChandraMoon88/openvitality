import logging
import re
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class CardiologistAgent(BaseAgent):
    """
    A specialized AI agent for heart health, focusing on risk assessment,
    hypertension management, lifestyle coaching, and cardiac emergency detection.
    """
    def __init__(self, nlu_engine: Any = None, emergency_router: Any = None):
        super().__init__(
            name="CardiologistAgent",
            description="Specializes in heart health, risk assessment, and management.",
            persona={
                "role": "knowledgeable and cautious cardiologist assistant",
                "directives": [
                    "Collect relevant cardiac risk factors (age, BP, cholesterol, etc.).",
                    "Provide evidence-based information on heart health, hypertension, and diet.",
                    "Strongly emphasize that this is not a diagnosis and to consult a doctor.",
                    "Immediately escalate any suspected cardiac emergency.",
                    "Encourage adherence to medication and healthy lifestyle choices."
                ],
                "style": "authoritative, reassuring, precise"
            }
        )
        self.nlu_engine = nlu_engine
        self.emergency_router = emergency_router
        
        self._memory["cardiac_history"] = {
            "age": None,
            "gender": None,
            "blood_pressure": None, # Stored as "systolic/diastolic"
            "cholesterol": {"total": None, "hdl": None, "ldl": None},
            "smoking_status": None, # "current", "former", "never"
            "diabetes": None, # True/False
            "family_history_heart_disease": False,
            "reported_symptoms": []
        }
        self._memory["conversation_stage"] = "greeting" # greeting, risk_assessment, coaching, emergency_check
        self._memory["current_question_index"] = 0

        self.risk_assessment_questions = [
            "To help me understand your heart health, could you tell me your age and gender?",
            "What is your typical blood pressure reading, if you know it?",
            "Do you know your cholesterol levels (total, HDL, LDL)?",
            "What is your smoking status: current, former, or have you never smoked?",
            "Have you been diagnosed with diabetes?",
            "Is there a family history of heart disease, such as heart attacks or strokes, before age 55 in males or 65 in females?"
        ]

        self.cardiac_red_flags = {
            "crushing chest pain": ["crushing chest pain", "severe chest pain", "pressure in chest", "squeezing in chest"],
            "radiating pain": ["pain radiating to left arm", "pain in jaw", "pain in back"],
            "shortness of breath": ["shortness of breath", "difficulty breathing", "gasping for air"],
            "sudden weakness": ["sudden weakness", "numbness on one side", "dizziness", "fainting"],
            "palpitations with symptoms": ["heart racing", "skipped beats", "fluttering", "palpitations with dizziness or chest pain"]
        }
        logger.info("CardiologistAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input related to heart health.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = await self.nlu_engine.process_text(text, context.get("language", "en"))
        
        # Always check for immediate cardiac red flags first
        # FIX: Added await here
        if await self._check_cardiac_red_flags(text, context):
            return {
                "response_text": self._get_emergency_response(context.get("country_code", "US")),
                "context_update": {"cardiac_emergency_detected": True},
                "action": "dial_emergency_services"
            }

        # Handle conversation flow
        if self._memory["conversation_stage"] == "greeting":
            self._memory["conversation_stage"] = "risk_assessment"
            self._memory["current_question_index"] = 0
            return self._ask_next_question()
        
        elif self._memory["conversation_stage"] == "risk_assessment":
            await self._process_risk_assessment_answer(text, nlu_output, self._memory["current_question_index"] - 1)
            
            if self._memory["current_question_index"] < len(self.risk_assessment_questions):
                return self._ask_next_question()
            else:
                self._memory["conversation_stage"] = "coaching"
                return await self._provide_cardiac_guidance(context)

        elif self._memory["conversation_stage"] == "coaching":
            return await self._handle_coaching_follow_ups(text, context, nlu_output)
        
        return {"response_text": "I'm not sure how to respond to that heart-related query.", "context_update": {}, "action": "clarify_cardiac"}

    # FIX: Changed to async to support awaiting emergency_router
    async def _check_cardiac_red_flags(self, text: str, context: Dict[str, Any]) -> bool:
        """
        Checks for keywords indicating a potential cardiac emergency.
        """
        text_lower = text.lower()
        symptoms_detected_text = [] 
        for flag_type, keywords in self.cardiac_red_flags.items():
            for k in keywords: 
                if k in text_lower:
                    symptoms_detected_text.append(k) 
                    break 
        
        if symptoms_detected_text:
            self._memory["cardiac_history"]["reported_symptoms"].extend(symptoms_detected_text)
            logger.critical(f"Cardiac red flags detected: {', '.join(symptoms_detected_text)}")
            if self.emergency_router:
                # FIX: Await the async router call
                await self.emergency_router.escalate_emergency_call(
                    context.get("call_id"), 
                    context.get("country_code", "US"), 
                    context.get("caller_location")
                )
            return True
        return False

    def _get_emergency_response(self, country_code: str) -> str:
        """Provides a location-specific emergency response."""
        emergency_number = "911"
        if country_code == "IN":
            emergency_number = "108"
        elif country_code == "GB":
            emergency_number = "999"
        
        return (
                f"This sounds like a severe cardiac emergency. I am immediately connecting you to emergency services. "
                f"Please stay calm and stay on the line. The emergency number is {emergency_number}.")

    def _ask_next_question(self) -> Dict[str, Any]:
        """Returns the next question in the risk assessment flow."""
        question_text = self.risk_assessment_questions[self._memory["current_question_index"]]
        self._memory["current_question_index"] += 1
        return {
            "response_text": question_text,
            "context_update": {"cardiac_stage": "risk_assessment", "question_asked": question_text},
            "action": "ask_question"
        }

    async def _process_risk_assessment_answer(self, text: str, nlu_output: Dict[str, Any], question_index: int):
        """
        Processes answers to risk assessment questions.
        """
        logger.debug(f"Processing answer to risk assessment question {question_index}: '{text}'")
        text_lower = text.lower()
        entities = nlu_output.get("entities", [])

        if question_index == 0: # Age and Gender
            age_match = re.search(r'(\d+)\s*(year|yr)?', text_lower)
            if age_match: self._memory["cardiac_history"]["age"] = int(age_match.group(1))
            if "male" in text_lower or "man" in text_lower: self._memory["cardiac_history"]["gender"] = "male"
            if "female" in text_lower or "woman" in text_lower: self._memory["cardiac_history"]["gender"] = "female"
        elif question_index == 1: # Blood Pressure
            bp_match = re.search(r'(\d+)\s*/\s*(\d+)', text_lower)
            if bp_match: self._memory["cardiac_history"]["blood_pressure"] = f"{bp_match.group(1)}/{bp_match.group(2)}"
        elif question_index == 2: # Cholesterol
            for entity in entities:
                if entity["type"] == "CHOLESTEROL_LEVEL": # Hypothetical entity type
                    # Logic to parse total, HDL, LDL
                    pass
        elif question_index == 3: # Smoking Status
            if "current" in text_lower: self._memory["cardiac_history"]["smoking_status"] = "current"
            elif "former" in text_lower or "quit" in text_lower: self._memory["cardiac_history"]["smoking_status"] = "former"
            elif "never" in text_lower: self._memory["cardiac_history"]["smoking_status"] = "never"
        elif question_index == 4: # Diabetes
            if "yes" in text_lower or "diagnosed with diabetes" in text_lower: self._memory["cardiac_history"]["diabetes"] = True
            elif "no" in text_lower: self._memory["cardiac_history"]["diabetes"] = False
        elif question_index == 5: # Family History
            if "yes" in text_lower or "family history" in text_lower: self._memory["cardiac_history"]["family_history_heart_disease"] = True
            elif "no" in text_lower: self._memory["cardiac_history"]["family_history_heart_disease"] = False

    async def _provide_cardiac_guidance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provides guidance based on collected cardiac risk factors.
        """
        history = self._memory["cardiac_history"]
        response_parts = ["Thank you for providing that information."]
        
        # Hypertension Management
        if history["blood_pressure"] and (int(history["blood_pressure"].split('/')[0]) >= 140 or int(history["blood_pressure"].split('/')[1]) >= 90):
            response_parts.append("Your blood pressure readings suggest hypertension. It's crucial to manage this to reduce heart disease risk. Consistent medication adherence and lifestyle changes are often recommended.")
        elif history["blood_pressure"]:
            response_parts.append("Your blood pressure appears to be within a healthy range. Maintaining a healthy lifestyle is key to keeping it that way.")

        # Lifestyle Coaching (DASH diet, exercise)
        response_parts.append("For heart health, a balanced diet like the DASH eating plan, regular physical activity (e.g., 30 minutes of moderate exercise most days), and maintaining a healthy weight are highly beneficial. If you smoke, quitting is the single best thing you can do for your heart.")

        final_response = " ".join(response_parts)
        final_response += " Remember, I am an AI and cannot provide a diagnosis or substitute for professional medical advice. Please consult your cardiologist or GP for a personalized assessment and management plan. (Source: American Heart Association, WHO Guidelines)"

        return {
            "response_text": final_response,
            "context_update": {"cardiac_stage": "coaching_complete"},
            "action": "provide_guidance"
        }

    async def _handle_coaching_follow_ups(self, text: str, context: Dict[str, Any], nlu_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles follow-up questions during the coaching phase.
        """
        logger.debug(f"Cardiologist Agent handling follow-up: '{text}'")
        # Example: if user asks about a specific diet or exercise
        if "diet" in text.lower() or "food" in text.lower():
            response_text = "The DASH diet, or Dietary Approaches to Stop Hypertension, emphasizes fruits, vegetables, whole grains, and lean protein, while limiting saturated fat, cholesterol, and sodium. This can be very helpful for heart health. (Source: National Heart, Lung, and Blood Institute)"
        elif "exercise" in text.lower() or "activity" in text.lower():
            response_text = "Aim for at least 150 minutes of moderate-intensity aerobic activity or 75 minutes of vigorous-intensity aerobic activity per week, along with muscle-strengthening activities on 2 or more days a week. Consult your doctor before starting any new exercise regimen. (Source: American Heart Association)"
        else:
            response_text = "I can provide general information on heart health, but for specific medical advice, please consult your doctor. (Source: AI Assistant)"

        return {
            "response_text": response_text,
            "context_update": {"cardiac_stage": "coaching"},
            "action": "answer_question"
        }

    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["cardiac_history"] = {
            "age": None, "gender": None, "blood_pressure": None,
            "cholesterol": {"total": None, "hdl": None, "ldl": None},
            "smoking_status": None, "diabetes": None,
            "family_history_heart_disease": False,
            "reported_symptoms": []
        }
        self._memory["conversation_stage"] = "greeting"
        self._memory["current_question_index"] = 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock NLU Engine and Emergency Router for testing
    class MockNLUEngine:
        async def process_text(self, text, lang):
            entities = []
            if "headache" in text.lower(): entities.append({"type": "SYMPTOM", "text": "headache"})
            if "chest pain" in text.lower(): entities.append({"type": "SYMPTOM", "text": "chest pain"})
            if "140/90" in text.lower(): entities.append({"type": "BLOOD_PRESSURE", "text": "140/90"})
            if "diabetes" in text.lower(): entities.append({"type": "DISEASE", "text": "diabetes"})
            return {"entities": entities, "intent": {"name": "general_health_info"}}

    class MockEmergencyRouter:
        async def escalate_emergency_call(self, call_id, country_code, location):
            logger.info(f"MOCK: Escalating emergency cardiac call {call_id} to {country_code} at {location}. NEVER HANG UP!")

    nlu_mock = MockNLUEngine()
    emergency_mock = MockEmergencyRouter()
    
    cardio_agent = CardiologistAgent(nlu_engine=nlu_mock, emergency_router=emergency_mock)

    async def run_cardio_flow():
        context = {"call_id": "cardio_call_789", "user_id": "user_ijk", "language": "en", "country_code": "US"}

        # Flow 1: Immediate Cardiac Red Flag
        print("\n--- Flow 1: Immediate Cardiac Red Flag ---")
        response = await cardio_agent.process_input("I have crushing chest pain and feel dizzy!", context)
        print(f"Agent Response: {response['response_text']}")
        assert "dial_emergency_services" in response["action"]
        cardio_agent.reset_memory()

        # Flow 2: Risk Assessment and Coaching
        print("\n--- Flow 2: Risk Assessment and Coaching ---")
        response1 = await cardio_agent.process_input("Hello, I want to discuss my heart health.", context)
        print(f"Agent: {response1['response_text']}")
        
        response2 = await cardio_agent.process_input("I am 55 years old and male.", context)
        print(f"Agent: {response2['response_text']}")
        
        response3 = await cardio_agent.process_input("My blood pressure is usually around 145/95.", context)
        print(f"Agent: {response3['response_text']}")
        
        response4 = await cardio_agent.process_input("I don't know my exact cholesterol, but I have high cholesterol.", context)
        print(f"Agent: {response4['response_text']}")
        
        response5 = await cardio_agent.process_input("I am a former smoker.", context)
        print(f"Agent: {response5['response_text']}")

        response6 = await cardio_agent.process_input("Yes, I have diabetes.", context)
        print(f"Agent: {response6['response_text']}")

        response7 = await cardio_agent.process_input("No, no family history of early heart disease.", context)
        print(f"Agent (Guidance): {response7['response_text']}")
        assert "hypertension" in response7["response_text"].lower()

        print("\n--- Flow 2: Follow-up Question on Diet ---")
        response_followup = await cardio_agent.process_input("Tell me more about the DASH diet.", context)
        print(f"Agent (Follow-up): {response_followup['response_text']}")
        assert "DASH eating plan" in response_followup["response_text"]

        cardio_agent.reset_memory()
        print(f"\nCardio Agent memory after reset: {cardio_agent.current_memory}")

    import asyncio
    asyncio.run(run_cardio_flow())