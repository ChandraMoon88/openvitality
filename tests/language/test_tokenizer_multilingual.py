
import sys
sys.path.append('.')

import unittest
from src.language.tokenizer_multilingual import MultilingualTokenizer

class TestMultilingualTokenizer(unittest.TestCase):

    def setUp(self):
        """Set up a new MultilingualTokenizer for each test."""
        self.tokenizer = MultilingualTokenizer()

    def test_tokenize_english_simple(self):
        """Test basic whitespace tokenization for English."""
        text = "Hello world, this is a test."
        expected = ["hello", "world", "this", "is", "a", "test"]
        result = self.tokenizer.tokenize(text, lang_code="en")
        self.assertEqual(result, expected)

    def test_tokenize_english_expand_contractions(self):
        """Test expansion of English contractions."""
        text = "I'm happy, but I can't come."
        expected_expanded = ["i", "am", "happy", "but", "i", "cannot", "come"]
        result = self.tokenizer.tokenize(text, lang_code="en", expand_contractions=True)
        self.assertEqual(result, expected_expanded)

    def test_tokenize_keep_punctuation(self):
        """Test keeping punctuation (note: implementation keeps it attached)."""
        text = "Hello, world!"
        # The current implementation's regex for removal is [^\w\s]. 
        # When keep_punctuation is true, this regex is skipped, but splitting is by whitespace.
        # So punctuation stays attached.
        expected = ["hello,", "world!"]
        result = self.tokenizer.tokenize(text, lang_code="en", keep_punctuation=True)
        self.assertEqual(result, expected)

    def test_tokenize_cjk_character_level(self):
        """Test character-level tokenization for CJK languages."""
        text_zh = "你好世界" # Hello world
        expected_zh = ["你", "好", "世", "界"]
        result_zh = self.tokenizer.tokenize(text_zh, lang_code="zh")
        self.assertEqual(result_zh, expected_zh)
        
        text_ja = "こんにちは" # Hello
        expected_ja = ["こ", "ん", "に", "ち", "は"]
        result_ja = self.tokenizer.tokenize(text_ja, lang_code="ja")
        self.assertEqual(result_ja, expected_ja)
        
    def test_tokenize_cjk_with_punctuation(self):
        """Test character-level tokenization for CJK with punctuation removal."""
        text_zh = "你好，世界！"
        expected_zh = ["你", "好", "世", "界"]
        result_zh = self.tokenizer.tokenize(text_zh, lang_code="zh", keep_punctuation=False)
        self.assertEqual(result_zh, expected_zh)

    def test_tokenize_indic_fallback(self):
        """Test fallback to whitespace tokenization for Indic languages."""
        text_hi = "मेरा नाम चाँद है"
        expected_hi = ["मेरा", "नाम", "चाँद", "है"]
        result_hi = self.tokenizer.tokenize(text_hi, lang_code="hi")
        self.assertEqual(result_hi, expected_hi)

    def test_tokenize_unsupported_language_fallback(self):
        """Test fallback to whitespace for an unsupported language."""
        text = "This is a test"
        expected = ["this", "is", "a", "test"]
        result = self.tokenizer.tokenize(text, lang_code="xx") # 'xx' is an unsupported code
        self.assertEqual(result, expected)

    def test_tokenize_empty_string(self):
        """Test that an empty string returns an empty list."""
        self.assertEqual(self.tokenizer.tokenize(""), [])
        self.assertEqual(self.tokenizer.tokenize("   "), [])


if __name__ == '__main__':
    unittest.main()
