import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.language.translator_api import TranslationManager

class TestTranslationManager(unittest.TestCase):

    @patch('src.language.translator_api.Translator')
    @patch('src.language.translator_api.GOOGLETRANS_AVAILABLE', True)
    def test_googletrans_success(self, MockTranslator):
        """Test translation succeeds using the primary googletrans backend."""
        # Setup Mock
        mock_translator_instance = MockTranslator.return_value
        mock_result = MagicMock()
        mock_result.text = "hello world"
        mock_translator_instance.translate.return_value = mock_result

        # Init Manager
        manager = TranslationManager()
        
        # Test
        result = manager.translate("hola mundo", dest_lang="en", src_lang="es")
        
        # Verify
        self.assertEqual(result, "hello world")
        mock_translator_instance.translate.assert_called_once_with("hola mundo", dest="en", src="es")

    @patch('src.language.translator_api.pipeline')
    @patch('src.language.translator_api.Translator')
    @patch('src.language.translator_api.HF_TRANSFORMERS_AVAILABLE', True)
    @patch('src.language.translator_api.GOOGLETRANS_AVAILABLE', True)
    def test_huggingface_fallback(self, MockTranslator, MockPipeline):
        """Test fallback to Hugging Face NLLB when googletrans fails."""
        # Setup GoogleTrans to fail
        mock_translator_instance = MockTranslator.return_value
        mock_translator_instance.translate.side_effect = Exception("Google API Error")

        # Setup Hugging Face to succeed
        # pipeline returns a callable (the model pipeline itself)
        mock_pipeline_instance = MagicMock()
        MockPipeline.return_value = mock_pipeline_instance
        # The pipeline instance is called with text: pipeline("text") -> [{'translation_text': '...'}]
        mock_pipeline_instance.return_value = [{'translation_text': 'hello world'}]
        
        # Mock tokenizer/config access needed for language code mapping logic in _translate
        mock_pipeline_instance.tokenizer.lang_code_to_id = {"eng_Latn": 1, "spa_Latn": 2}
        mock_pipeline_instance.model.config.forced_bos_token_id = None

        # Init Manager (this calls pipeline(...) so MockPipeline must handle it)
        manager = TranslationManager(hf_nllb_model_name="dummy_model")

        # Test
        result = manager.translate("hola mundo", dest_lang="en", src_lang="es")

        # Verify
        self.assertEqual(result, "hello world")
        mock_translator_instance.translate.assert_called() # Google was tried
        mock_pipeline_instance.assert_called() # HF was used

    @patch('src.language.translator_api.requests')
    @patch('src.language.translator_api.pipeline')
    @patch('src.language.translator_api.Translator')
    @patch('src.language.translator_api.LIBRETRANSLATE_AVAILABLE', True)
    @patch('src.language.translator_api.HF_TRANSFORMERS_AVAILABLE', True)
    @patch('src.language.translator_api.GOOGLETRANS_AVAILABLE', True)
    def test_libretranslate_fallback(self, MockTranslator, MockPipeline, MockRequests):
        """Test fallback to LibreTranslate when other backends fail."""
        # FIX: Ensure RequestException is a valid exception class so 'except' blocks work
        MockRequests.exceptions.RequestException = Exception

        # Setup GoogleTrans to fail
        MockTranslator.return_value.translate.side_effect = Exception("Google Fail")
        
        # Setup HF to fail.
        mock_pipeline_instance = MagicMock()
        MockPipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.side_effect = Exception("HF Fail") 
        mock_pipeline_instance.tokenizer = MagicMock()
        
        # Setup LibreTranslate to succeed
        mock_response = MagicMock()
        mock_response.json.return_value = {'translatedText': 'hello world'}
        MockRequests.post.return_value = mock_response

        # Init
        manager = TranslationManager()

        # Test
        result = manager.translate("hola mundo", dest_lang="en", src_lang="es")

        # Verify
        self.assertEqual(result, "hello world")
        MockRequests.post.assert_called_once()

    @patch('src.language.translator_api.requests')
    @patch('src.language.translator_api.pipeline')
    @patch('src.language.translator_api.Translator')
    @patch('src.language.translator_api.LIBRETRANSLATE_AVAILABLE', True)
    @patch('src.language.translator_api.HF_TRANSFORMERS_AVAILABLE', True)
    @patch('src.language.translator_api.GOOGLETRANS_AVAILABLE', True)
    def test_all_backends_fail(self, MockTranslator, MockPipeline, MockRequests):
        """Test that None is returned if all backends fail."""
        # FIX: Ensure RequestException is a valid exception class so 'except' blocks work
        MockRequests.exceptions.RequestException = Exception
        
        # All fail
        MockTranslator.return_value.translate.side_effect = Exception("Google Fail")
        
        mock_pipeline_instance = MagicMock()
        MockPipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.side_effect = Exception("HF Fail")
        mock_pipeline_instance.tokenizer = MagicMock()
        
        MockRequests.post.side_effect = Exception("Network Fail")

        manager = TranslationManager()
        result = manager.translate("fail text", dest_lang="en")

        self.assertIsNone(result)

    @patch('src.language.translator_api.Translator')
    @patch('src.language.translator_api.GOOGLETRANS_AVAILABLE', True)
    def test_caching(self, MockTranslator):
        """Test that translation results are cached."""
        # Setup Success
        mock_instance = MockTranslator.return_value
        mock_res = MagicMock()
        mock_res.text = "cached"
        mock_instance.translate.return_value = mock_res

        manager = TranslationManager()
        
        # First call
        res1 = manager.translate("test", "en")
        self.assertEqual(res1, "cached")
        
        # Second call
        res2 = manager.translate("test", "en")
        self.assertEqual(res2, "cached")

        # Verify google translate was only called once
        mock_instance.translate.assert_called_once()

if __name__ == '__main__':
    unittest.main()