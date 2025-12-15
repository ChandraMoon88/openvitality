import logging
from typing import Dict, Any, List, Optional
from functools import lru_cache
import json

# Assuming these modules will be implemented later
# from .tokenizer_multilingual import MultilingualTokenizer
# from .entity_extractor_medical import MedicalEntityExtractor
# from .intent_parser import IntentClassifier
# from .sentiment_analyzer import SentimentAnalyzer
# from .code_mixer_normalizer import CodeMixNormalizer
# from src.voice.stt.language_identification import LanguageIdentifier

logger = logging.getLogger(__name__)

class NLUEngine:
    """
    Main Natural Language Understanding (NLU) pipeline.
    Orchestrates various stages like language detection, tokenization,
    code-mix normalization, entity extraction, intent classification,
    and sentiment analysis.
    """
    def __init__(self, cache_size: int = 128):
        self.cache_size = cache_size
        self._process_text_cached = lru_cache(maxsize=self.cache_size)(self._process_text)
        
        # Placeholders for sub-components (will be instantiated with actual implementations later)
        self.language_detector = None # LanguageIdentifier()
        self.tokenizer = None         # MultilingualTokenizer()
        self.code_mix_normalizer = None # CodeMixNormalizer()
        self.entity_extractor = None  # MedicalEntityExtractor()
        self.intent_classifier = None # IntentClassifier()
        self.sentiment_analyzer = None # SentimentAnalyzer()

        logger.info(f"NLUEngine initialized with cache size: {self.cache_size}")

    def set_language_detector(self, detector_instance: Any):
        self.language_detector = detector_instance
        logger.debug("Language detector set.")

    def set_tokenizer(self, tokenizer_instance: Any):
        self.tokenizer = tokenizer_instance
        logger.debug("Tokenizer set.")

    def set_code_mix_normalizer(self, normalizer_instance: Any):
        self.code_mix_normalizer = normalizer_instance
        logger.debug("Code-mix normalizer set.")

    def set_entity_extractor(self, extractor_instance: Any):
        self.entity_extractor = extractor_instance
        logger.debug("Entity extractor set.")

    def set_intent_classifier(self, classifier_instance: Any):
        self.intent_classifier = classifier_instance
        logger.debug("Intent classifier set.")

    def set_sentiment_analyzer(self, analyzer_instance: Any):
        self.sentiment_analyzer = analyzer_instance
        logger.debug("Sentiment analyzer set.")

    def process_text(self, text: str, session_language: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes the input text through the NLU pipeline.
        Uses caching for duplicate queries.
        """
        # The session_language parameter is not part of the cache key because
        # the _process_text method internally detects language, so providing
        # session_language is a hint, but the output should be consistent
        # regardless of whether the hint was provided, assuming the text is the same.
        # If session_language *must* influence the output for the same text, 
        # then it should be part of the cache key. For now, we assume it's for efficiency/hinting.
        return self._process_text_cached(text)

    def _process_text(self, text: str) -> Dict[str, Any]:
        """
        Internal method to process text without caching.
        """
        logger.info(f"Processing text: '{text}'")
        output = {
            "original_text": text,
            "language": "unknown",
            "translated_text": text, # Placeholder for translation
            "normalized_text": text, # Placeholder for code-mix normalization
            "tokens": [],
            "intent": {"name": "general_question", "confidence": 0.0},
            "entities": [],
            "sentiment": {"label": "neutral", "score": 0.0},
            "error": None
        }

        try:
            # 1. Language Detection
            if self.language_detector:
                detected_lang = self.language_detector.detect_language(text)
                output["language"] = detected_lang.get("lang", "en")
                output["lang_confidence"] = detected_lang.get("confidence", 0.0)
            else:
                output["language"] = "en" # Fallback
                logger.warning("No language detector configured. Defaulting to 'en'.")

            # 2. Code-mix Normalization (e.g., Hinglish -> English)
            if self.code_mix_normalizer:
                output["normalized_text"] = self.code_mix_normalizer.normalize(text, output["language"])
            
            # 3. Tokenization
            if self.tokenizer:
                output["tokens"] = self.tokenizer.tokenize(output["normalized_text"], output["language"])

            # 4. Entity Extraction
            if self.entity_extractor:
                output["entities"] = self.entity_extractor.extract_entities(output["normalized_text"], output["language"])

            # 5. Intent Classification
            if self.intent_classifier:
                output["intent"] = self.intent_classifier.classify_intent(output["normalized_text"], output["language"])

            # 6. Sentiment Analysis
            if self.sentiment_analyzer:
                output["sentiment"] = self.sentiment_analyzer.analyze_sentiment(output["normalized_text"], output["language"])

            # Placeholder for actual translation logic if needed (e.g., if NLU components only work on English)
            # if output["language"] != "en" and self.translator:
            #     output["translated_text"] = self.translator.translate(text, output["language"], "en")

        except Exception as e:
            logger.error(f"Error during NLU processing: {e}", exc_info=True)
            output["error"] = str(e)
            # Revert to original text if processing fails
            output["normalized_text"] = text
            output["translated_text"] = text

        logger.debug(f"NLU output for '{text}': {json.dumps(output, indent=2)}")
        return output

# Example Usage (with mock components)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock NLU components
    class MockLanguageDetector:
        def detect_language(self, text):
            if "hindi" in text.lower() or "mujhe" in text.lower():
                return {"lang": "hi", "confidence": 0.9}
            if "spanish" in text.lower() or "hola" in text.lower():
                return {"lang": "es", "confidence": 0.85}
            return {"lang": "en", "confidence": 0.95}

    class MockTokenizer:
        def tokenize(self, text, lang):
            return text.lower().split()

    class MockCodeMixNormalizer:
        def normalize(self, text, lang):
            if lang == "hi" and "fever hai" in text.lower():
                return text.lower().replace("fever hai", "have fever")
            return text

    class MockMedicalEntityExtractor:
        def extract_entities(self, text, lang):
            entities = []
            if "fever" in text.lower():
                entities.append({"type": "symptom", "value": "fever"})
            if "pain" in text.lower():
                entities.append({"type": "symptom", "value": "pain"})
            if "3 days" in text.lower():
                entities.append({"type": "duration", "value": "3 days"})
            return entities

    class MockIntentClassifier:
        def classify_intent(self, text, lang):
            if "appointment" in text.lower() or "book" in text.lower():
                return {"name": "appointment_booking", "confidence": 0.9}
            if "emergency" in text.lower() or "urgent" in text.lower():
                return {"name": "medical_emergency", "confidence": 0.98}
            return {"name": "general_question", "confidence": 0.7}

    class MockSentimentAnalyzer:
        def analyze_sentiment(self, text, lang):
            if "pain" in text.lower() or "emergency" in text.lower():
                return {"label": "negative", "score": -0.8}
            if "thank you" in text.lower():
                return {"label": "positive", "score": 0.9}
            return {"label": "neutral", "score": 0.1}

    nlu_engine = NLUEngine(cache_size=2)
    nlu_engine.set_language_detector(MockLanguageDetector())
    nlu_engine.set_tokenizer(MockTokenizer())
    nlu_engine.set_code_mix_normalizer(MockCodeMixNormalizer())
    nlu_engine.set_entity_extractor(MockMedicalEntityExtractor())
    nlu_engine.set_intent_classifier(MockIntentClassifier())
    nlu_engine.set_sentiment_analyzer(MockSentimentAnalyzer())


    # Test cases
    print("\n--- Test Case 1: English (Symptom Report) ---")
    output1 = nlu_engine.process_text("I have a fever for 3 days.")
    print(json.dumps(output1, indent=2))

    print("\n--- Test Case 2: Hindi Code-mix (Symptom Report) ---")
    output2 = nlu_engine.process_text("Mujhe fever hai aur head pain bhi.")
    print(json.dumps(output2, indent=2))
    
    print("\n--- Test Case 3: English (Appointment Booking) ---")
    output3 = nlu_engine.process_text("I want to book an appointment.")
    print(json.dumps(output3, indent=2))

    print("\n--- Test Case 4: Emergency ---")
    output4 = nlu_engine.process_text("This is an urgent medical emergency!")
    print(json.dumps(output4, indent=2))

    print("\n--- Test Case 5: Spanish ---")
    output5 = nlu_engine.process_text("Hola, tengo dolor de cabeza.")
    print(json.dumps(output5, indent=2))

    print("\n--- Test Cache (re-processing output1) ---")
    output1_cached = nlu_engine.process_text("I have a fever for 3 days.")
    print(f"Is output1_cached the same as output1? {output1_cached == output1}") # Should be True if caching works
