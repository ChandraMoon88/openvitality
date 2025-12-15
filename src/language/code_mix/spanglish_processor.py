import logging
import re
from typing import List, Tuple, Optional, Any

# Assuming a LanguageDetector and TranslationManager exist elsewhere
# from src.voice.stt.language_identification import LanguageIdentifier # If used for word-level LID
from src.language.translator_api import TranslationManager

logger = logging.getLogger(__name__)

class SpanglishProcessor:
    """
    Specialized processor for Spanglish (Spanish+English code-mixing).
    Identifies language segments, handles false friends, and manages borrowing
    of medical terms to normalize text into a primary language (typically English)
    for NLU processing.
    """
    def __init__(self, target_lang: str = "en"):
        self.target_lang = target_lang
        # Placeholders for actual language detection and translation services
        self.language_detector = None # For word/phrase level LID
        self.translator = None # TranslationManager()

        # Common "false friends" in Spanish/English that can cause confusion
        # (Spanish word, expected English translation for NLU context)
        self.false_friends = {
            "embarazada": "pregnant",  # Not "embarrassed"
            "sopa": "soup",            # Not "soap"
            "exito": "success",        # Not "exit"
            "sensible": "sensitive",   # Not "sensible"
            "delito": "crime",         # Not "delight"
            "librería": "bookstore",    # Not "library"
        }

        # Medical terms commonly borrowed from English into Spanish, which should
        # ideally remain in English in the normalized text if target_lang is English.
        self.medical_borrowings = [
            "doctor", "appointment", "cancer", "diabetes", "check-up", "scan",
            "medicine", "therapy", "surgery", "clinic", "hospital", "allergy"
        ]
        
        # Regex for splitting text into words and punctuation
        self.word_punc_splitter = re.compile(r"(\w+|\W+)")

        logger.info(f"SpanglishProcessor initialized with target language: {self.target_lang}")

    def set_language_detector(self, detector_instance: Any): # Placeholder for concrete type
        self.language_detector = detector_instance
        logger.debug("Language detector set for SpanglishProcessor.")

    def set_translator(self, translator_instance: TranslationManager):
        self.translator = translator_instance
        logger.debug("Translation manager set for SpanglishProcessor.")

    def process(self, text: str, primary_lang: str = "es") -> str:
        """
        Processes a Spanglish sentence to normalize it into the target language.

        Args:
            text (str): The Spanglish input text.
            primary_lang (str): The assumed dominant language of the input (e.g., "es" for Spanish).

        Returns:
            str: The normalized text, primarily in the target language (self.target_lang).
        """
        if not text.strip():
            return ""
        
        # If the target language is not English, this processor might need adjustment
        if self.target_lang != "en":
            logger.warning(f"SpanglishProcessor is optimized for target_lang='en'. Current target: '{self.target_lang}'")

        # Step 1: Split into word/punctuation segments
        segments = [s for s in self.word_punc_splitter.findall(text) if s.strip()]
        
        normalized_parts: List[str] = []

        for segment in segments:
            segment_lower = segment.lower()
            
            # Check for medical borrowings (keep as is if English is target)
            if self.target_lang == "en" and segment_lower in self.medical_borrowings:
                normalized_parts.append(segment)
                continue

            # Check for false friends
            if segment_lower in self.false_friends:
                # If target is English, replace with the correct English meaning
                if self.target_lang == "en":
                    normalized_parts.append(self.false_friends[segment_lower])
                    logger.debug(f"Resolved false friend '{segment}' to '{self.false_friends[segment_lower]}'")
                    continue
                # If target is Spanish, leave as is, or handle differently
                
            # Attempt word-level language detection
            detected_lang = primary_lang # Default to primary
            if self.language_detector:
                lang_res = self.language_detector.detect_language(segment)
                if lang_res and lang_res.get("lang") and lang_res.get("confidence", 0) > 0.6: # Confidence check
                    detected_lang = lang_res["lang"]

            # If segment is in primary_lang (Spanish) and primary_lang is not target_lang (English), translate
            if detected_lang == primary_lang and primary_lang != self.target_lang and self.translator:
                translated_segment = self.translator.translate(segment, dest_lang=self.target_lang, src_lang=primary_lang)
                if translated_segment:
                    normalized_parts.append(translated_segment)
                    logger.debug(f"Translated '{segment}' from {primary_lang} to {self.target_lang}")
                else:
                    normalized_parts.append(segment) # Fallback
            else:
                normalized_parts.append(segment)
        
        normalized_text = "".join(normalized_parts) # Basic join, might need more intelligent re-joining

        # Post-processing for common Spanglish grammar patterns or rephrasing
        # Example: "Me duele the head" -> "My head hurts" (requires advanced NLP)
        if "me duele the " in normalized_text.lower() and self.target_lang == "en":
            # Very simplistic regex for this specific pattern
            normalized_text = re.sub(r"me duele the (\w+)", r"my \1 hurts", normalized_text, flags=re.IGNORECASE)
            logger.debug(f"Applied Spanglish grammar fix: {normalized_text}")

        logger.debug(f"Original text: '{text}' -> Normalized: '{normalized_text}'")
        return normalized_text

