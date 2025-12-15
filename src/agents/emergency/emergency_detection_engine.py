import logging
import re
from typing import Dict, Any, List, Optional
import asyncio

logger = logging.getLogger(__name__)

class EmergencyDetectionEngine:
    """
    The central watchdog for life-threatening situations. It continuously monitors
    incoming user input (text, and conceptually audio) for critical indicators
    and triggers immediate escalation protocols if an emergency is detected.
    """
    def __init__(self, nlu_engine: Any = None, sentiment_analyzer: Any = None, emergency_router: Any = None, audio_analyzer: Any = None, vad_engine: Any = None):
        self.nlu_engine = nlu_engine
        self.sentiment_analyzer = sentiment_analyzer
        self.emergency_router = emergency_router
        self.audio_analyzer = audio_analyzer
        self.vad_engine = vad_engine
        
        # Extensive list of emergency trigger words and phrases
        self.trigger_patterns: Dict[str, List[re.Pattern]] = {
            "CARDAC": [
                # FIX: Added 'chest hurts' to the regex pattern
                re.compile(r'\b(chest pain|chest hurts|heart attack|crushing|pressure in chest|radiating pain|squeezing in chest|angina)\b', re.IGNORECASE),
                re.compile(r'\b(heart racing|palpitations|dizzy|fainting|sweating|nausea)\b', re.IGNORECASE)
            ],
            "RESPIRATORY": [
                re.compile(r'\b(can\'t breathe|difficulty breathing|shortness of breath|gasping|choking|wheezing|blue lips|struggling to breathe)\b', re.IGNORECASE)
            ],
            "NEURO": [
                re.compile(r'\b(stroke|facial droop|arm weakness|slurred speech|sudden confusion|worst headache of my life|numbness on one side)\b', re.IGNORECASE)
            ],
            "TRAUMA": [
                re.compile(r'\b(bleeding heavily|severe bleeding|stabbed|shot|accident|broken bone|head injury|unconscious)\b', re.IGNORECASE)
            ],
            "MENTAL_HEALTH_CRISIS": [
                re.compile(r'\b(kill myself|end it all|suicide|no reason to live|goodbye forever|can\'t go on|self-harm|hurting myself)\b', re.IGNORECASE)
            ],
            "GENERAL_EMERGENCY_KEYWORDS": [
                re.compile(r'\b(emergency|urgent|help me|call 911|call 108|call 999|need help now|danger|critical)\b', re.IGNORECASE)
            ]
        }

        # Thresholds for audio-based detection (conceptual)
        self.audio_panic_threshold = 0.8
        self.audio_silence_threshold_seconds = 5 # How long before user silence is suspicious

        logger.info("EmergencyDetectionEngine initialized as the system watchdog.")

    async def check_for_emergency(self, text: str, audio_stream: Optional[Any] = None, context: Dict[str, Any] = None) -> bool:
        """
        Main function to check for emergencies from text and optionally audio input.

        Args:
            text (str): The transcribed text from the user.
            audio_stream (Optional[Any]): A conceptual audio stream or processed audio features.
            context (Dict[str, Any]): Session context (e.g., call_id, user_location).

        Returns:
            bool: True if an emergency is detected, False otherwise.
        """
        context = context if context is not None else {}
        logger.debug(f"Checking for emergency in text: '{text}'")

        # 1. Keyword-based detection (Text)
        text_lower = text.lower()
        detected_categories = set()
        for category, patterns in self.trigger_patterns.items():
            for pattern in patterns:
                if pattern.search(text_lower):
                    detected_categories.add(category)
                    logger.warning(f"Emergency trigger '{category}' detected from text: '{text}'")
                    break # Only need one trigger per category

        # 2. Sentiment-based detection (Text)
        if self.sentiment_analyzer:
            sentiment_output = self.sentiment_analyzer.analyze_sentiment(text, context.get("language", "en"))
            if sentiment_output.get("score", 0) < -0.8 or \
               sentiment_output.get("emotional_indicators", {}).get("panic") or \
               sentiment_output.get("emotional_indicators", {}).get("depression"):
                detected_categories.add("MENTAL_HEALTH_CRISIS")
                logger.warning(f"Extreme negative sentiment or emotional crisis indicators detected from text: '{text}'")

        # 3. Audio analysis (Conceptual)
        if self.audio_analyzer and audio_stream:
            # audio_features = self.audio_analyzer.extract_features(audio_stream)
            # if self.audio_analyzer.detect_panic_in_voice(audio_features) > self.audio_panic_threshold:
            #     detected_categories.add("AUDIO_PANIC")
            #     logger.warning("Panic/distress detected in user's voice.")
            pass # Placeholder for audio analysis logic

        # 4. Silence detection (Conceptual)
        if self.vad_engine and context.get("last_speech_time") and \
           (asyncio.get_event_loop().time() - context["last_speech_time"] > self.audio_silence_threshold_seconds):
            # If silence is detected after critical input, it might indicate distress
            if "MENTAL_HEALTH_CRISIS" in detected_categories:
                logger.warning("Prolonged silence after mental health crisis keywords. Possible distress.")
                # This could trigger an additional escalation or a prompt from the AI

        if detected_categories:
            logger.critical(f"EMERGENCY DETECTED: {', '.join(detected_categories)} for Call ID: {context.get('call_id', 'N/A')}. Initiating emergency response.")
            # Trigger immediate escalation via the EmergencyCallRouter
            if self.emergency_router:
                # Ensure a context has been provided, otherwise it won't have info to pass
                self.emergency_router.escalate_emergency_call(
                    call_id=context.get("call_id", "unknown_call"),
                    country_code=context.get("country_code", "US"),
                    caller_location=context.get("caller_location", {"source": "unknown"})
                )
            return True
        
        return False

    def bypass_normal_flow_if_emergency(self, detected_emergency: bool) -> bool:
        """
        Instructs the orchestrator to bypass normal conversational flow.
        """
        return detected_emergency

    def get_emergency_classification(self, text: str) -> List[str]:
        """
        Returns a list of specific emergency categories detected in the text.
        """
        text_lower = text.lower()
        detected_categories = []
        
        # 1. Check Keywords
        for category, patterns in self.trigger_patterns.items():
            for pattern in patterns:
                if pattern.search(text_lower):
                    detected_categories.append(category)
                    break
        
        # 2. FIX: Check Sentiment (consistent with check_for_emergency)
        if self.sentiment_analyzer:
            # We assume English for classification helper if no context provided
            sentiment_output = self.sentiment_analyzer.analyze_sentiment(text, "en")
            if sentiment_output.get("score", 0) < -0.8 or \
               sentiment_output.get("emotional_indicators", {}).get("panic") or \
               sentiment_output.get("emotional_indicators", {}).get("depression"):
                if "MENTAL_HEALTH_CRISIS" not in detected_categories:
                    detected_categories.append("MENTAL_HEALTH_CRISIS")

        return detected_categories

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock dependencies
    class MockNLUEngine:
        def process_text(self, text, lang):
            return {"intent": {"name": "general_question"}}

    class MockSentimentAnalyzer:
        def analyze_sentiment(self, text, lang):
            text_lower = text.lower()
            if "end it all" in text_lower or "hopeless" in text_lower:
                return {"label": "negative", "score": -0.9, "emotional_indicators": {"depression": True}}
            elif "crushing chest pain" in text_lower:
                return {"label": "negative", "score": -0.8}
            return {"label": "neutral", "score": 0.1}

    class MockEmergencyCallRouter:
        def escalate_emergency_call(self, call_id, country_code, caller_location):
            logger.critical(f"MOCK: EMERGENCY ESCALATED for call {call_id} in {country_code}. Location: {caller_location}")

    nlu_mock = MockNLUEngine()
    sentiment_mock = MockSentimentAnalyzer()
    emergency_router_mock = MockEmergencyCallRouter()
    
    detector = EmergencyDetectionEngine(
        nlu_engine=nlu_mock,
        sentiment_analyzer=sentiment_mock,
        emergency_router=emergency_router_mock
    )

    async def run_emergency_detection_tests():
        context = {"call_id": "test_call_1", "country_code": "US", "caller_location": {"lat": 34, "lon": -118}}

        print("\n--- Test 1: Cardiac Emergency ---")
        text1 = "I have crushing chest pain radiating to my left arm!"
        is_emergency1 = await detector.check_for_emergency(text1, context=context)
        print(f"Is emergency? {is_emergency1}, Categories: {detector.get_emergency_classification(text1)}")
        assert is_emergency1 is True
        assert "CARDAC" in detector.get_emergency_classification(text1)

        print("\n--- Test 2: Mental Health Crisis ---")
        text2 = "I feel so hopeless, I want to end it all."
        is_emergency2 = await detector.check_for_emergency(text2, context=context)
        print(f"Is emergency? {is_emergency2}, Categories: {detector.get_emergency_classification(text2)}")
        assert is_emergency2 is True
        assert "MENTAL_HEALTH_CRISIS" in detector.get_emergency_classification(text2)

        print("\n--- Test 3: Respiratory Emergency ---")
        text3 = "I can't breathe, I'm gasping for air!"
        is_emergency3 = await detector.check_for_emergency(text3, context=context)
        print(f"Is emergency? {is_emergency3}, Categories: {detector.get_emergency_classification(text3)}")
        assert is_emergency3 is True
        assert "RESPIRATORY" in detector.get_emergency_classification(text3)

        print("\n--- Test 4: No Emergency ---")
        text4 = "I have a mild headache."
        is_emergency4 = await detector.check_for_emergency(text4, context=context)
        print(f"Is emergency? {is_emergency4}, Categories: {detector.get_emergency_classification(text4)}")
        assert is_emergency4 is False

        print("\n--- Test 5: General Emergency Keyword ---")
        text5 = "I need help right now, it's an emergency!"
        is_emergency5 = await detector.check_for_emergency(text5, context=context)
        print(f"Is emergency? {is_emergency5}, Categories: {detector.get_emergency_classification(text5)}")
        assert is_emergency5 is True
        assert "GENERAL_EMERGENCY_KEYWORDS" in detector.get_emergency_classification(text5)

    import asyncio
    asyncio.run(run_emergency_detection_tests())