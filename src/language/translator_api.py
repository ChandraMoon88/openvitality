import logging
from typing import Dict, Any, Optional
from functools import lru_cache

# Primary: googletrans (unofficial, free)
try:
    from googletrans import Translator
    GOOGLETRANS_AVAILABLE = True
except ImportError:
    GOOGLETRANS_AVAILABLE = False
    logging.warning("googletrans library not installed. Google Translate API will be unavailable.")

# Backup 1: Hugging Face NLLB-200 (model needs to be downloaded, requires transformers)
try:
    from transformers import pipeline
    HF_TRANSFORMERS_AVAILABLE = True
except ImportError:
    HF_TRANSFORMERS_AVAILABLE = False
    logging.warning("Hugging Face Transformers not installed. NLLB-200 translation will be unavailable.")

# Backup 2: LibreTranslate (self-hosted, requires requests)
try:
    import requests
    LIBRETRANSLATE_AVAILABLE = True
except ImportError:
    LIBRETRANSLATE_AVAILABLE = False
    logging.warning("requests library not installed. LibreTranslate API will be unavailable.")

logger = logging.getLogger(__name__)

class TranslationManager:
    """
    Universal translator that attempts to translate text using multiple backends.
    Prioritizes googletrans, then Hugging Face NLLB-200, then LibreTranslate.
    Includes caching for efficiency and a conceptual quality check.
    """
    def __init__(self, 
                 cache_size: int = 1000, 
                 libretranslate_url: str = "http://localhost:5000", 
                 hf_nllb_model_name: str = "facebook/nllb-200-distilled-600M"):
        
        self._translate_cached = lru_cache(maxsize=cache_size)(self._translate)
        
        self.google_translator = Translator() if GOOGLETRANS_AVAILABLE else None
        self.libretranslate_url = libretranslate_url
        
        self.hf_nllb_pipeline = None
        if HF_TRANSFORMERS_AVAILABLE:
            try:
                # NLLB-200 supports 200 languages. Example: "eng_Latn", "hin_Deva", "spa_Latn"
                # Requires a specific model, e.g., "facebook/nllb-200-distilled-600M" or "facebook/nllb-200-1.3B"
                self.hf_nllb_pipeline = pipeline("translation", model=hf_nllb_model_name, src_lang="eng_Latn", tgt_lang="hin_Deva") # Default languages
                logger.info(f"Hugging Face NLLB-200 pipeline '{hf_nllb_model_name}' loaded.")
            except Exception as e:
                logger.warning(f"Failed to load Hugging Face NLLB-200 model '{hf_nllb_model_name}': {e}. NLLB-200 translation disabled.")
                self.hf_nllb_pipeline = None

        logger.info(f"TranslationManager initialized. Backends available: GoogleTrans={bool(self.google_translator)}, NLLB={bool(self.hf_nllb_pipeline)}, LibreTranslate={LIBRETRANSLATE_AVAILABLE}")

    def translate(self, text: str, dest_lang: str, src_lang: str = "auto") -> Optional[str]:
        """
        Translates text from source language to destination language.
        Uses caching to avoid re-translation of identical text.
        """
        return self._translate_cached(text, dest_lang, src_lang)

    def _translate(self, text: str, dest_lang: str, src_lang: str = "auto") -> Optional[str]:
        """
        Internal translation method without caching. Tries multiple backends.
        """
        if not text:
            return ""
        
        # GoogleTrans (primary)
        if self.google_translator:
            try:
                result = self.google_translator.translate(text, dest=dest_lang, src=src_lang)
                if result and result.text:
                    logger.debug(f"Translated '{text}' from {src_lang} to {dest_lang} using GoogleTrans.")
                    return result.text
            except Exception as e:
                logger.warning(f"GoogleTrans failed for '{text}': {e}. Trying next backend.")

        # Hugging Face NLLB-200 (backup 1)
        if self.hf_nllb_pipeline:
            try:
                # NLLB-200 requires specific language codes (e.g., 'eng_Latn').
                # This would need a mapping from ISO 639-1 codes.
                # For simplicity in this example, we assume `src_lang` and `dest_lang` are HF-compatible
                # or a simple mapping function is used.
                hf_src_lang = self._map_iso_to_nllb(src_lang) if src_lang != "auto" else "eng_Latn" # Default source
                hf_dest_lang = self._map_iso_to_nllb(dest_lang)

                if hf_src_lang and hf_dest_lang:
                    # Update pipeline's source and target languages
                    self.hf_nllb_pipeline.tokenizer.src_lang = hf_src_lang
                    self.hf_nllb_pipeline.model.config.forced_bos_token_id = self.hf_nllb_pipeline.tokenizer.lang_code_to_id[hf_dest_lang]
                    
                    result = self.hf_nllb_pipeline(text)
                    if result and result[0] and result[0]['translation_text']:
                        logger.debug(f"Translated '{text}' from {src_lang} to {dest_lang} using NLLB-200.")
                        return result[0]['translation_text']
            except Exception as e:
                logger.warning(f"NLLB-200 translation failed for '{text}': {e}. Trying next backend.")


        # LibreTranslate (backup 2)
        if LIBRETRANSLATE_AVAILABLE:
            try:
                payload = {'q': text, 'source': src_lang, 'target': dest_lang}
                response = requests.post(f"{self.libretranslate_url}/translate", json=payload)
                response.raise_for_status() # Raise an exception for HTTP errors
                translation = response.json()['translatedText']
                logger.debug(f"Translated '{text}' from {src_lang} to {dest_lang} using LibreTranslate.")
                return translation
            except requests.exceptions.RequestException as e:
                logger.warning(f"LibreTranslate failed for '{text}': {e}.")
            except Exception as e:
                logger.warning(f"LibreTranslate encountered an unexpected error for '{text}': {e}.")

        logger.error(f"All translation backends failed for text: '{text}' (from {src_lang} to {dest_lang}).")
        return None

    def detect_language(self, text: str) -> Optional[str]:
        """
        Detects the language of the given text.
        Prioritizes googletrans.
        """
        if not text:
            return None
        
        if self.google_translator:
            try:
                result = self.google_translator.detect(text)
                if result and result.lang:
                    logger.debug(f"Detected language for '{text}' as {result.lang} with confidence {result.confidence} using GoogleTrans.")
                    return result.lang
            except Exception as e:
                logger.warning(f"GoogleTrans language detection failed for '{text}': {e}. No other detector configured.")
        
        logger.warning(f"No language detection backend available or all failed for '{text}'.")
        return None

    def _map_iso_to_nllb(self, iso_code: str) -> Optional[str]:
        """
        Maps standard ISO 639-1 language codes to NLLB-200 compatible codes.
        This is a partial mapping for common languages.
        """
        mapping = {
            "en": "eng_Latn",
            "hi": "hin_Deva", # Hindi (Devanagari script)
            "es": "spa_Latn",
            "fr": "fra_Latn",
            "de": "deu_Latn",
            "ar": "arb_Arab", # Arabic (Arabic script)
            "zh": "zho_Hans", # Chinese (Simplified)
            "ja": "jpn_Jpan",
            "ko": "kor_Hang",
            "ru": "rus_Cyrl",
            "pt": "por_Latn",
            "bn": "ben_Beng", # Bengali (Bengali script)
            "ta": "tam_Taml", # Tamil (Tamil script)
            "te": "tel_Telu", # Telugu (Telugu script)
            "mr": "mar_Deva", # Marathi (Devanagari script)
            # Add more as needed
        }
        return mapping.get(iso_code.lower())

    def quality_check(self, original_text: str, translated_text: str, src_lang: str, dest_lang: str) -> bool:
        """
        Conceptual quality check by back-translating and comparing.
        In a real system, this would use a more robust metric (e.g., BLEU score or semantic similarity).
        """
        logger.debug("Performing conceptual back-translation quality check...")
        back_translated = self.translate(translated_text, src_lang, dest_lang)
        
        if back_translated is None:
            logger.warning("Back-translation failed, cannot perform quality check.")
            return False
        
        # Very naive comparison: check for significant word overlap or semantic similarity.
        # For production, use libraries like sentence-transformers for embedding similarity.
        if original_text.lower() == back_translated.lower():
            logger.debug("Quality check passed: Back-translated text matches original (exact).")
            return True
        
        # Simple word overlap check
        original_words = set(original_text.lower().split())
        back_translated_words = set(back_translated.lower().split())
        
        common_words = original_words.intersection(back_translated_words)
        overlap_ratio = len(common_words) / len(original_words) if original_words else 0
        
        if overlap_ratio > 0.6: # Arbitrary threshold
            logger.debug(f"Quality check passed: Back-translated text has {overlap_ratio:.2f} word overlap with original.")
            return True
        
        logger.warning(f"Quality check failed for original: '{original_text}', back-translated: '{back_translated}' (Overlap: {overlap_ratio:.2f}).")
        return False


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Ensure LibreTranslate server is running for that part of the example
    # docker run -it --rm -p 5000:5000 libretranslate/libretranslate

    translator_manager = TranslationManager(libretranslate_url="http://localhost:5000")

    print("\n--- Language Detection ---")
    text_en = "Hello, how are you?"
    text_hi = "नमस्ते, आप कैसे हैं?"
    text_es = "¿Hola como estas?"

    print(f"'{text_en}' -> Detected: {translator_manager.detect_language(text_en)}")
    print(f"'{text_hi}' -> Detected: {translator_manager.detect_language(text_hi)}")
    print(f"'{text_es}' -> Detected: {translator_manager.detect_language(text_es)}")

    print("\n--- English to Hindi ---")
    original_en_text = "I have a severe headache and fever for three days. I need to book an appointment."
    translated_hi = translator_manager.translate(original_en_text, dest_lang="hi", src_lang="en")
    print(f"EN: '{original_en_text}' -> HI: '{translated_hi}'")
    if translated_hi:
        translator_manager.quality_check(original_en_text, translated_hi, "en", "hi")


    print("\n--- Hindi to English ---")
    original_hi_text = "मुझे तीन दिन से तेज सरदर्द और बुखार है। मुझे एक अपॉइंटमेंट बुक करना है।"
    translated_en = translator_manager.translate(original_hi_text, dest_lang="en", src_lang="hi")
    print(f"HI: '{original_hi_text}' -> EN: '{translated_en}'")
    if translated_en:
        translator_manager.quality_check(original_hi_text, translated_en, "hi", "en")


    print("\n--- English to Spanish ---")
    original_en_text_2 = "My child has a cough."
    translated_es = translator_manager.translate(original_en_text_2, dest_lang="es") # src_lang="auto"
    print(f"EN: '{original_en_text_2}' -> ES: '{translated_es}'")
    if translated_es:
        translator_manager.quality_check(original_en_text_2, translated_es, "en", "es")

    print("\n--- Cached Translation ---")
    translated_hi_cached = translator_manager.translate(original_en_text, dest_lang="hi", src_lang="en")
    print(f"Cached HI: '{translated_hi_cached}' (Should be fast)")
    # Check if cached result is the same
    assert translated_hi == translated_hi_cached
