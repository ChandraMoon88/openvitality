import os
import time
import logging
from typing import Dict, Any, List, Generator, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests # Import requests here as it's used in retry_if_exception_type

# Hugging Face Transformers library
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline # type: ignore
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    logging.warning("Hugging Face Transformers not found. Local model inference will be unavailable.")
    _TRANSFORMERS_AVAILABLE = False

# Hugging Face Inference API client
try:
    from huggingface_hub import InferenceClient, HfHub
    _HF_HUB_AVAILABLE = True
except ImportError as e:
    logging.warning(f"huggingface_hub not found. Inference API will be unavailable. Error: {e}")
    _HF_HUB_AVAILABLE = False

from .llm_interface import LLMInterface, LLMConfig, LLMAPIError, LLMRateLimitError, LLMResponse
from .llm_factory import LLMFactory # To register itself

logger = logging.getLogger(__name__)

class HuggingFaceProvider(LLMInterface):
    """
    Hugging Face LLM integration adhering to the LLMInterface.
    Supports local model inference via `transformers` library and
    Hugging Face Inference API via `huggingface_hub`.
    """
    def __init__(self, model_id: str, use_inference_api: bool = False, api_token: Optional[str] = None, **kwargs):
        self.model_id = model_id
        self.use_inference_api = use_inference_api
        self.api_token = api_token if api_token else os.getenv("HF_API_TOKEN")
        self.tokenizer = None
        self.pipeline = None
        self.inference_client = None

        # print(f"[DEBUG] HuggingFaceProvider.__init__ - use_inference_api: {self.use_inference_api}")
        # print(f"[DEBUG] HuggingFaceProvider.__init__ - _HF_HUB_AVAILABLE (top-level): {_HF_HUB_AVAILABLE}")
        # print(f"[DEBUG] HuggingFaceProvider.__init__ - _TRANSFORMERS_AVAILABLE: {_TRANSFORMERS_AVAILABLE}")

        if self.use_inference_api:
            if not self.api_token:
                logger.warning("HF_API_TOKEN not provided. Inference API might be rate-limited or restricted.")
            self.inference_client = InferenceClient(token=self.api_token)
            logger.info(f"HuggingFaceProvider initialized with Inference API for model: {self.model_id}")
        else:
            if not _TRANSFORMERS_AVAILABLE:
                raise ImportError("transformers library is required for local model inference.")
            try:
                # Load tokenizer and model for local inference
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
                self.pipeline = pipeline(
                    "text-generation",
                    model=self.model_id,
                    tokenizer=self.tokenizer,
                    device=0 if os.environ.get("USE_CUDA", "false").lower() == "true" else -1, # Use GPU if available and configured
                    **kwargs
                )
                logger.info(f"HuggingFaceProvider initialized with local model: {self.model_id}")
            except Exception as e:
                logger.error(f"Failed to load local Hugging Face model '{self.model_id}': {e}. Falling back to Inference API (if possible).")
                # Try to fall back to Inference API if local loading fails and client available
                if _HF_HUB_AVAILABLE and self.api_token:
                    logger.info("Attempting to use Hugging Face Inference API as fallback.")
                    self.use_inference_api = True
                    self.inference_client = InferenceClient(token=self.api_token)
                else:
                    raise ValueError(f"Failed to initialize HuggingFaceProvider. Neither local model nor Inference API could be set up: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10),
           retry=retry_if_exception_type((requests.exceptions.RequestException, ))
           if _HF_HUB_AVAILABLE else None) # Only retry if HF_HUB is available
    def _run_inference(self, prompt: str, config: LLMConfig, stream: bool = False) -> Any:
        """Internal method to run inference using either local pipeline or Inference API."""
        if self.use_inference_api and self.inference_client:
            try:
                # Inference API does not have a direct chat endpoint like OpenAI/Gemini
                # We format messages into a single prompt.
                # It also often doesn't expose all config options directly.
                params = {
                    "temperature": config.temperature,
                    "max_new_tokens": config.max_tokens, # Inference API uses max_new_tokens
                    "top_p": config.top_p,
                    "return_full_text": False, # Only return generated part
                    "do_sample": True if config.temperature > 0 else False,
                    # stop_sequences are typically not directly supported via InferenceClient generate
                    # Needs more advanced handling or post-processing.
                }

                if stream:
                    return self.inference_client.text_generation(prompt, **params, stream=True)
                else:
                    return self.inference_client.text_generation(prompt, **params)
            except Exception as e:
                logger.error(f"Hugging Face Inference API error: {e}")
                # Re-raise as our custom error type
                if "rate limit" in str(e).lower():
                    raise LLMRateLimitError(f"Hugging Face Inference API rate limit exceeded: {e}") from e
                raise LLMAPIError(f"Hugging Face Inference API error: {e}") from e
        elif self.pipeline:
            # Local model inference via transformers pipeline
            pipeline_kwargs = {
                "max_new_tokens": config.max_tokens,
                "do_sample": True if config.temperature > 0 else False,
                "temperature": config.temperature,
                "top_p": config.top_p,
                "return_full_text": False,
                # stop_sequences require custom generation loop with pipeline or using model.generate directly
                # For simplicity, we'll omit stop_sequences for now.
            }
            if stream:
                # Transformers pipeline stream is not directly supported for simple text-generation
                # Would require manual text generation loop with model.generate(..., stream=True)
                logger.warning("Local pipeline streaming is not directly supported for text-generation pipeline. Returning full response.")
                response = self.pipeline(prompt, **pipeline_kwargs)
                yield response[0]['generated_text'] # Yield full text as single chunk
            else:
                return self.pipeline(prompt, **pipeline_kwargs)
        else:
            raise ValueError("HuggingFaceProvider not initialized correctly (no client or pipeline).")

    def generate_text(self, prompt: str, config: LLMConfig) -> LLMResponse:
        model_name = config.model if config.model else self.model_id
        try:
            response = self._run_inference(prompt, config, stream=False)
            
            generated_text = ""
            if self.use_inference_api:
                if isinstance(response, str): # InferenceClient returns string directly for non-stream
                    generated_text = response
                elif isinstance(response, dict) and 'generated_text' in response: # Some APIs return dict
                    generated_text = response['generated_text']
            elif self.pipeline:
                generated_text = response[0]['generated_text'] # Pipeline returns list of dicts

            # Token counting for Hugging Face models using their tokenizer
            prompt_tokens = self.count_tokens(text=prompt, model_name=model_name)
            completion_tokens = self.count_tokens(text=generated_text, model_name=model_name)

            return LLMResponse(
                generated_text=generated_text,
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                raw_response={"response": response},
                finish_reason="STOP" # Need to parse this from raw response if available
            )
        except (LLMAPIError, LLMRateLimitError) as e:
            raise
        except Exception as e:
            raise LLMAPIError(f"An unexpected error occurred with Hugging Face: {e}") from e

    def generate_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> LLMResponse:
        # Hugging Face models generally don't have a standardized chat API like OpenAI/Gemini
        # We need to manually format messages into a single prompt.
        # This is a common pattern for "instruct" models or conversational models.
        formatted_prompt = ""
        for msg in messages:
            if msg["role"] == "user":
                formatted_prompt += f"User: {msg['content']}\n"
            elif msg["role"] == "assistant":
                formatted_prompt += f"Assistant: {msg['content']}\n"
            elif msg["role"] == "system":
                formatted_prompt += f"System: {msg['content']}\n"
        formatted_prompt += "Assistant:" # Indicate the assistant should respond next

        return self.generate_text(formatted_prompt, config) # Delegate to text generation

    def stream_text(self, prompt: str, config: LLMConfig) -> Generator[str, None, None]:
        model_name = config.model if config.model else self.model_id
        try:
            stream_gen = self._run_inference(prompt, config, stream=True)
            if self.use_inference_api:
                for chunk in stream_gen:
                    if chunk.token and chunk.token.text:
                        yield chunk.token.text
            elif self.pipeline:
                # If local pipeline cannot stream, _run_inference yielded full text as one chunk
                for chunk_text in stream_gen:
                    yield chunk_text
        except (LLMAPIError, LLMRateLimitError) as e:
            logger.error(f"Hugging Face API error during stream_text: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during Hugging Face stream_text: {e}")
            raise

    def stream_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Generator[str, None, None]:
        # Same as generate_chat_response, format into a single prompt and stream as text
        formatted_prompt = ""
        for msg in messages:
            if msg["role"] == "user":
                formatted_prompt += f"User: {msg['content']}\n"
            elif msg["role"] == "assistant":
                formatted_prompt += f"Assistant: {msg['content']}\n"
            elif msg["role"] == "system":
                formatted_prompt += f"System: {msg['content']}\n"
        formatted_prompt += "Assistant:"

        return self.stream_text(formatted_prompt, config)

    def count_tokens(self, text: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None, model_name: Optional[str] = None) -> int:
        model_name = model_name if model_name else self.model_id
        # Use the tokenizer of the loaded model for accurate token counting
        if self.tokenizer:
            if text:
                return len(self.tokenizer.encode(text, add_special_tokens=True))
            elif messages:
                # For messages, convert to a single string as would be fed to the model
                formatted_text = ""
                for msg in messages:
                    if msg["role"] == "user":
                        formatted_text += f"User: {msg['content']}\n"
                    elif msg["role"] == "assistant":
                        formatted_text += f"Assistant: {msg['content']}\n"
                    elif msg["role"] == "system":
                        formatted_text += f"System: {msg['content']}\n"
                return len(self.tokenizer.encode(formatted_text, add_special_tokens=True))
        logger.warning(f"Tokenizer not available for {model_name}. Returning approximate token count.")
        # Fallback to rough estimate if tokenizer isn't loaded
        if text:
            return len(text.split()) * 4 // 3
        elif messages:
            total_words = 0
            for msg in messages:
                total_words += len(msg.get("content", "").split())
            return total_words * 4 // 3
        return 0

    def get_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        model_name = model_name if model_name else self.model_id
        # Capabilities depend heavily on the specific HF model.
        # This is a generic representation.
        capabilities = {
            "model_name": model_name,
            "provider": "HuggingFace",
            "max_context_length": 1024, # This varies greatly by model
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "supported_features": ["text_completion", "chat_completion_formatted", "streaming_partial"],
            "local_inference_supported": not self.use_inference_api
        }
        # Attempt to get max_position_embeddings from tokenizer config if available
        if self.tokenizer and hasattr(self.tokenizer, 'model_max_length'):
            capabilities["max_context_length"] = self.tokenizer.model_max_length
        return capabilities

