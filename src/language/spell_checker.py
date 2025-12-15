# Purpose: Correct typos in user input
# What to add:
# Library: pyspellchecker, Hunspell, or custom dictionary
# Language-specific dictionaries: Load based on detected language
# Medical dictionary: Add common medical terms to prevent false corrections
# Confidence score: Only auto-correct if very confident
# User confirmation: For less confident suggestions, ask user "Did you mean X?"

import logging
from typing import List, Dict, Optional, Tuple, Any
import os
import re

# Try to import pyspellchecker
try:
    from spellchecker import SpellChecker # type: ignore
    _PYSPELLCHECKER_AVAILABLE = True
except ImportError:
    logging.warning("pyspellchecker not found. Spell checking will be unavailable.")
    _PYSPELLCHECKER_AVAILABLE = False

logger = logging.getLogger(__name__)

class SpellChecker:
    """
    Corrects typos in user input, with support for multiple languages
    and a specialized medical dictionary.
    """
    def __init__(self,
                 language_models: Dict[str, str] = None,
                 medical_dictionary_path: Optional[str] = None,
                 correction_threshold: float = 0.7): # Minimum probability for auto-correction
        self.spellcheckers: Dict[str, SpellChecker] = {}
        self.correction_threshold = correction_threshold
        self.medical_terms: set[str] = set()

        # Load default language models if none provided
        if language_models is None:
            language_models = {"en": "en_US", "es": "es"} # pyspellchecker uses ISO 639-1 codes or specific dictionary paths

        if _PYSPELLCHECKER_AVAILABLE:
            for lang_code, lang_model_path in language_models.items():
                try:
                    # pyspellchecker expects language code like 'en', 'es', or a path to a dictionary
                    # If it's a code, it will download it if not present.
                    # For custom models, lang_model_path would be the path.
                    self.spellcheckers[lang_code] = SpellChecker(language=lang_model_path)
                    logger.info(f"pyspellchecker initialized for language: {lang_code}")
                except Exception as e:
                    logger.error(f"Could not load pyspellchecker for {lang_code} with model {lang_model_path}: {e}")
                    # If loading fails, remove from dictionary to avoid errors later
                    self.spellcheckers.pop(lang_code, None)
        else:
            logger.warning("pyspellchecker is not available, spell checking will be minimal.")

        # Load medical dictionary
        if medical_dictionary_path:
            self._load_medical_dictionary(medical_dictionary_path)
        logger.info(f"SpellChecker initialized. Correction threshold: {self.correction_threshold}")

    def _load_medical_dictionary(self, file_path: str):
        """Loads medical terms from a file to prevent false corrections."""
        if not os.path.exists(file_path):
            logger.warning(f"Medical dictionary file not found at: {file_path}")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    term = line.strip().lower()
                    if term:
                        self.medical_terms.add(term)
            logger.info(f"Loaded {len(self.medical_terms)} medical terms from {file_path}")

            # Add medical terms to all loaded spellcheckers' dictionaries
            if _PYSPELLCHECKER_AVAILABLE:
                for lang_checker in self.spellcheckers.values():
                    lang_checker.word_frequency.load_words(list(self.medical_terms))
                    logger.debug(f"Added medical terms to {lang_checker.language_code} spellchecker.")

        except Exception as e:
            logger.error(f"Error loading medical dictionary from {file_path}: {e}")

    def correct_text(self, text: str, lang: str = "en") -> Tuple[str, List[Dict[str, Any]]]:
        """
        Corrects spelling in the input text for a given language.

        :param text: The input string potentially containing typos.
        :param lang: The language code to use for correction.
        :return: A tuple containing the corrected text and a list of corrections made.
                 Each correction is a dict: {'original': str, 'corrected': str, 'confidence': float}.
        """
        if not _PYSPELLCHECKER_AVAILABLE or lang not in self.spellcheckers:
            logger.warning(f"No spell checker available for language '{lang}'. Returning original text.")
            return text, []

        checker = self.spellcheckers[lang]
        words = text.split() # Simple whitespace split for initial tokenization
        corrected_words = []
        corrections_made: List[Dict[str, Any]] = []

        for word in words:
            original_word = word
            # Clean word from punctuation for checking, but keep original for replacement
            cleaned_word = re.sub(r'[^a-zA-Z\]', '', word).lower() # Keep apostrophes for contractions

            if not cleaned_word: # Handle empty strings after cleaning
                corrected_words.append(original_word)
                continue

            # Skip if it's a known medical term (already added to checker, but double check)
            if cleaned_word in self.medical_terms:
                corrected_words.append(original_word)
                continue

            # Get potential corrections and their probabilities
            candidates = checker.candidates(cleaned_word)
            best_correction = None
            max_probability = 0.0

            if candidates:
                # Find the candidate with the highest probability
                for candidate in candidates:
                    prob = checker.word_probability(candidate)
                    if prob > max_probability:
                        max_probability = prob
                        best_correction = candidate

            if best_correction and best_correction != cleaned_word:
                # If confidence is above threshold, auto-correct
                if max_probability >= self.correction_threshold:
                    # Reconstruct the word with original casing/punctuation if possible
                    # This is a simplification; a full implementation would preserve more
                    # about original word structure.
                    corrected_word_with_case = re.sub(re.escape(cleaned_word), best_correction, original_word, flags=re.IGNORECASE)
                    corrected_words.append(corrected_word_with_case)
                    corrections_made.append({
                        "original": original_word,
                        "corrected": corrected_word_with_case,
                        "confidence": max_probability
                    })
                    logger.debug(f"Auto-corrected '{original_word}' to '{corrected_word_with_case}' with confidence {max_probability:.2f}")
                else:
                    # Suggest for confirmation if confidence is lower
                    corrected_words.append(original_word) # Keep original in text
                    corrections_made.append({
                        "original": original_word,
                        "suggested": best_correction,
                        "confidence": max_probability
                    })
                    logger.debug(f"Suggested correction for '{original_word}' to '{best_correction}' with confidence {max_probability:.2f} (below threshold).")
            else:
                corrected_words.append(original_word)

        return " ".join(corrected_words), corrections_made

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Create a dummy medical dictionary file
    dummy_medical_dict_path = "medical_terms.txt"
    with open(dummy_medical_dict_path, "w", encoding="utf-8") as f:
        f.write("Aspirin\n")
        f.write("Paracetamol\n")
        f.write("Hypertension\n")
        f.write("Diabetes\n")
        f.write("Anaemia\n")

    # Initialize SpellChecker with English, Spanish, and a medical dictionary
    checker = SpellChecker(
        language_models={"en": "en_US", "es": "es"},
        medical_dictionary_path=dummy_medical_dict_path,
        correction_threshold=0.8 # Higher threshold for auto-correction
    )

    print("\n--- English Tests ---")
    text_en_1 = "I have a hedache and my throaght hurts."
    corrected_en_1, corrections_en_1 = checker.correct_text(text_en_1, "en")
    print(f"Original: '{text_en_1}'")
    print(f"Corrected: '{corrected_en_1}'")
    print(f"Corrections: {corrections_en_1}")
    assert "headache" in corrected_en_1 and "throat" in corrected_en_1

    text_en_2 = "My blood presure is high, is it Hypertnsion?"
    corrected_en_2, corrections_en_2 = checker.correct_text(text_en_2, "en")
    print(f"Original: '{text_en_2}'")
    print(f"Corrected: '{corrected_en_2}'")
    print(f"Corrections: {corrections_en_2}")
    # Hypertension should not be corrected as it's in medical dict, 'presure' should be
    assert "pressure" in corrected_en_2 and "Hypertension" in corrected_en_2

    text_en_3 = "Can I take Aspiring for my paain?"
    corrected_en_3, corrections_en_3 = checker.correct_text(text_en_3, "en")
    print(f"Original: '{text_en_3}'")
    print(f"Corrected: '{corrected_en_3}'")
    print(f"Corrections: {corrections_en_3}")
    assert "Aspirin" in corrected_en_3 and "pain" in corrected_en_3

    text_en_4_low_conf = "I have a rare deease."
    corrected_en_4, corrections_en_4 = checker.correct_text(text_en_4_low_conf, "en")
    print(f"Original: '{text_en_4_low_conf}'")
    print(f"Corrected: '{corrected_en_4}'")
    print(f"Corrections: {corrections_en_4}")
    # 'deease' might be corrected to 'disease' or 'decreased' with lower confidence.
    # Depending on `correction_threshold`, it might be corrected or suggested.

    print("\n--- Spanish Tests ---")
    text_es_1 = "Tengo dolr de cabza."
    corrected_es_1, corrections_es_1 = checker.correct_text(text_es_1, "es")
    print(f"Original: '{text_es_1}'")
    print(f"Corrected: '{corrected_es_1}'")
    print(f"Corrections: {corrections_es_1}")
    assert "dolor" in corrected_es_1 and "cabeza" in corrected_es_1

    text_es_2 = "Mi hija tiene diabeetes."
    corrected_es_2, corrections_es_2 = checker.correct_text(text_es_2, "es")
    print(f"Original: '{text_es_2}'")
    print(f"Corrected: '{corrected_es_2}'")
    print(f"Corrections: {corrections_es_2}")
    # 'diabeetes' should be corrected to 'diabetes' if the Spanish dictionary includes it
    # or if a medical term list in Spanish is provided. pyspellchecker's 'es' dict might not have it.

    print("\n--- Cleanup ---")
    os.remove(dummy_medical_dict_path)
    print(f"Removed dummy medical dictionary file: {dummy_medical_dict_path}")