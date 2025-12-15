
import sys
sys.path.append('.')

import unittest
from unittest.mock import MagicMock, patch

# Mock the transformers library at the top level so it's not required for tests
mock_transformers = MagicMock()
sys.modules['transformers'] = mock_transformers

from src.language.intent_parser import IntentClassifier

class TestIntentClassifier(unittest.TestCase):

    def test_keyword_emergency_classification(self):
        """Test keyword-based classification for emergency intent."""
        # Initialize without a HF model for pure keyword testing
        classifier = IntentClassifier()
        classifier.zero_shot_classifier = None 
        
        text = "I am having severe chest pain, this is an emergency!"
        result = classifier.classify_intent(text)
        self.assertEqual(result['name'], 'medical_emergency')

    def test_keyword_appointment_classification(self):
        """Test keyword-based classification for appointment booking."""
        classifier = IntentClassifier()
        classifier.zero_shot_classifier = None

        text = "I need to book an appointment for next week."
        result = classifier.classify_intent(text)
        self.assertEqual(result['name'], 'appointment_booking')

    def test_keyword_no_match_fallback(self):
        """Test fallback to default when no keywords match."""
        classifier = IntentClassifier()
        classifier.zero_shot_classifier = None

        text = "The sky is blue today."
        result = classifier.classify_intent(text)
        self.assertEqual(result['name'], 'general_question')

    def test_hf_classification_success(self):
        """Test successful classification using a mocked Hugging Face model."""
        # Mock the HF pipeline function to return a mock classifier
        mock_classifier = MagicMock()
        mock_transformers.pipeline.return_value = mock_classifier
        
        classifier = IntentClassifier()
        
        # Configure the mock classifier's return value for a specific input
        text = "I feel a bit sick."
        hf_result = {"labels": ["symptom_inquiry"], "scores": [0.95]}
        mock_classifier.return_value = hf_result

        result = classifier.classify_intent(text)

        # Check that the HF classifier was called
        mock_classifier.assert_called_once_with(text, classifier.default_candidate_labels, multi_label=False)
        # Check that the result is from the HF model
        self.assertEqual(result['name'], 'symptom_inquiry')
        self.assertEqual(result['confidence'], 0.95)

    def test_hf_low_confidence_fallback_to_keywords(self):
        """Test fallback to keywords when HF confidence is below threshold."""
        mock_classifier = MagicMock()
        mock_transformers.pipeline.return_value = mock_classifier
        
        classifier = IntentClassifier(confidence_threshold=0.8)

        # HF result is below the 0.8 threshold
        text = "I need to schedule a visit to check my fever."
        hf_result = {"labels": ["appointment_booking"], "scores": [0.7]}
        mock_classifier.return_value = hf_result

        result = classifier.classify_intent(text)
        
        # The result should come from the keyword fallback.
        # "fever" is a keyword for symptom_inquiry.
        # "schedule" is a keyword for appointment_booking.
        # The keyword classifier gives 1 point per match, so it's a tie.
        # The code returns the first one it finds with the max score. Let's check for either.
        self.assertIn(result['name'], ['symptom_inquiry', 'appointment_booking'])

    def test_no_hf_model_initially_uses_keywords(self):
        """Test that the classifier falls back to keywords if the HF model fails to load."""
        # Force the pipeline to raise an error
        mock_transformers.pipeline.side_effect = Exception("Model not found")

        classifier = IntentClassifier()
        self.assertIsNone(classifier.zero_shot_classifier)

        text = "I want to talk about my bill."
        result = classifier.classify_intent(text)
        self.assertEqual(result['name'], 'billing_inquiry')
    
    def test_empty_string_input(self):
        """Test that an empty string returns 'unclear' intent."""
        classifier = IntentClassifier()
        text = "   "
        result = classifier.classify_intent(text)
        self.assertEqual(result['name'], 'unclear')
        self.assertEqual(result['confidence'], 0.0)


if __name__ == '__main__':
    # Reset the mock after module is loaded
    mock_transformers.pipeline.side_effect = None
    unittest.main()
