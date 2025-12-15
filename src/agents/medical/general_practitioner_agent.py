import logging
import re
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class GeneralPractitionerAgent(BaseAgent):
    """
    A General Practitioner (GP) Agent for handling common medical issues.
    It takes patient history, suggests possible conditions, provides advice,
    and recommends further action.
    """
    def __init__(self, nlu_engine: Any = None, rag_orchestrator: Any = None):
        super().__init__(
            name="GeneralPractitionerAgent",
            description="Provides advice for common medical issues.",
            persona={
                "role": "compassionate general practitioner assistant",
                "directives": [
                    "Gather comprehensive patient history (symptoms, duration, severity, risk factors).",
                    "Suggest common conditions based on symptoms, but never provide a definitive diagnosis.",
                    "Offer evidence-based self-care advice or over-the-counter (OTC) medication suggestions.",
                    "Recommend seeing a human doctor for further assessment or if red flags are present.",
                    "Always cite medical sources for information provided.",
                    "Use simple, understandable language (8th-grade reading level)."
                ],
                "style": "supportive, informative, cautious"
            }
        )
        self.nlu_engine = nlu_engine
        self.rag_orchestrator = rag_orchestrator
        
        self._memory["patient_history"] = {
            "symptoms": [],
            "duration": None,
            "severity": None,
            "risk_factors": {"age": None, "pregnancy": False, "chronic_conditions": []},
            "medication_taken": []
        }
        self._memory["conversation_stage"] = "greeting" # greeting, history_taking, advising
        self._memory["current_question_index"] = 0
        self.history_questions = [
            "Could you please describe your main symptoms?",
            "When did these symptoms start?",
            "On a scale of 1 to 10, how severe would you rate your discomfort?",
            "Do you have any underlying health conditions, or are you taking any regular medications?",
            "Are you pregnant or of child-bearing age (if applicable)?",
            "Have you tried any remedies or medications for your symptoms already?"
        ]
        logger.info("GeneralPractitionerAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input, collects history, and provides GP-like advice.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = await self.nlu_engine.process_text(text, context.get("language", "en"))
        
        # Advance conversation stage
        if self._memory["conversation_stage"] == "greeting":
            self._memory["conversation_stage"] = "history_taking"
            self._memory["current_question_index"] = 0
            return self._ask_next_question()
        
        elif self._memory["conversation_stage"] == "history_taking":
            self._process_answer(text, nlu_output, self._memory["current_question_index"] - 1)
            
            if self._memory["current_question_index"] < len(self.history_questions):
                return self._ask_next_question()
            else:
                # All history collected, proceed to provide advice
                self._memory["conversation_stage"] = "advising"
                return await self._provide_advice(context)

        elif self._memory["conversation_stage"] == "advising":
            # If user asks follow-up questions during advising phase
            return await self._handle_follow_up_questions(text, context, nlu_output)
        
        return {"response_text": "I'm not sure how to respond to that.", "context_update": {}, "action": "clarify"}


    def _ask_next_question(self) -> Dict[str, Any]:
        """Returns the next question in the history-taking flow."""
        question_text = self.history_questions[self._memory["current_question_index"]]
        self._memory["current_question_index"] += 1
        return {
            "response_text": question_text,
            "context_update": {"gp_stage": "history_taking", "question_asked": question_text},
            "action": "ask_question"
        }

    def _process_answer(self, text: str, nlu_output: Dict[str, Any], question_index: int):
        """
        Processes the user's answer to a history-taking question.
        """
        logger.debug(f"GP Agent processing answer to question {question_index}: '{text}'")
        
        entities = nlu_output.get("entities", [])
        
        if question_index == 0: # Main symptoms
            for entity in entities:
                if entity["type"] == "SYMPTOM" and entity["text"] not in self._memory["patient_history"]["symptoms"]:
                    self._memory["patient_history"]["symptoms"].append(entity["text"])
        elif question_index == 1: # When did symptoms start?
            for entity in entities:
                if entity["type"] == "DURATION":
                    self._memory["patient_history"]["duration"] = entity["text"]
        elif question_index == 2: # Severity?
            pain_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b', text, re.IGNORECASE)
            if pain_match:
                pain_val = pain_match.group(0).lower()
                num_map = {"one":1, "two":2, "three":3, "four":4, "five":5, "six":6, "seven":7, "eight":8, "nine":9, "ten":10}
                severity = num_map.get(pain_val, int(pain_val) if pain_val.isdigit() else 0)
                if 0 < severity <= 10:
                    self._memory["patient_history"]["severity"] = severity
        elif question_index == 3: # Chronic conditions/medications
            for entity in entities:
                if entity["type"] == "DISEASE" and entity["text"] not in self._memory["patient_history"]["risk_factors"]["chronic_conditions"]:
                    self._memory["patient_history"]["risk_factors"]["chronic_conditions"].append(entity["text"])
                if entity["type"] == "CHEMICAL" and entity["text"] not in self._memory["patient_history"]["medication_taken"]:
                    self._memory["patient_history"]["medication_taken"].append(entity["text"])
        elif question_index == 4: # Pregnancy
            is_negative = re.search(r'\b(no|not|never)\b', text, re.IGNORECASE)
            if re.search(r'\b(yes|pregnant)\b', text, re.IGNORECASE) and not is_negative:
                self._memory["patient_history"]["risk_factors"]["pregnancy"] = True
            else:
                self._memory["patient_history"]["risk_factors"]["pregnancy"] = False
        elif question_index == 5: # Remedies
            if re.search(r'\b(ibuprofen|tylenol|paracetamol|home remedy)\b', text, re.IGNORECASE):
                self._memory["patient_history"]["medication_taken"].append(text) # Store as raw text for now


    async def _provide_advice(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesizes information to provide advice and recommendations.
        """
        history = self._memory["patient_history"]
        symptoms_str = ", ".join(history["symptoms"]).lower() if history["symptoms"] else "unspecified symptoms"
        severity = history["severity"] if history["severity"] else "moderate"
        duration = history["duration"] if history["duration"] else "some time"

        # Conceptual differential diagnosis (LLM + RAG)
        diagnosis_query = f"Patient reports {symptoms_str} for {duration} with severity {severity} out of 10. " \
                          f"Risk factors: {history['risk_factors']}. " \
                          f"Suggest possible common conditions and first-line advice."
        
        rag_response = {"text": "I can't provide a diagnosis, but common conditions with these symptoms include the common cold or flu. "}
        citation = "Source: WHO Guidelines on Common Illnesses."

        if self.rag_orchestrator:
            try:
                rag_result = await self.rag_orchestrator.query(diagnosis_query)
                rag_response["text"] = rag_result.get("answer", rag_response["text"])
                citation = rag_result.get("citation", citation)
            except Exception as e:
                logger.error(f"RAG Orchestrator failed: {e}")

        response_parts = [
            "Thank you for sharing your symptoms. Based on what you've told me:",
            rag_response["text"]
        ]

        # Determine advice based on severity and symptoms
        severity_val = int(severity) if isinstance(severity, int) else 5

        # FIX: Reordered checks so RED FLAGS take precedence over general severity
        if "chest pain" in symptoms_str or "difficulty breathing" in symptoms_str or "breathing" in symptoms_str:
             response_parts.append("These are red flag symptoms. Please seek immediate medical attention by calling emergency services or going to the nearest emergency room.")
             action = "recommend_emergency_care"
        elif severity_val >= 7:
            response_parts.append("Given the severity of your discomfort, I highly recommend you see a doctor as soon as possible for a proper examination.")
            action = "recommend_doctor_visit"
        elif "fever" in symptoms_str and (duration == "more than 3 days" or severity_val >= 5):
            response_parts.append("For fever, ensure you stay hydrated, get plenty of rest, and consider over-the-counter pain relievers like ibuprofen or paracetamol if you have no contraindications. If your fever persists or worsens, please consult a doctor.")
            action = "suggest_otc_meds"
        else:
            response_parts.append("For self-care, focus on rest, hydration, and avoiding irritants. If symptoms persist for more than a few days or worsen, it's best to consult a doctor.")
            action = "suggest_self_care"

        final_response = " ".join(response_parts) + f" (Source: {citation})"
        final_response += " Please remember, I am an AI and cannot provide a definitive diagnosis or replace a human doctor. Always consult a healthcare professional for medical advice."

        return {
            "response_text": final_response,
            "context_update": {"gp_stage": "advising_complete", "recommendation": action},
            "action": action
        }

    async def _handle_follow_up_questions(self, text: str, context: Dict[str, Any], nlu_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles follow-up questions after initial advice has been given.
        """
        logger.debug(f"GP Agent handling follow-up question: '{text}'")
        rag_query = f"User asks: '{text}'. Context of previous advice: {self._memory['patient_history']}. Answer concisely."
        
        rag_response = {"text": "I can try to answer that for you. "}
        citation = "Source: Medical Literature."

        if self.rag_orchestrator:
            try:
                rag_result = await self.rag_orchestrator.query(rag_query)
                rag_response["text"] = rag_result.get("answer", rag_response["text"])
                citation = rag_result.get("citation", citation)
            except Exception as e:
                logger.error(f"RAG Orchestrator failed for follow-up: {e}")

        response_text = rag_response["text"] + f" (Source: {citation})"
        response_text += " Remember, I am an AI and cannot provide a definitive diagnosis."

        return {
            "response_text": response_text,
            "context_update": {"gp_stage": "advising"}, # Stay in advising stage
            "action": "answer_question"
        }


    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["patient_history"] = {
            "symptoms": [],
            "duration": None,
            "severity": None,
            "risk_factors": {"age": None, "pregnancy": False, "chronic_conditions": []},
            "medication_taken": []
        }
        self._memory["conversation_stage"] = "greeting"
        self._memory["current_question_index"] = 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock NLU Engine and RAG Orchestrator for testing
    class MockNLUEngine:
        async def process_text(self, text, lang):
            entities = []
            if "headache" in text.lower(): entities.append({"type": "SYMPTOM", "text": "headache"})
            if "fever" in text.lower(): entities.append({"type": "SYMPTOM", "text": "fever"})
            if "3 days" in text.lower(): entities.append({"type": "DURATION", "text": "3 days"})
            if "ibuprofen" in text.lower(): entities.append({"type": "CHEMICAL", "text": "ibuprofen"})
            if "diabetes" in text.lower(): entities.append({"type": "DISEASE", "text": "diabetes"})
            if re.search(r'\bpregnant\b', text, re.IGNORECASE): entities.append({"type": "CONDITION", "text": "pregnant"})
            return {"entities": entities, "intent": {"name": "symptom_inquiry"}}

    class MockRAGOrchestrator:
        async def query(self, query_text: str) -> Dict[str, str]:
            if "fever" in query_text.lower() and "headache" in query_text.lower():
                return {
                    "answer": "Common causes include viral infections like the flu. Rest and hydration are key.",
                    "citation": "CDC: Influenza (Flu)"
                }
            elif "side effects of ibuprofen" in query_text.lower():
                return {
                    "answer": "Ibuprofen can cause stomach upset, dizziness, and headaches. Consult a doctor if severe.",
                    "citation": "NIH: Ibuprofen Information"
                }
            return {
                "answer": "I can only provide general medical information and not a diagnosis. Please consult a doctor.",
                "citation": "General Medical Advice"
            }

    nlu_mock = MockNLUEngine()
    rag_mock = MockRAGOrchestrator()
    
    gp_agent = GeneralPractitionerAgent(nlu_engine=nlu_mock, rag_orchestrator=rag_mock)

    async def run_gp_flow():
        context = {"call_id": "gp_call_456", "user_id": "user_xyz", "language": "en"}

        print("\n--- GP Flow: Initial Greeting & History Taking ---")
        response = await gp_agent.process_input("Hello, I need some medical advice.", context)
        print(f"Agent: {response['response_text']}")
        
        response = await gp_agent.process_input("I have a headache and a fever.", context)
        print(f"Agent: {response['response_text']}")
        
        response = await gp_agent.process_input("It started about 3 days ago.", context)
        print(f"Agent: {response['response_text']}")
        
        response = await gp_agent.process_input("My pain is about a 6 out of 10.", context)
        print(f"Agent: {response['response_text']}")

        response = await gp_agent.process_input("I have diabetes.", context)
        print(f"Agent: {response['response_text']}")

        response = await gp_agent.process_input("No, I am not pregnant.", context)
        print(f"Agent: {response['response_text']}")

        response = await gp_agent.process_input("I've taken some ibuprofen.", context)
        print(f"Agent (Advice): {response['response_text']}")
        assert "common cold or flu" in response["response_text"]
        assert "CDC: Influenza (Flu)" in response["response_text"]

        print("\n--- GP Flow: Follow-up Question ---")
        response_followup = await gp_agent.process_input("What are the side effects of ibuprofen?", context)
        print(f"Agent (Follow-up): {response_followup['response_text']}")
        assert "stomach upset" in response_followup["response_text"]

        gp_agent.reset_memory()
        print(f"\nGP Agent memory after reset: {gp_agent.current_memory}")

    import asyncio
    asyncio.run(run_gp_flow())