# Mock LanguageDetector (simplified for example)
class MockLanguageDetector:
    def detect_language(self, text):
        text_lower = text.lower()
        if "duele" in text_lower or "cabeza" in text_lower:
            return {"lang": "es", "confidence": 0.9}
        if "head" in text_lower or "pain" in text_lower:
            return {"lang": "en", "confidence": 0.9}
        return {"lang": "en", "confidence": 0.5} # Default to English, lower confidence

# Mock TranslationManager (simplified for example)
class MockTranslationManager:
    def translate(self, text: str, dest_lang: str, src_lang: str = "auto") -> Optional[str]:
        if src_lang == "es" and dest_lang == "en":
            if text.lower() == "hola": return "Hello"
            if text.lower() == "me": return "I"
            if text.lower() == "duele": return "hurt"
            if text.lower() == "la": return "the"
            if text.lower() == "cabeza": return "head"
            if text.lower() == "tengo": return "I have"
            if text.lower() == "cita": return "appointment"
            if text.lower() == "embarazada": return "pregnant"
            # Simulate a real translator
            if text == "Me duele la cabeza": return "My head hurts"
            if text == "Me duele el estómago": return "My stomach hurts"
        return text # Return original if no specific translation

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    processor = SpanglishProcessor(target_lang="en")
    processor.set_language_detector(MockLanguageDetector())
    processor.set_translator(MockTranslationManager())

    print("\n--- Test Case 1: Simple Code-mix ---")
    text1 = "Hola, I have a headache."
    normalized1 = processor.process(text1, primary_lang="es")
    print(f"Original: '{text1}'\nNormalized: '{normalized1}'")
    assert "Hello, I have a headache." == normalized1

    print("\n--- Test Case 2: False Friend ---")
    text2 = "Estoy embarazada, not embarrassed."
    normalized2 = processor.process(text2, primary_lang="es")
    print(f"Original: '{text2}'\nNormalized: '{normalized2}'")
    assert "Estoy pregnant, not embarrassed." == normalized2

    print("\n--- Test Case 3: Borrowed Medical Term ---")
    text3 = "Necesito un appointment with the doctor."
    normalized3 = processor.process(text3, primary_lang="es")
    print(f"Original: '{text3}'\nNormalized: '{normalized3}'")
    assert "Necesito un appointment with the doctor." == normalized3 # 'appointment' and 'doctor' remain English

    print("\n--- Test Case 4: Grammar Reconstruction Example ---")
    text4 = "Me duele the head."
    normalized4 = processor.process(text4, primary_lang="es")
    print(f"Original: '{text4}'\nNormalized: '{normalized4}'")
    assert "My head hurts." == normalized4

    print("\n--- Test Case 5: Complex Spanglish ---")
    text5 = "Mi mamá está embarazada y tiene un exito en la vida. Necesita un check-up."
    normalized5 = processor.process(text5, primary_lang="es")
    print(f"Original: '{text5}'\nNormalized: '{normalized5}'")
    # Expected: "My mom is pregnant and has a success in life. Needs a check-up."
    # Depending on mock translation/LID, may vary.
    assert "pregnant" in normalized5.lower() and "success" in normalized5.lower() and "check-up" in normalized5.lower()

    print("\n--- Test Case 6: Pure Spanish ---")
    text6 = "Me duele la cabeza."
    normalized6 = processor.process(text6, primary_lang="es")
    print(f"Original: '{text6}'\nNormalized: '{normalized6}'")
    assert "My head hurts." == normalized6