# Register the HuggingFaceProvider with the LLMFactory
LLMFactory.register_provider("huggingface", HuggingFaceProvider)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Set dummy API token for testing purposes (replace with your actual key in .env)
    # This token is used by Inference API
    os.environ["HF_API_TOKEN"] = "hf_YOUR_HUGGINGFACE_TOKEN"
    
    # Example for local model inference (requires downloading model)
    # Test model: "Helsinki-NLP/opus-mt-en-de" (translation, so not causal LM, but for demo)
    # A small text-generation model like "sshleifer/tiny-gpt2" or "distilgpt2" could be used.
    test_model_id = "distilgpt2" # A small model for quick local testing

    # --- Test 1: Local Model Inference (if transformers available) ---
    if _TRANSFORMERS_AVAILABLE:
        print(f"\n--- Local Hugging Face Model Tests (Model: {test_model_id}) ---")
        try:
            # Ensure the model is small enough for local testing without large downloads
            hf_llm_local = HuggingFaceProvider(model_id=test_model_id, use_inference_api=False)
            hf_config = LLMConfig(model=test_model_id, temperature=0.7, max_tokens=50)

            print("\n--- Testing generate_text (Local) ---")
            response = hf_llm_local.generate_text("The quick brown fox jumps over the lazy", hf_config)
            print(f"Generated Text: {response.generated_text}")
            print(f"Tokens: Prompt={response.prompt_tokens}, Completion={response.completion_tokens}, Total={response.total_tokens}")

            print("\n--- Testing stream_text (Local - will be full text) ---")
            print("Streaming Text: ", end="")
            for chunk in hf_llm_local.stream_text("Once upon a time in a faraway land,", hf_config):
                print(chunk, end="")
            print("\n")
            
            print("\n--- Testing token count (Local) ---")
            tokens_text = hf_llm_local.count_tokens(text="This is a sentence for token counting.")
            print(f"Tokens in text (Local): {tokens_text}")
            
            caps_local = hf_llm_local.get_model_capabilities()
            print(f"Local Model Capabilities: {caps_local}")

        except ImportError:
            print("Skipping local Hugging Face tests: transformers not installed.")
        except Exception as e:
            print(f"Error during local HF tests: {e}")
    else:
        print("Hugging Face Transformers not available, skipping local model tests.")

    # --- Test 2: Hugging Face Inference API (if huggingface_hub available and token valid) ---
    if _HF_HUB_AVAILABLE and os.getenv("HF_API_TOKEN") and os.getenv("HF_API_TOKEN") != "hf_YOUR_HUGGINGFACE_TOKEN":
        print(f"\n--- Hugging Face Inference API Tests (Model: {test_model_id}) ---")
        try:
            hf_llm_api = HuggingFaceProvider(model_id=test_model_id, use_inference_api=True, api_token=os.getenv("HF_API_TOKEN"))
            hf_config = LLMConfig(model=test_model_id, temperature=0.7, max_tokens=50)

            print("\n--- Testing generate_text (Inference API) ---")
            response_api = hf_llm_api.generate_text("The cat sat on the", hf_config)
            print(f"Generated Text: {response_api.generated_text}")
            
            print("\n--- Testing stream_text (Inference API) ---")
            print("Streaming Text: ", end="")
            for chunk in hf_llm_api.stream_text("In a quaint little village,", hf_config):
                print(chunk, end="")
            print("\n")
            
            print("\n--- Testing token count (Inference API - approx.) ---")
            tokens_text_api = hf_llm_api.count_tokens(text="This is a sentence for Inference API token counting.")
            print(f"Tokens in text (Inference API - approx.): {tokens_text_api}")
            
            caps_api = hf_llm_api.get_model_capabilities()
            print(f"Inference API Model Capabilities: {caps_api}")

        except ImportError:
            print("Skipping Inference API tests: huggingface_hub not installed.")
        except Exception as e:
            print(f"Error during Inference API tests: {e}")
    else:
        print("Hugging Face Hub not available or HF_API_TOKEN not set, skipping Inference API tests.")
