
import sys
sys.path.append('.')

import unittest
from unittest.mock import MagicMock, patch

# We patch spacy at the top to prevent it from being required for tests
sys.modules['spacy'] = MagicMock()

from src.language.entity_extractor_medical import MedicalEntityExtractor

class TestMedicalEntityExtractor(unittest.TestCase):

    def setUp(self):
        """Setup a new MedicalEntityExtractor for each test."""
        # Initialize the extractor. It will think spacy is installed but loading will fail,
        # which is a good default state for testing fallbacks.
        with patch('spacy.load', side_effect=OSError) as mock_load:
            self.extractor = MedicalEntityExtractor()
        # We can confirm that spacy was disabled
        self.assertIsNone(self.extractor.nlp)

    def test_regex_duration_extraction(self):
        """Test extraction of duration entities using regex."""
        text = "I have had a fever for 3 days and was sick a few weeks ago."
        entities = self.extractor._extract_regex_entities(text)
        
        self.assertEqual(len(entities), 2)
        self.assertIn('DURATION', [e['type'] for e in entities])
        
        texts = [e['text'] for e in entities]
        self.assertIn('3 days', texts)
        self.assertIn('a few weeks', texts)

    def test_regex_dosage_extraction(self):
        """Test extraction of dosage entities using regex."""
        text = "Take 500mg of Paracetamol and two pills of Ibuprofen 200 g."
        entities = self.extractor._extract_regex_entities(text)
        
        self.assertEqual(len(entities), 3)
        self.assertTrue(all(e['type'] == 'DOSAGE' for e in entities))

        texts = [e['text'] for e in entities]
        self.assertIn('500mg', texts)
        self.assertIn('two pills', texts)
        self.assertIn('200 g', texts)

    def test_keyword_extraction_fallback(self):
        """Test keyword-based extraction when no NER model is available."""
        # self.extractor.nlp is already None from setUp
        text = "I have a fever, a cough, and pain in my stomach."
        entities = self.extractor._extract_keyword_entities(text)
        
        self.assertGreaterEqual(len(entities), 3)
        types = [e['type'] for e in entities]
        self.assertIn('SYMPTOM', types)
        self.assertIn('BODY_PART', types)
        
        texts = [e['text'].lower() for e in entities]
        self.assertIn('fever', texts)
        self.assertIn('cough', texts)
        self.assertIn('stomach', texts)

    def test_spacy_entity_extraction(self):
        """Test the integration with a mocked spaCy NER model."""
        # Create a mock for a spaCy entity
        mock_ent = MagicMock()
        mock_ent.text = "Cardizem"
        mock_ent.label_ = "CHEMICAL"
        mock_ent.start_char = 15
        mock_ent.end_char = 23

        # Create a mock for the spaCy doc object
        mock_doc = MagicMock()
        mock_doc.ents = [mock_ent]
        
        # Mock the nlp object to return the mock doc
        self.extractor.nlp = MagicMock(return_value=mock_doc)

        text = "The patient took Cardizem for his condition."
        entities = self.extractor.extract_entities(text)
        
        # The result should contain the spaCy entity and potentially regex entities
        self.assertGreaterEqual(len(entities), 1)
        
        spacy_entity = next((e for e in entities if e['source'] == 'spacy_ner'), None)
        self.assertIsNotNone(spacy_entity)
        self.assertEqual(spacy_entity['text'], "Cardizem")
        self.assertEqual(spacy_entity['type'], "CHEMICAL")

    def test_entity_normalization(self):
        """Test the simple normalization logic."""
        # Plural
        self.assertEqual(self.extractor._normalize_entity("fevers", "SYMPTOM"), "fever")
        # Singular
        self.assertEqual(self.extractor._normalize_entity("cough", "SYMPTOM"), "cough")
        # Different type
        self.assertEqual(self.extractor._normalize_entity("tablets", "DOSAGE"), "tablets")

    def test_empty_and_no_entity_text(self):
        """Test that empty text or text with no entities returns an empty list."""
        # Since our keyword search is broad, we'll test this on the specific methods
        self.assertEqual(self.extractor.extract_entities(""), [])
        # Test with nlp disabled
        self.extractor.nlp = None
        self.assertEqual(self.extractor.extract_entities("This is a normal sentence."), [])


if __name__ == '__main__':
    unittest.main()
