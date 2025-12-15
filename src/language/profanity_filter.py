# Purpose: Censor inappropriate language
# What to add:
# Rule-based filtering: List of known bad words
# Regex patterns: Catch variations (f**k, sh!t)
# Character substitution: Replace with *, #, or medical-safe phrases
# Contextual filtering: Be careful not to censor medical terms (e.g., "analgesic")
# Language-specific lists: Profanity differs by language
# Integration with logging: Flag flagged content for human review (audit trail)

import re
import logging
from typing import List, Dict, Optional, Tuple
import time

logger = logging.getLogger(__name__)

class ProfanityFilter:
    """
    Filters and censors profanity from text based on a list of bad words
    and regex patterns, with considerations for medical context and multilingual support.
    """
    def __init__(self,
                 censor_char: str = "*",
                 medical_terms: Optional[List[str]] = None,
                 lang_specific_lists: Optional[Dict[str, List[str]]] = None):
        self.censor_char = censor_char
        self.medical_terms = set(term.lower() for term in medical_terms) if medical_terms else set()

        # Default profanity list (English)
        self.profanity_list: Dict[str, List[str]] = {
            "en": [
                r"\bfuck\b", r"\bfuk\b", r"\bfck\b", r"\bsht\b", r"\bshit\b", r"\basshole\b",
                r"\bbitch\b", r"\bdick\b", r"\bcunt\b", r"\bdamn\b", r"\bhell\b",
                r"\bass\b", r"\bsucker\b", r"\btard\b", r"\bretard\b",
                r"\bnigga\b", r"\bnigger\b", r"\bfaggot\b", r"\bdyke\b",
                r"\bpussy\b", r"\bcock\b", r"\bwhor(e|ing)\b", r"\bslut\b",
                r"\bchink\b", r"\bgook\b", r"\bspic\b", r"\bkike\b", r"\bwetback\b",
                r"\bcracker\b", r"\bgay\b", r"\blesbian\b" # Contextual: gay/lesbian can be offensive but also descriptive
            ],
            # Add placeholders for other languages
            "hi": [r"\bchutiya\b", r"\b Bhosdi\b", r"\b madarchod\b", r"\bhijo de puta\b"], # Example for Hindi
            "es": [r"\bjoder\b", r"\bputa\b", r"\bmaricón\b"] # Example for Spanish
        }

        # Merge with provided language-specific lists
        if lang_specific_lists:
            for lang, words in lang_specific_lists.items():
                self.profanity_list.setdefault(lang, []).extend(words)

        # Compile regex patterns for faster matching
        self.compiled_patterns: Dict[str, List[re.Pattern]] = {}
        for lang, words in self.profanity_list.items():
            self.compiled_patterns[lang] = [re.compile(word, re.IGNORECASE) for word in words]

        logger.info("ProfanityFilter initialized.")
        logger.debug(f"Medical terms to exclude: {self.medical_terms}")
        for lang, patterns in self.compiled_patterns.items():
            logger.debug(f"Loaded {len(patterns)} profanity patterns for {lang}.")

    def _censor_match(self, match: re.Match) -> str:
        """Helper to replace matched profanity with censor characters."""
        return self.censor_char * len(match.group(0))

    def filter_text(self, text: str, lang: str = "en") -> Tuple[str, bool, List[str]]:
        """
        Filters profanity from the input text.

        :param text: The input string to filter.
        :param lang: The language code to use for profanity list (e.g., "en", "hi").
        :return: A tuple containing the filtered text, a boolean indicating if profanity was found,
                 and a list of detected profanity words (uncensored).
        """
        filtered_text = text
        profanity_found = False
        detected_words: List[str] = []
        lang_patterns = self.compiled_patterns.get(lang.lower(), [])

        for pattern in lang_patterns:
            # Find all matches
            for match in pattern.finditer(filtered_text):
                matched_word = match.group(0)
                # Check if the matched word is a medical term (case-insensitive)
                if matched_word.lower() in self.medical_terms:
                    logger.debug(f"Skipping potential profanity '{matched_word}' as it's a known medical term.")
                    continue

                profanity_found = True
                detected_words.append(matched_word)
                # Replace the matched word with censor characters
                filtered_text = filtered_text[:match.start()] + \
                                self._censor_match(match) + \
                                filtered_text[match.end():]
                logger.info(f"Censored '{matched_word}' in text.")

        if profanity_found:
            logger.warning(f"Profanity detected and filtered in text (lang: {lang}). Original: '{text}', Filtered: '{filtered_text}'")
            # Flag for audit
            self._log_profanity_audit(text, filtered_text, detected_words, lang)

        return filtered_text, profanity_found, detected_words

    def _log_profanity_audit(self, original_text: str, filtered_text: str, detected_words: List[str], lang: str):
        """
        Logs detected profanity for audit trail and potential human review.
        """
        audit_entry = {
            "timestamp": time.time(),
            "original_text": original_text,
            "filtered_text": filtered_text,
            "detected_words": detected_words,
            "language": lang,
            "action": "censored_by_filter"
        }
        # In a real system, this would write to a dedicated audit log file or database
        logger.critical(f"PROFANITY_AUDIT: {audit_entry}")
        # Optionally, trigger an alert for extreme profanity

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    medical_terms_example = ["anal", "feces", "penis", "vagina", "breast", "sex", "pussy willow"] # 'pussy willow' to test context
    filter_en = ProfanityFilter(censor_char="#", medical_terms=medical_terms_example)
    filter_hi = ProfanityFilter(censor_char="*", lang_specific_lists={"hi": [r"\bbakchod\b", r"\bgaandu\b"]})
    filter_es = ProfanityFilter(censor_char="$", lang_specific_lists={"es": [r"\bcoño\b", r"\bimbécil\b"]})

    print("\n--- English Tests ---")
    text1_en = "What the fuck are you saying? That's bullshit!"
    filtered1_en, found1_en, words1_en = filter_en.filter_text(text1_en, "en")
    print(f"Original: '{text1_en}'\nFiltered: '{filtered1_en}' (Found: {found1_en}, Words: {words1_en})")
    assert found1_en is True
    assert filtered1_en == "What the #### are you saying? That's ########!"

    text2_en = "The patient reported anal pain."
    filtered2_en, found2_en, words2_en = filter_en.filter_text(text2_en, "en")
    print(f"Original: '{text2_en}'\nFiltered: '{filtered2_en}' (Found: {found2_en}, Words: {words2_en})")
    assert found2_en is False # "anal" is a medical term

    text3_en = "Look at that beautiful pussy willow tree."
    filtered3_en, found3_en, words3_en = filter_en.filter_text(text3_en, "en")
    print(f"Original: '{text3_en}'\nFiltered: '{filtered3_en}' (Found: {found3_en}, Words: {words3_en})")
    assert found3_en is False # "pussy willow" is excluded

    text4_en = "You are an absolute retard!"
    filtered4_en, found4_en, words4_en = filter_en.filter_text(text4_en, "en")
    print(f"Original: '{text4_en}'\nFiltered: '{filtered4_en}' (Found: {found4_en}, Words: {words4_en})")
    assert found4_en is True
    assert filtered4_en == "You are an absolute ######!"

    print("\n--- Hindi Tests ---")
    text1_hi = "तू एक नंबर का bakchod है।"
    filtered1_hi, found1_hi, words1_hi = filter_hi.filter_text(text1_hi, "hi")
    print(f"Original: '{text1_hi}'\nFiltered: '{filtered1_hi}' (Found: {found1_hi}, Words: {words1_hi})")
    assert found1_hi is True
    assert filtered1_hi == "तू एक नंबर का ****** है."

    print("\n--- Spanish Tests ---")
    text1_es = "¡Coño, qué calor hace!"
    filtered1_es, found1_es, words1_es = filter_es.filter_text(text1_es, "es")
    print(f"Original: '{text1_es}'\nFiltered: '{filtered1_es}' (Found: {found1_es}, Words: {words1_es})")
    assert found1_es is True
    assert filtered1_es == "¡$coño$, qué calor hace!" # Note: regex needs to be more precise for punctuation

    print("\n--- No Profanity ---")
    text_clean = "Hello, how are you today?"
    filtered_clean, found_clean, words_clean = filter_en.filter_text(text_clean, "en")
    print(f"Original: '{text_clean}'\nFiltered: '{filtered_clean}' (Found: {found_clean}, Words: {words_clean})")
    assert found_clean is False