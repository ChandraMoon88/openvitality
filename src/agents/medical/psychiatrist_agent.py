import logging
import re
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class PsychiatristAgent(BaseAgent):
    """
    A specialized AI agent for mental health support.
    Focuses on screening, crisis detection, offering coping techniques,
    and connecting users to appropriate resources.
    """
    def __init__(self, nlu_engine: Any = None, sentiment_analyzer: Any = None, suicide_hotline_bridge: Any = None):
        super().__init__(
            name="PsychiatristAgent",
            description="Provides mental health support and resources.",
            persona={
                "role": "compassionate and non-judgmental mental health assistant",
                "directives": [
                    "Prioritize user safety, especially in crisis situations.",
                    "Emphasize confidentiality and create a safe space.",
                    "Use non-judgmental and validating language.",
                    "Offer screening tools (PHQ-9, GAD-7) to assess mood/anxiety.",
                    "Provide basic coping strategies (e.g., breathing exercises).",
                    "Connect users to crisis hotlines and professional help when appropriate.",
                    "Never diagnose or provide therapy; offer support and resources only."
                ],
                "style": "calm, empathetic, supportive, confidential"
            }
        )
        self.nlu_engine = nlu_engine
        self.sentiment_analyzer = sentiment_analyzer
        self.suicide_hotline_bridge = suicide_hotline_bridge
        
        self._memory["mental_health_state"] = {
            "depression_score": None,
            "anxiety_score": None,
            "suicidal_ideation_detected": False,
            "current_feelings": [],
            "coping_strategies_discussed": []
        }
        self._memory["conversation_stage"] = "greeting" # greeting, screening, coping, crisis, resources
        self._memory["screening_questions_index"] = 0
        self.phq9_questions = [
            "Over the last two weeks, how often have you been bothered by: Little interest or pleasure in doing things?",
            "Feeling down, depressed, or hopeless?",
            "Trouble falling or staying asleep, or sleeping too much?",
            "Feeling tired or having little energy?",
            "Poor appetite or overeating?",
            "Feeling bad about yourself—or that you are a failure or have let yourself or your family down?",
            "Trouble concentrating on things, such as reading the newspaper or watching television?",
            "Moving or speaking so slowly that other people could have noticed? Or the opposite—being so fidgety or restless that you have been moving a lot more than usual?",
            "Thoughts that you would be better off dead or of hurting yourself in some way?"
        ]
        self.gad7_questions = [
            "Over the last two weeks, how often have you been bothered by: Feeling nervous, anxious, or on edge?",
            "Not being able to stop or control worrying?",
            "Worrying too much about different things?",
            "Trouble relaxing?",
            "Being so restless that it's hard to sit still?",
            "Becoming easily annoyed or irritable?",
            "Feeling afraid as if something awful might happen?"
        ]
        self.crisis_keywords = re.compile(r'\b(suicide|kill myself|end it all|die|no reason to live|goodbye forever|can\'t go on)\b', re.IGNORECASE)
        self.self_harm_keywords = re.compile(r'\b(cut myself|hurt myself|self-harm|punish myself)\b', re.IGNORECASE)
        
        logger.info("PsychiatristAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input for mental health support.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        sentiment_output = {}
        if self.nlu_engine:
            nlu_output = self.nlu_engine.process_text(text, context.get("language", "en"))
        if self.sentiment_analyzer:
            sentiment_output = self.sentiment_analyzer.analyze_sentiment(text, context.get("language", "en"))

        # Immediate crisis detection
        if await self._check_for_crisis(text, context):
            return {
                "response_text": self._get_crisis_response(context.get("country_code", "US")),
                "context_update": {"mental_health_crisis_detected": True},
                "action": "escalate_to_suicide_hotline"
            }
        
        # Update current feelings based on sentiment
        if sentiment_output.get("label") and sentiment_output["label"] != "neutral" and sentiment_output["label"] not in self._memory["mental_health_state"]["current_feelings"]:
            self._memory["mental_health_state"]["current_feelings"].append(sentiment_output["label"])

        # Handle conversation flow
        if self._memory["conversation_stage"] == "greeting":
            self._memory["conversation_stage"] = "initial_check"
            return {
                "response_text": "Hello, thank you for reaching out. This is a confidential conversation, and I'm here to listen. How are you feeling today?",
                "context_update": {"mh_stage": "initial_check"},
                "action": "listen"
            }
        
        elif self._memory["conversation_stage"] == "initial_check":
            if "depressed" in text.lower() or "anxious" in text.lower() or sentiment_output.get("emotional_indicators", {}).get("depression"):
                self._memory["conversation_stage"] = "screening"
                return self._start_screening("PHQ-9")
            else:
                return {
                    "response_text": "I hear you. If you're feeling overwhelmed, we can explore some coping strategies, or I can connect you to resources.",
                    "context_update": {"mh_stage": "offer_coping"},
                    "action": "offer_help"
                }

        elif self._memory["conversation_stage"] == "screening":
            return self._continue_screening(text)
        
        elif self._memory["conversation_stage"] == "coping":
            return self._offer_coping_strategies(text)
        
        elif self._memory["conversation_stage"] == "resources":
            return self._provide_resources(text)

        return {"response_text": "I'm still learning how to best support you. Would you like to try a breathing exercise, or would you like to know about crisis hotlines?", "context_update": {}, "action": "clarify_mh"}

    async def _check_for_crisis(self, text: str, context: Dict[str, Any]) -> bool:
        """
        Detects suicidal ideation or self-harm indications.
        """
        text_lower = text.lower()
        if self.crisis_keywords.search(text_lower) or self.self_harm_keywords.search(text_lower):
            self._memory["mental_health_state"]["suicidal_ideation_detected"] = True
            logger.critical(f"CRISIS ALERT: Suicidal ideation or self-harm keywords detected: '{text}'")
            if self.suicide_hotline_bridge:
                await self.suicide_hotline_bridge.escalate_to_hotline(context.get("call_id"), context.get("country_code", "US"), text)
            return True
        return False
    
    def _get_crisis_response(self, country_code: str) -> str:
        """Provides a crisis response, immediately transferring to a hotline."""
        hotline_number = "988" # US Suicide & Crisis Lifeline
        if country_code == "IN":
            hotline_number = "9152987821" # AASRA
        elif country_code == "GB":
            hotline_number = "116123" # Samaritans
        
        return (f"I hear you, and it sounds like you're going through a lot. Your safety is my top priority. "
                f"I am immediately connecting you to a crisis hotline where a trained professional can provide direct support. "
                f"Please stay on the line. The hotline number is {hotline_number}.")

    def _start_screening(self, screening_type: str) -> Dict[str, Any]:
        """Initiates a mental health screening (PHQ-9 or GAD-7)."""
        self._memory["mental_health_state"]["screening_type"] = screening_type
        self._memory["mental_health_state"]["screening_answers"] = []
        self._memory["screening_questions_index"] = 0
        
        questions = self.phq9_questions if screening_type == "PHQ-9" else self.gad7_questions
        return {
            "response_text": f"I can ask you a few questions from a common {screening_type} screening tool. Please answer with 'not at all', 'several days', 'more than half the days', or 'nearly every day'. Here is the first question: {questions[0]}",
            "context_update": {"mh_stage": "screening", "screening_type": screening_type},
            "action": "ask_screening_question"
        }

    def _continue_screening(self, text: str) -> Dict[str, Any]:
        """Continues with screening questions, processes answers."""
        screening_type = self._memory["mental_health_state"]["screening_type"]
        questions = self.phq9_questions if screening_type == "PHQ-9" else self.gad7_questions
        
        # Process the answer to the previous question
        answer_score = self._parse_screening_answer(text)
        self._memory["mental_health_state"]["screening_answers"].append(answer_score)
        
        self._memory["screening_questions_index"] += 1
        if self._memory["screening_questions_index"] < len(questions):
            return {
                "response_text": questions[self._memory["screening_questions_index"]],
                "context_update": {"mh_stage": "screening", "screening_type": screening_type},
                "action": "ask_screening_question"
            }
        else:
            # Screening complete, calculate score and provide outcome
            total_score = sum(self._memory["mental_health_state"]["screening_answers"])
            if screening_type == "PHQ-9":
                self._memory["mental_health_state"]["depression_score"] = total_score
                return self._provide_phq9_outcome(total_score)
            else: # GAD-7
                self._memory["mental_health_state"]["anxiety_score"] = total_score
                return self._provide_gad7_outcome(total_score)

    def _parse_screening_answer(self, text: str) -> int:
        """Converts text answer to a numerical score for screening questions."""
        text_lower = text.lower()
        if "not at all" in text_lower: return 0
        if "several days" in text_lower: return 1
        if "more than half" in text_lower: return 2
        if "nearly every day" in text_lower: return 3
        return 0 # Default to 0 if unsure

    def _provide_phq9_outcome(self, score: int) -> Dict[str, Any]:
        """Provides outcome based on PHQ-9 score."""
        if score >= 20: level = "Severe Depression"; recommendation = "It appears you may be experiencing symptoms of severe depression. It is very important to seek immediate professional help. I can connect you with resources."
        elif score >= 15: level = "Moderately Severe Depression"; recommendation = "Your responses suggest moderately severe depression. I highly recommend connecting with a mental health professional soon."
        elif score >= 10: level = "Moderate Depression"; recommendation = "Your responses indicate moderate depression. Speaking with a therapist or doctor could be very beneficial."
        elif score >= 5: level = "Mild Depression"; recommendation = "You may be experiencing mild depression. Exploring coping strategies or talking to someone might help."
        else: level = "Minimal Depression"; recommendation = "Your responses suggest minimal depressive symptoms. Continue to monitor how you feel."
        
        # FIX: Reset conversation stage to exit screening loop
        self._memory["conversation_stage"] = "initial_check"

        return {
            "response_text": f"Based on your answers, your PHQ-9 score is {score}, indicating {level}. {recommendation}",
            "context_update": {"mh_stage": "screening_complete", "depression_level": level},
            "action": "offer_resources"
        }

    def _provide_gad7_outcome(self, score: int) -> Dict[str, Any]:
        """Provides outcome based on GAD-7 score."""
        if score >= 15: level = "Severe Anxiety"; recommendation = "It appears you may be experiencing symptoms of severe anxiety. Please seek immediate professional help. I can connect you with resources."
        elif score >= 10: level = "Moderate Anxiety"; recommendation = "Your responses suggest moderate anxiety. Connecting with a mental health professional could be very beneficial."
        elif score >= 5: level = "Mild Anxiety"; recommendation = "You may be experiencing mild anxiety. Exploring coping strategies or talking to someone might help."
        else: level = "Minimal Anxiety"; recommendation = "Your responses suggest minimal anxiety symptoms. Continue to monitor how you feel."
        
        # FIX: Reset conversation stage to exit screening loop
        self._memory["conversation_stage"] = "initial_check"

        return {
            "response_text": f"Based on your answers, your GAD-7 score is {score}, indicating {level}. {recommendation}",
            "context_update": {"mh_stage": "screening_complete", "anxiety_level": level},
            "action": "offer_resources"
        }

    def _offer_coping_strategies(self, text: str) -> Dict[str, Any]:
        """Offers basic CBT-inspired coping strategies."""
        self._memory["conversation_stage"] = "coping"
        if "breath" in text.lower():
            response = "Let's try a simple breathing exercise. Breathe in slowly through your nose for 4 counts, hold for 7 counts, and exhale slowly through your mouth for 8 counts. Repeat this a few times. How do you feel after that?"
            self._memory["mental_health_state"]["coping_strategies_discussed"].append("breathing exercise")
        elif "reframing" in text.lower() or "thoughts" in text.lower():
            response = "Sometimes our thoughts can feel overwhelming. A technique called 'thought reframing' can help. When you have a negative thought, try to identify it and then gently challenge it. Is there another way to look at this situation? How would you advise a friend in this situation?"
            self._memory["mental_health_state"]["coping_strategies_discussed"].append("thought reframing")
        else:
            response = "We can try a breathing exercise, or explore thought reframing techniques. Which would you prefer? Or I can provide information about professional help."
        
        return {
            "response_text": response,
            "context_update": {"mh_stage": "coping"},
            "action": "offer_coping_strategy"
        }

    def _provide_resources(self, text: str) -> Dict[str, Any]:
        """Connects users to crisis hotlines or other mental health resources."""
        self._memory["conversation_stage"] = "resources"
        response_text = "If you are in immediate danger, please call emergency services. For ongoing support, I recommend reaching out to a mental health professional. You can find local resources through organizations like NAMI or by searching online for licensed therapists in your area. For crisis situations, here are some hotline numbers: (example: US: 988, UK: 116 123)."
        return {
            "response_text": response_text,
            "context_update": {"mh_stage": "resources_provided"},
            "action": "provide_resources"
        }

    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["mental_health_state"] = {
            "depression_score": None,
            "anxiety_score": None,
            "suicidal_ideation_detected": False,
            "current_feelings": [],
            "coping_strategies_discussed": []
        }
        self._memory["conversation_stage"] = "greeting"
        self._memory["screening_questions_index"] = 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    class MockNLUEngine:
        def process_text(self, text, lang):
            return {"intent": {"name": "mental_health_support"}}

    class MockSentimentAnalyzer:
        def analyze_sentiment(self, text, lang):
            if "hopeless" in text.lower() or "end it all" in text.lower():
                return {"label": "negative", "score": -0.9, "emotional_indicators": {"depression": True, "panic": False, "anger": False, "high_pain_intensity": False}}
            elif "anxious" in text.lower() or "nervous" in text.lower():
                return {"label": "negative", "score": -0.7, "emotional_indicators": {"depression": False, "panic": False, "anger": False, "high_pain_intensity": False}}
            return {"label": "neutral", "score": 0.1, "emotional_indicators": {"depression": False, "panic": False, "anger": False, "high_pain_intensity": False}}

    class MockSuicideHotlineBridge:
        async def escalate_to_hotline(self, call_id, country_code, text):
            logger.critical(f"MOCK: Escalating suicide ideation for call {call_id} to hotline in {country_code} due to text: '{text}'. DO NOT DISCONNECT!")

    nlu_mock = MockNLUEngine()
    sentiment_mock = MockSentimentAnalyzer()
    suicide_hotline_mock = MockSuicideHotlineBridge()
    
    psych_agent = PsychiatristAgent(nlu_engine=nlu_mock, sentiment_analyzer=sentiment_mock, suicide_hotline_bridge=suicide_hotline_mock)

    async def run_psych_flow():
        context = {"call_id": "mh_call_001", "user_id": "user_mh", "language": "en", "country_code": "US"}

        # Flow 1: Crisis Detection
        print("\n--- Flow 1: Crisis Detection (Suicidal Ideation) ---")
        response = await psych_agent.process_input("I feel so hopeless, I want to end it all.", context)
        print(f"Agent Response: {response['response_text']}")
        assert "escalate_to_suicide_hotline" in response["action"]
        psych_agent.reset_memory()

        # Flow 2: PHQ-9 Screening
        print("\n--- Flow 2: PHQ-9 Screening ---")
        response1 = await psych_agent.process_input("Hello, I've been feeling depressed lately.", context)
        print(f"Agent: {response1['response_text']}") 
        
        response2 = await psych_agent.process_input("Nearly every day.", context) # PHQ-9 Q1
        print(f"Agent: {response2['response_text']}")
        response3 = await psych_agent.process_input("More than half the days.", context) # PHQ-9 Q2
        print(f"Agent: {response3['response_text']}")
        response4 = await psych_agent.process_input("Several days.", context) # PHQ-9 Q3
        print(f"Agent: {response4['response_text']}")
        response5 = await psych_agent.process_input("Not at all.", context) # PHQ-9 Q4
        print(f"Agent: {response5['response_text']}")
        response6 = await psych_agent.process_input("Several days.", context) # PHQ-9 Q5
        print(f"Agent: {response6['response_text']}")
        response7 = await psych_agent.process_input("More than half the days.", context) # PHQ-9 Q6
        print(f"Agent: {response7['response_text']}")
        response8 = await psych_agent.process_input("Nearly every day.", context) # PHQ-9 Q7
        print(f"Agent: {response8['response_text']}")
        response9 = await psych_agent.process_input("Not at all.", context) # PHQ-9 Q8
        print(f"Agent: {response9['response_text']}")
        response10 = await psych_agent.process_input("Not at all.", context) # PHQ-9 Q9
        print(f"Agent (Outcome): {response10['response_text']}")
        assert "Moderate Depression" in response10["response_text"] 
        psych_agent.reset_memory()

        # Flow 3: Coping Strategies
        print("\n--- Flow 3: Coping Strategies (Breathing) ---")
        response_coping1 = await psych_agent.process_input("I'm feeling very anxious, can you help me relax?", context)
        print(f"Agent: {response_coping1['response_text']}")
        assert "breathing exercise" in response_coping1["response_text"]

        response_coping2 = await psych_agent.process_input("I feel a little better after that.", context)
        print(f"Agent: {response_coping2['response_text']}") 
        assert "try a breathing exercise, or explore thought reframing" in response_coping2["response_text"]


        psych_agent.reset_memory()
        print(f"\nPsychiatrist Agent memory after reset: {psych_agent.current_memory}")

    import asyncio
    asyncio.run(run_psych_flow())