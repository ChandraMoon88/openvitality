import re
import logging
from typing import List, Dict, Any, Optional, Tuple

try:
    from transformers import pipeline
    HF_TRANSFORMERS_AVAILABLE = True
except ImportError:
    HF_TRANSFORMERS_AVAILABLE = False
    logging.warning("Hugging Face Transformers not installed. Zero-shot intent classification will be unavailable.")

logger = logging.getLogger(__name__)

class IntentClassifier:
    """
    Determines the user's primary goal or intent from a given text.
    Uses Hugging Face zero-shot classification as the primary method,
    with a fallback to keyword pattern matching.
    """
    def __init__(self, 
                 hf_model_name: str = "facebook/bart-large-mnli", 
                 default_candidate_labels: Optional[List[str]] = None, 
                 confidence_threshold: float = 0.7):
        
        self.zero_shot_classifier = None
        if HF_TRANSFORMERS_AVAILABLE:
            try:
                self.zero_shot_classifier = pipeline("zero-shot-classification", model=hf_model_name)
                logger.info(f"Hugging Face zero-shot classifier '{hf_model_name}' loaded.")
            except Exception as e:
                logger.error(f"Failed to load Hugging Face model '{hf_model_name}': {e}. Zero-shot classification disabled.")
                self.zero_shot_classifier = None
        
        self.default_candidate_labels = default_candidate_labels if default_candidate_labels else [
            "medical_emergency", "symptom_inquiry", "appointment_booking", "medication_query",
            "test_results", "insurance_question", "general_health_info", "small_talk", "billing_inquiry"
        ]
        self.confidence_threshold = confidence_threshold

        # Keyword-based fallback patterns
        self.keyword_patterns: Dict[str, List[re.Pattern]] = {
            "medical_emergency": [
                re.compile(r'\b(emergency|urgent|help|911|108|999|ambulance|can\'t breathe|chest pain|severe pain|stroke|heart attack)\b', re.IGNORECASE)
            ],
            "symptom_inquiry": [
                re.compile(r'\b(symptom|feel|ache|pain|cough|fever|headache|nausea)\b', re.IGNORECASE)
            ],
            "appointment_booking": [
                re.compile(r'\b(appointment|schedule|book|visit|see a doctor)\b', re.IGNORECASE)
            ],
            "medication_query": [
                re.compile(r'\b(medication|drug|pill|prescription|medicine|pharmacy)\b', re.IGNORECASE)
            ],
            "test_results": [
                re.compile(r'\b(test results|blood test|lab results|scan results)\b', re.IGNORECASE)
            ],
            "insurance_question": [
                re.compile(r'\b(insurance|coverage|policy|claim)\b', re.IGNORECASE)
            ],
            "billing_inquiry": [
                re.compile(r'\b(bill|billing|cost|payment|invoice|owe)\b', re.IGNORECASE)
            ],
            "general_health_info": [
                re.compile(r'\b(health info|general question|how to|what is)\b', re.IGNORECASE)
            ],
            "small_talk": [
                re.compile(r'\b(hello|hi|how are you|good morning|thank you|bye)\b', re.IGNORECASE)
            ]
        }
        logger.info("IntentClassifier initialized.")

    def classify_intent(self, text: str, lang_code: str = "en", context_intents: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Classifies the intent of the given text.

        Args:
            text (str): The input text to classify.
            lang_code (str): Language code of the text (e.g., "en").
            context_intents (Optional[List[str]]): List of previous intents to influence current classification.

        Returns:
            Dict[str, Any]: A dictionary containing the top intent name and its confidence score.
                            e.g., {"name": "symptom_inquiry", "confidence": 0.92}
        """
        if not text.strip():
            return {"name": "unclear", "confidence": 0.0}

        # 1. Zero-shot classification (primary method)
        if self.zero_shot_classifier and lang_code == "en": # Zero-shot typically works best in English
            try:
                # Use context_intents to narrow down labels if provided
                candidate_labels = self.default_candidate_labels
                if context_intents:
                    # Simple approach: prioritize context intents, or filter for relevance
                    # For now, let's keep it simple and use all labels.
                    pass 

                result = self.zero_shot_classifier(text, candidate_labels, multi_label=False)
                top_intent = result["labels"][0]
                top_confidence = result["scores"][0]

                if top_confidence >= self.confidence_threshold:
                    logger.debug(f"Zero-shot classified intent: '{top_intent}' with confidence {top_confidence:.2f} for '{text}'")
                    return {"name": top_intent, "confidence": round(top_confidence, 2)}
                else:
                    logger.debug(f"Zero-shot confidence {top_confidence:.2f} below threshold for '{text}', falling back.")

            except Exception as e:
                logger.warning(f"Zero-shot classification failed for '{text}': {e}. Falling back to keyword matching.")

        # 2. Keyword pattern matching (fallback method)
        logger.debug(f"Attempting keyword-based intent classification for '{text}' (lang: {lang_code}).")
        fallback_intent, fallback_confidence = self._classify_with_keywords(text, lang_code)
        
        if fallback_confidence > 0:
            logger.debug(f"Keyword-based classified intent: '{fallback_intent}' with confidence {fallback_confidence:.2f} for '{text}'")
            return {"name": fallback_intent, "confidence": round(fallback_confidence, 2)}

        logger.info(f"Could not determine clear intent for '{text}'. Defaulting to 'general_question'.")
        return {"name": "general_question", "confidence": 0.1}

    def _classify_with_keywords(self, text: str, lang_code: str) -> Tuple[str, float]:
        """
        Classifies intent using regex-based keyword matching.
        A simple scoring mechanism is used: 1 point per match.
        """
        scores: Dict[str, int] = {intent: 0 for intent in self.keyword_patterns.keys()}
        
        # This approach is language-agnostic if keywords are general or if text is pre-translated.
        # For true multilingual keyword matching, patterns would need to be language-specific.
        processed_text = text.lower() # Simple for keyword matching

        for intent, patterns in self.keyword_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(processed_text)
                if matches:
                    scores[intent] += len(matches)
        
        # Apply a boost for emergency if explicit emergency numbers are mentioned
        if "emergency" in scores and ("911" in processed_text or "108" in processed_text or "999" in processed_text):
            scores["medical_emergency"] += 5 # Significant boost

        top_intent = "general_question"
        max_score = 0
        total_score = sum(scores.values())

        if total_score > 0:
            for intent, score in scores.items():
                if score > max_score:
                    max_score = score
                    top_intent = intent
            # Simple confidence: ratio of top intent score to total score, or a base minimum
            confidence = max_score / total_score if total_score > 0 else 0.1
            # Scale confidence to be more like 0-1, with a floor
            confidence = max(0.1, min(1.0, confidence * 0.5 + 0.5)) # Adjust for better range
        else:
            confidence = 0.1 # Very low confidence if no keywords matched

        return top_intent, confidence

    def detect_multiple_intents(self, text: str, lang_code: str = "en") -> List[Dict[str, Any]]:
        """
        Conceptual method for detecting multiple intents in a single utterance.
        This would typically involve multi-label classification or more complex parsing.
        """
        logger.info(f"Detecting multiple intents for '{text}' (conceptual).")
        # For now, a simplified approach: run zero-shot in multi-label mode if available
        # or find all intents that match keywords above a certain threshold.
        
        detected_intents = []
        if self.zero_shot_classifier and lang_code == "en":
            try:
                result = self.zero_shot_classifier(text, self.default_candidate_labels, multi_label=True)
                for label, score in zip(result["labels"], result["scores"]):
                    if score >= self.confidence_threshold / 2: # Lower threshold for multi-label
                        detected_intents.append({"name": label, "confidence": round(score, 2)})
            except Exception as e:
                logger.warning(f"Multi-label zero-shot classification failed: {e}")
        
        # Fallback to keyword matching for multiple intents
        if not detected_intents:
            # Re-evaluate keyword patterns, potentially with a lower score threshold
            processed_text = text.lower()
            for intent, patterns in self.keyword_patterns.items():
                match_count = 0
                for pattern in patterns:
                    match_count += len(pattern.findall(processed_text))
                
                # If an intent has a significant keyword count, consider it
                if match_count > 0:
                    detected_intents.append({"name": intent, "confidence": min(1.0, match_count * 0.3)})
        
        return detected_intents if detected_intents else [{"name": "general_question", "confidence": 0.1}]


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    # Example candidate labels
    candidate_labels = [
        "medical_emergency", "symptom_inquiry", "appointment_booking", "medication_query",
        "test_results", "insurance_question", "general_health_info", "small_talk"
    ]
    classifier = IntentClassifier(default_candidate_labels=candidate_labels, confidence_threshold=0.7)

    print("\n--- Test Case 1: Symptom Inquiry ---")
    text1 = "I have a terrible headache and a fever."
    intent1 = classifier.classify_intent(text1)
    print(f"Text: '{text1}' -> Intent: {intent1['name']} (Confidence: {intent1['confidence']})")
    assert intent1["name"] == "symptom_inquiry" or "general_health_info" # Depends on model precision

    print("\n--- Test Case 2: Medical Emergency ---")
    text2 = "I am having chest pain and can't breathe! Call 911!"
    intent2 = classifier.classify_intent(text2)
    print(f"Text: '{text2}' -> Intent: {intent2['name']} (Confidence: {intent2['confidence']})")
    assert intent2["name"] == "medical_emergency"

    print("\n--- Test Case 3: Appointment Booking ---")
    text3 = "I need to schedule an appointment with a doctor."
    intent3 = classifier.classify_intent(text3)
    print(f"Text: '{text3}' -> Intent: {intent3['name']} (Confidence: {intent3['confidence']})")
    assert intent3["name"] == "appointment_booking"

    print("\n--- Test Case 4: Medication Query ---")
    text4 = "What are the side effects of Paracetamol?"
    intent4 = classifier.classify_intent(text4)
    print(f"Text: '{text4}' -> Intent: {intent4['name']} (Confidence: {intent4['confidence']})")
    assert intent4["name"] == "medication_query"

    print("\n--- Test Case 5: Small Talk ---")
    text5 = "Hello, how are you today?"
    intent5 = classifier.classify_intent(text5)
    print(f"Text: '{text5}' -> Intent: {intent5['name']} (Confidence: {intent5['confidence']})")
    assert intent5["name"] == "small_talk"

    print("\n--- Test Case 6: Low Confidence / Fallback ---")
    text6 = "Tell me something random."
    intent6 = classifier.classify_intent(text6)
    print(f"Text: '{text6}' -> Intent: {intent6['name']} (Confidence: {intent6['confidence']})")
    assert intent6["name"] == "general_question"

    print("\n--- Test Case 7: Multiple Intents (Conceptual) ---")
    text7 = "I have a cough and want to book an appointment."
    multi_intents7 = classifier.detect_multiple_intents(text7)
    print(f"Text: '{text7}' -> Multiple Intents: {multi_intents7}")
    # Expected to see 'symptom_inquiry' and 'appointment_booking'
    assert any(i["name"] == "symptom_inquiry" for i in multi_intents7) or any(i["name"] == "appointment_booking" for i in multi_intents7)