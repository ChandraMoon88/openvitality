
import sys
sys.path.append('.')

import unittest
from unittest.mock import MagicMock

from src.language.nlu_engine import NLUEngine

class TestNLUEngine(unittest.TestCase):

    def setUp(self):
        """Set up a new NLUEngine and mock components for each test."""
        self.nlu_engine = NLUEngine(cache_size=2)
        
        # Create mock instances for all dependencies
        self.mock_lang_detector = MagicMock()
        self.mock_tokenizer = MagicMock()
        self.mock_normalizer = MagicMock()
        self.mock_entity_extractor = MagicMock()
        self.mock_intent_classifier = MagicMock()
        self.mock_sentiment_analyzer = MagicMock()

        # Inject mock dependencies into the engine
        self.nlu_engine.set_language_detector(self.mock_lang_detector)
        self.nlu_engine.set_tokenizer(self.mock_tokenizer)
        self.nlu_engine.set_code_mix_normalizer(self.mock_normalizer)
        self.nlu_engine.set_entity_extractor(self.mock_entity_extractor)
        self.nlu_engine.set_intent_classifier(self.mock_intent_classifier)
        self.nlu_engine.set_sentiment_analyzer(self.mock_sentiment_analyzer)

        # Configure default return values for all mocks to prevent serialization errors
        self.mock_lang_detector.detect_language.return_value = {"lang": "en", "confidence": 1.0}
        self.mock_tokenizer.tokenize.return_value = []
        self.mock_entity_extractor.extract_entities.return_value = []
        self.mock_intent_classifier.classify_intent.return_value = {"name": "general_question", "confidence": 1.0}
        self.mock_sentiment_analyzer.analyze_sentiment.return_value = {"label": "neutral", "score": 0.0}

    def test_full_pipeline_flow(self):
        """Test the correct orchestration and data flow through the pipeline."""
        original_text = "Mujhe fever hai"
        normalized_text = "I have fever"

        # Configure return values for each mock component
        self.mock_lang_detector.detect_language.return_value = {"lang": "hi", "confidence": 0.9}
        # Reset side_effect and set return_value to ensure correct behavior
        self.mock_normalizer.side_effect = None
        self.mock_normalizer.normalize.return_value = normalized_text
        self.mock_tokenizer.tokenize.return_value = ["i", "have", "fever"]
        self.mock_entity_extractor.extract_entities.return_value = [{"type": "symptom", "value": "fever"}]
        self.mock_intent_classifier.classify_intent.return_value = {"name": "symptom_inquiry", "confidence": 0.85}
        self.mock_sentiment_analyzer.analyze_sentiment.return_value = {"label": "negative", "score": -0.7}

        # Process the text
        result = self.nlu_engine.process_text(original_text)

        # Assert that each component was called once
        self.mock_lang_detector.detect_language.assert_called_once_with(original_text)
        self.mock_normalizer.normalize.assert_called_once_with(original_text, "hi")
        self.mock_tokenizer.tokenize.assert_called_once_with(normalized_text, "hi")
        self.mock_entity_extractor.extract_entities.assert_called_once_with(normalized_text, "hi")
        self.mock_intent_classifier.classify_intent.assert_called_once_with(normalized_text, "hi")
        self.mock_sentiment_analyzer.analyze_sentiment.assert_called_once_with(normalized_text, "hi")

        # Assert that the final output is correctly assembled
        self.assertEqual(result["language"], "hi")
        self.assertEqual(result["normalized_text"], normalized_text)
        self.assertEqual(result["tokens"], ["i", "have", "fever"])
        self.assertEqual(result["entities"][0]["value"], "fever")
        self.assertEqual(result["intent"]["name"], "symptom_inquiry")
        self.assertEqual(result["sentiment"]["label"], "negative")

    def test_caching(self):
        """Test that the lru_cache is working as expected."""
        text = "This is a test sentence."
        self.mock_lang_detector.detect_language.return_value = {"lang": "en"}
        self.mock_normalizer.normalize.return_value = text
        
        # First call - should call the components
        result1 = self.nlu_engine.process_text(text)
        self.assertEqual(self.mock_lang_detector.detect_language.call_count, 1)
        self.assertEqual(self.mock_intent_classifier.classify_intent.call_count, 1)

        # Second call with same text - should NOT call the components again
        result2 = self.nlu_engine.process_text(text)
        self.assertEqual(self.mock_lang_detector.detect_language.call_count, 1)
        self.assertEqual(self.mock_intent_classifier.classify_intent.call_count, 1)
        
        # Verify the cached result is returned
        self.assertEqual(result1, result2)

    def test_error_handling(self):
        """Test that errors in the pipeline are caught and reported."""
        text = "Some input"
        error_message = "Intent model failed"
        self.mock_lang_detector.detect_language.return_value = {"lang": "en"}
        self.mock_normalizer.normalize.return_value = text
        self.mock_intent_classifier.classify_intent.side_effect = Exception(error_message)

        result = self.nlu_engine.process_text(text)

        # Assert that an error is reported in the output
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["error"], error_message)
        # Assert that default values are still present for other fields
        self.assertEqual(result["intent"]["name"], "general_question")

    def test_no_components_configured(self):
        """Test that the engine runs and returns defaults if no components are set."""
        # A fresh instance with no mocks set
        unconfigured_engine = NLUEngine()
        text = "Some text"
        result = unconfigured_engine.process_text(text)

        # Check for default values
        self.assertEqual(result["original_text"], text)
        self.assertEqual(result["language"], "en") # Falls back to 'en'
        self.assertEqual(result["intent"]["name"], "general_question")
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["sentiment"]["label"], "neutral")
        self.assertIsNone(result["error"])


if __name__ == "__main__":
    unittest.main()
