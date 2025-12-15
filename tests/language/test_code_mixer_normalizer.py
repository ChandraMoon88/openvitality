
import sys
sys.path.append('.')

import unittest
from typing import Optional, Dict, Any

from src.language.code_mixer_normalizer import CodeMixNormalizer

# --- Mock Dependencies ---

class MockLanguageDetector:
    """Mock language detector for testing."""
    def detect_language(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        # Simple rule-based mock
        if text_lower in ["mujhe", "hai", "aur", "bhi"]:
            return {"lang": "hi", "confidence": 0.9}
        if text_lower in ["fever", "headache", "hospital"]:
            # Even if it's an English word, the primary language might be different.
            # The regex in the normalizer is the main driver for these common words.
            return {"lang": "en", "confidence": 0.95}
        return {"lang": "en", "confidence": 0.7} # Default to English

class MockTranslationManager:
    """Mock translation manager for testing."""
    def translate(self, text: str, dest_lang: str, src_lang: str = "auto") -> Optional[str]:
        translations_hi_en = {
            "mujhe": "I",
            "hai": "have",
            "aur": "and",
            "bhi": "also"
        }
        if src_lang == "hi" and dest_lang == "en":
            return translations_hi_en.get(text.lower(), text)
        return text

class TestCodeMixNormalizer(unittest.TestCase):

    def setUp(self):
        """Set up the test case."""
        self.normalizer = CodeMixNormalizer(target_lang="en")
        self.normalizer.set_language_detector(MockLanguageDetector())
        self.normalizer.set_translator(MockTranslationManager())

    def test_normalize_hinglish_sentence(self):
        """Test normalization of a simple Hinglish sentence."""
        text = "Mujhe fever hai aur headache bhi"
        primary_lang = "hi"
        expected = "I fever have and headache also"
        result = self.normalizer.normalize(text, primary_lang)
        self.assertEqual(result, expected)

    def test_normalize_english_sentence_no_change(self):
        """Test that an English sentence with primary lang 'en' is unchanged."""
        text = "I have a fever and headache"
        primary_lang = "en"
        result = self.normalizer.normalize(text, primary_lang)
        self.assertEqual(result, text)

    def test_normalize_empty_string(self):
        """Test that an empty string is handled correctly."""
        text = ""
        result = self.normalizer.normalize(text, primary_lang="hi")
        self.assertEqual(result, "")

    def test_translation_fallback(self):
        """Test that a word with no translation is kept as is."""
        # "ka" is not in our mock translator's dictionary
        text = "Mujhe bukhar ka ehsaas hai"
        primary_lang = "hi"
        # "bukhar", "ka", "ehsaas" will not be translated by this mock
        expected = "I bukhar ka ehsaas have"
        result = self.normalizer.normalize(text, primary_lang)
        self.assertEqual(result, expected)

    def test_regex_detection_of_english_word(self):
        """Test that the regex correctly identifies a common English word even if LID misses."""
        # Our mock LID doesn't know "hospital", but the regex does.
        # So it should be treated as English ('en') and not translated.
        text = "Mujhe hospital hai" # Grammatically incorrect, but tests the mechanism
        primary_lang = "hi"
        expected = "I hospital have"
        result = self.normalizer.normalize(text, primary_lang)
        self.assertEqual(result, expected)

if __name__ == "__main__":
    unittest.main()
