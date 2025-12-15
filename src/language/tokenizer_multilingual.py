import re
import logging
from typing import List

logger = logging.getLogger(__name__)

# Placeholder for indic_nlp_library, assuming it's installed and configured
# from indicnlp.tokenize import indic_detokenize, indic_tokenize

class MultilingualTokenizer:
    """
    Splits text into words (tokens) correctly, supporting multiple languages.
    Handles language-specific tokenization rules, punctuation, and contractions.
    """
    def __init__(self):
        # Basic English contractions for expansion
        self.contractions_map = {
            "don't": "do not", "can't": "cannot", "won't": "will not", "i'm": "i am",
            "you're": "you are", "it's": "it is", "we're": "we are", "they're": "they are",
            "i've": "i have", "we've": "we have", "they've": "they have", "i'd": "i would",
            "you'd": "you would", "it'd": "it would", "we'd": "we would", "they'd": "they would",
            "i'll": "i will", "you'll": "you will", "it'll": "it will", "we'll": "we will",
            "they'll": "they will", "isn't": "is not", "aren't": "are not", "wasn't": "was not",
            "weren't": "were not", "hasn't": "has not", "haven't": "have not", "hadn't": "had not",
            "doesn't": "does not", "don't": "do not", "didn't": "did not", "wouldn't": "would not",
            "shouldn't": "should not", "couldn't": "could not", "mustn't": "must not",
        }
        logger.info("MultilingualTokenizer initialized.")

    def tokenize(self, text: str, lang_code: str = "en", keep_punctuation: bool = False, expand_contractions: bool = False) -> List[str]:
        """
        Tokenizes the input text based on the specified language.

        Args:
            text (str): The input string to tokenize.
            lang_code (str): ISO 639-1 language code (e.g., "en", "hi", "es", "zh").
            keep_punctuation (bool): If True, punctuation marks are kept as separate tokens.
                                     If False, punctuation is removed.
            expand_contractions (bool): If True, contractions like "don't" are expanded to "do not".

        Returns:
            List[str]: A list of tokens.
        """
        if not text:
            return []

        processed_text = text.lower() if lang_code not in ["zh", "ja", "ko"] else text

        if expand_contractions:
            processed_text = self._expand_contractions(processed_text)

        tokens: List[str] = []
        
        # Define a safer punctuation removal regex that includes the Devanagari danda
        # and standard ASCII punctuation.
        if not keep_punctuation:
            import string
            # Escape all punctuation characters for use in regex, and add other common ones.
            punctuation_to_remove = re.escape(string.punctuation) + "।"
            processed_text = re.sub(f'[{punctuation_to_remove}]', '', processed_text)

        if lang_code in ["zh", "ja", "ko"]:
            # Character-level tokenization for CJK languages
            logger.debug(f"Using character-level tokenization for CJK language '{lang_code}'.")
            # If we didn't keep punctuation, it's already removed.
            # If we did, we need to handle it. For CJK, it's often better to just list them.
            if not keep_punctuation:
                 processed_text = re.sub(r'[︰．。，、？！（）【】「」『』]', '', processed_text)
            tokens = list(processed_text)
        else:
            # Whitespace-based tokenization for most other languages
            tokens = processed_text.split()
        
        # Filter out empty strings that might result from splitting/regex
        return [token for token in tokens if token]

    def _expand_contractions(self, text: str) -> str:
        """Expands common English contractions."""
        def replace_contraction(match):
            return self.contractions_map.get(match.group(0), match.group(0))
        
        # Use regex to find contractions and replace them
        # re.I for case-insensitive, but we already lowercased it.
        # re.A (ASCII-only matching) or re.U (Unicode) might be relevant based on string type.
        contraction_pattern = re.compile(r'\b(?:' + '|'.join(re.escape(c) for c in self.contractions_map.keys()) + r')\b')
        return contraction_pattern.sub(replace_contraction, text)


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    tokenizer = MultilingualTokenizer()

    print("\n--- English ---")
    text_en = "Don't worry, I can't believe it! It's 10.5 degrees Celsius."
    print(f"Original: {text_en}")
    print(f"Tokens (default): {tokenizer.tokenize(text_en)}")
    print(f"Tokens (keep punc): {tokenizer.tokenize(text_en, keep_punctuation=True)}")
    print(f"Tokens (expand): {tokenizer.tokenize(text_en, expand_contractions=True)}")
    print(f"Tokens (expand, keep punc): {tokenizer.tokenize(text_en, expand_contractions=True, keep_punctuation=True)}")

    print("\n--- Spanish ---")
    text_es = "¿Cómo estás? No sé si puedo ir."
    print(f"Original: {text_es}")
    print(f"Tokens (default): {tokenizer.tokenize(text_es, lang_code='es')}")
    print(f"Tokens (keep punc): {tokenizer.tokenize(text_es, lang_code='es', keep_punctuation=True)}")

    print("\n--- Hindi (placeholder) ---")
    text_hi = "मेरा नाम चाँद है। मैं डॉक्टर हूँ।" # My name is Chand. I am a doctor.
    print(f"Original: {text_hi}")
    print(f"Tokens (default): {tokenizer.tokenize(text_hi, lang_code='hi')}")
    print(f"Tokens (keep punc): {tokenizer.tokenize(text_hi, lang_code='hi', keep_punctuation=True)}")

    print("\n--- Chinese (character-level) ---")
    text_zh = "你好，世界！这是一个测试。" # Hello, world! This is a test.
    print(f"Original: {text_zh}")
    print(f"Tokens (default): {tokenizer.tokenize(text_zh, lang_code='zh')}")
    print(f"Tokens (keep punc): {tokenizer.tokenize(text_zh, lang_code='zh', keep_punctuation=True)}")

    print("\n--- Arabic (placeholder) ---")
    text_ar = "كيف حالك؟ هذا نص عربي." # How are you? This is Arabic text.
    print(f"Original: {text_ar}")
    print(f"Tokens (default): {tokenizer.tokenize(text_ar, lang_code='ar')}")
    print(f"Tokens (keep punc): {tokenizer.tokenize(text_ar, lang_code='ar', keep_punctuation=True)}")

    print("\n--- Edge Case: Empty String ---")
    print(f"Tokens for '': {tokenizer.tokenize('')}")
