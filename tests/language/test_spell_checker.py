
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pytest
from unittest.mock import patch, MagicMock, mock_open
from src.language import spell_checker

# --- Mocks and Fixtures ---

@pytest.fixture
def mock_pyspellchecker():
    """Fixture to provide a mocked version of the pyspellchecker library's main class."""
    with patch('src.language.spell_checker.SpellChecker', autospec=True) as mock_spell_class:
        # Mock instance that will be returned when SpellChecker(language=...) is called
        mock_instance = mock_spell_class.return_value
        
        # Mock the methods of the instance
        mock_instance.candidates.return_value = None
        mock_instance.word_probability.return_value = 0.0
        mock_instance.word_frequency.load_words = MagicMock()

        # A function to configure the mock's behavior for a specific word
        def configure_correction(word, candidates, probabilities):
            if mock_instance.candidates.side_effect is None:
                mock_instance.candidates.side_effect = lambda w: candidates.get(w)
            else:
                original_side_effect = mock_instance.candidates.side_effect
                mock_instance.candidates.side_effect = lambda w: candidates.get(w, original_side_effect(w))

            if mock_instance.word_probability.side_effect is None:
                mock_instance.word_probability.side_effect = lambda p: probabilities.get(p, 0.0)
            else:
                original_prob_side_effect = mock_instance.word_probability.side_effect
                mock_instance.word_probability.side_effect = lambda p: probabilities.get(p, original_prob_side_effect(p))

        mock_instance.configure_correction = configure_correction
        yield mock_instance

@patch('src.language.spell_checker._PYSPELLCHECKER_AVAILABLE', True)
def get_spellchecker_instance(medical_dict_content=None, threshold=0.8):
    """Helper to get a SpellChecker instance with mocked file I/O if needed."""
    if medical_dict_content:
        with patch('builtins.open', mock_open(read_data=medical_dict_content)):
            with patch('os.path.exists', return_value=True):
                return spell_checker.SpellChecker(medical_dictionary_path="dummy/path.txt", correction_threshold=threshold)
    else:
        return spell_checker.SpellChecker(correction_threshold=threshold)


class TestSpellCheckerAvailability:
    
    @patch('src.language.spell_checker._PYSPELLCHECKER_AVAILABLE', False)
    def test_correction_returns_original_text_if_unavailable(self):
        """If pyspellchecker is not installed, it should return the original text."""
        from importlib import reload
        reload(spell_checker) # Force re-evaluation of the module-level flag
        
        checker = spell_checker.SpellChecker()
        text = "This is some mistyped text."
        corrected_text, corrections = checker.correct_text(text)
        
        assert corrected_text == text
        assert corrections == []

class TestSpellCheckerLogic:

    def test_auto_correction_above_threshold(self, mock_pyspellchecker):
        """Tests that a word is auto-corrected if confidence is high."""
        checker = get_spellchecker_instance(threshold=0.8)
        checker.spellcheckers['en'] = mock_pyspellchecker

        # Configure mock for "hedache"
        mock_pyspellchecker.configure_correction(
            word="hedache",
            candidates={"hedache": ["headache"]},
            probabilities={"headache": 0.9}
        )

        text = "I have a hedache."
        corrected_text, corrections = checker.correct_text(text, "en")

        assert corrected_text == "I have a headache."
        assert len(corrections) == 1
        assert corrections[0]['original'] == "hedache."
        assert corrections[0]['corrected'] == "headache."
        assert "suggested" not in corrections[0]

    def test_suggestion_below_threshold(self, mock_pyspellchecker):
        """Tests that a correction is suggested if confidence is below the threshold."""
        checker = get_spellchecker_instance(threshold=0.8)
        checker.spellcheckers['en'] = mock_pyspellchecker

        # Configure mock for "deease"
        mock_pyspellchecker.configure_correction(
            word="deease",
            candidates={"deease": ["disease"]},
            probabilities={"disease": 0.7}
        )

        text = "It is a rare deease."
        corrected_text, corrections = checker.correct_text(text, "en")

        assert corrected_text == "It is a rare deease." # Text is NOT changed
        assert len(corrections) == 1
        assert corrections[0]['original'] == "deease."
        assert corrections[0]['suggested'] == "disease"
        assert "corrected" not in corrections[0]

    def test_medical_dictionary_prevents_correction(self, mock_pyspellchecker):
        """Tests that words in the medical dictionary are not corrected."""
        medical_dict = "Aspirin\nHypertension\n"
        checker = get_spellchecker_instance(medical_dict_content=medical_dict)
        checker.spellcheckers['en'] = mock_pyspellchecker

        # The term "Hypertension" should now be in the medical_terms set
        assert "hypertension" in checker.medical_terms
        
        # Test that the term is not considered for correction
        text = "He has Hypertension."
        corrected_text, corrections = checker.correct_text(text, "en")
        
        assert corrected_text == "He has Hypertension."
        assert len(corrections) == 0
        # Check that `candidates` was not even called for this word
        # (This is harder to test with the current loop structure, but we can infer it
        # from the lack of corrections)

    def test_no_correction_for_known_words(self, mock_pyspellchecker):
        """Tests that correct words are not changed."""
        checker = get_spellchecker_instance()
        checker.spellcheckers['en'] = mock_pyspellchecker
        
        # `candidates` returns None for known words
        mock_pyspellchecker.configure_correction("sentence", candidates={"sentence": None}, probabilities={})

        text = "This is a correct sentence."
        corrected_text, corrections = checker.correct_text(text, "en")
        
        assert corrected_text == "This is a correct sentence."
        assert len(corrections) == 0

    def test_punctuation_is_preserved(self, mock_pyspellchecker):
        """Tests that punctuation attached to a word is handled correctly."""
        checker = get_spellchecker_instance(threshold=0.9)
        checker.spellcheckers['en'] = mock_pyspellchecker
        
        mock_pyspellchecker.configure_correction(
            "hellp",
            candidates={"hellp": ["help"]},
            probabilities={"help": 0.95}
        )

        text = "Can you hellp!?"
        corrected_text, corrections = checker.correct_text(text, "en")
        
        # The logic for reconstruction might be simple, so we test for a plausible outcome
        assert corrected_text == "Can you help!?"
        assert corrections[0]['original'] == "hellp!?"
        assert corrections[0]['corrected'] == "help!?"
