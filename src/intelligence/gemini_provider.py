# Purpose: Gemini LLM integration
# What to add:
# Implement LLMInterface for Gemini
# Use google-generativeai SDK
# Handle API key authentication
# Rate limiting and error handling (retry, exponential backoff)
# Model selection (gemini-pro, gemini-pro-vision)
# Safety settings integration
# Streaming support

from __future__ import annotations

import os
import time
import logging
from typing import Dict, Any, List, Generator, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import google.generativeai as genai # type: ignore
from google.api_core import exceptions # type: ignore

from .llm_interface import LLMInterface, LLMConfig, LLMResponse, LLMAPIError, LLMRateLimitError
from .llm_factory import LLMFactory # To register itself

logger = logging.getLogger(__name__)

import os # Ensure os is imported
# ... other imports ...

class GeminiProvider(LLMInterface):
    """
    Gemini LLM integration adhering to the LLMInterface.
    Uses the google-generativeai SDK for interacting with Gemini models.
    """
    def __init__(self, api_key: str, model: str = os.getenv("GEMINI_MODEL_NAME", "gemini-pro"), **kwargs):
        if not api_key:
            raise ValueError("Gemini API key is required.")
        genai.configure(api_key=api_key)
        self.default_model = model if model else "gemini-1.0-pro"
        self.safety_settings = kwargs.pop("safety_settings", [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ])
        logger.info(f"GeminiProvider initialized with default model: {self.default_model}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10),
           retry=retry_if_exception_type((exceptions.ResourceExhausted, exceptions.ServiceUnavailable)))
    def _generate_content_with_retry(self, model_instance, contents, generation_config, safety_settings, stream: bool = False):
        """Helper to call generate_content with retry logic."""
        return model_instance.generate_content(
            contents=contents,
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=stream
        )

    def generate_text(self, prompt: str, config: LLMConfig) -> LLMResponse:
        model_name = config.model if config.model else self.default_model
        try:
            model = genai.GenerativeModel(model_name=model_name)
            generation_config = {
                "temperature": config.temperature,
                "max_output_tokens": config.max_tokens,
                "top_p": config.top_p,
                # Gemini doesn't directly support 'stop_sequences' in generate_content,
                # but it can be handled programmatically post-generation if critical.
            }
            # For text generation, Gemini's generate_content expects string or part objects
            contents = prompt

            response = self._generate_content_with_retry(model, contents, generation_config, self.safety_settings)

            generated_text = ""
            if response.candidates:
                # Assuming first candidate is the primary one
                if hasattr(response.candidates[0], 'text'):
                    generated_text = response.candidates[0].text
                elif hasattr(response.candidates[0], 'content') and response.candidates[0].content.parts:
                    generated_text = "".join([p.text for p in response.candidates[0].content.parts if hasattr(p, 'text')])
            elif response.prompt_feedback and response.prompt_feedback.block_reason:
                raise LLMAPIError(f"Prompt blocked: {response.prompt_feedback.block_reason}")
            
            # Gemini SDK doesn't directly expose token counts in response like OpenAI
            # This is an approximation or would require a separate token counting call
            prompt_tokens = self.count_tokens(text=prompt, model_name=model_name)
            completion_tokens = self.count_tokens(text=generated_text, model_name=model_name)

            return LLMResponse(
                generated_text=generated_text,
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                raw_response=response.__dict__, # Access underlying proto/object structure
                finish_reason="STOP" # Gemini API response finish reason needs to be parsed from raw
            )
        except exceptions.ResourceExhausted as e:
            raise LLMRateLimitError(f"Gemini API rate limit exceeded: {e}") from e
        except exceptions.GoogleAPICallError as e:
            raise LLMAPIError(f"Gemini API error: {e}") from e
        except Exception as e:
            raise LLMAPIError(f"An unexpected error occurred with Gemini API: {e}") from e

    def generate_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> LLMResponse:
        model_name = config.model if config.model else self.default_model
        try:
            model = genai.GenerativeModel(model_name=model_name)
            generation_config = {
                "temperature": config.temperature,
                "max_output_tokens": config.max_tokens,
                "top_p": config.top_p,
            }

            # Convert messages to Gemini's chat format
            # Gemini's chat expects alternating 'user' and 'model' roles.
            # If the history doesn't strictly alternate, you might need to adjust or handle.
            gemini_history = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})

            # Start chat with the history, then send the last message
            chat = model.start_chat(history=gemini_history[:-1]) # All but the last message is history
            last_message_content = gemini_history[-1]["parts"]

            response = self._generate_content_with_retry(chat, last_message_content, generation_config, self.safety_settings)

            generated_text = ""
            if response.candidates:
                if hasattr(response.candidates[0], 'text'):
                    generated_text = response.candidates[0].text
                elif hasattr(response.candidates[0], 'content') and response.candidates[0].content.parts:
                    generated_text = "".join([p.text for p in response.candidates[0].content.parts if hasattr(p, 'text')])
            elif response.prompt_feedback and response.prompt_feedback.block_reason:
                raise LLMAPIError(f"Prompt blocked: {response.prompt_feedback.block_reason}")

            # Approximated token counts
            prompt_tokens = self.count_tokens(messages=messages, model_name=model_name)
            completion_tokens = self.count_tokens(text=generated_text, model_name=model_name)

            return LLMResponse(
                generated_text=generated_text,
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                raw_response=response.__dict__,
                finish_reason="STOP"
            )
        except exceptions.ResourceExhausted as e:
            raise LLMRateLimitError(f"Gemini API rate limit exceeded: {e}") from e
        except exceptions.GoogleAPICallError as e:
            raise LLMAPIError(f"Gemini API error: {e}") from e
        except Exception as e:
            raise LLMAPIError(f"An unexpected error occurred with Gemini API: {e}") from e

    def stream_text(self, prompt: str, config: LLMConfig) -> Generator[str, None, None]:
        model_name = config.model if config.model else self.default_model
        try:
            model = genai.GenerativeModel(model_name=model_name)
            generation_config = {
                "temperature": config.temperature,
                "max_output_tokens": config.max_tokens,
                "top_p": config.top_p,
            }
            contents = prompt

            response_stream = self._generate_content_with_retry(model, contents, generation_config, self.safety_settings, stream=True)

            for chunk in response_stream:
                if chunk.candidates and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if hasattr(part, 'text'):
                            yield part.text
                elif chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    raise LLMAPIError(f"Prompt blocked during stream: {chunk.prompt_feedback.block_reason}")

        except exceptions.ResourceExhausted as e:
            raise LLMRateLimitError(f"Gemini API rate limit exceeded during stream: {e}") from e
        except exceptions.GoogleAPICallError as e:
            raise LLMAPIError(f"Gemini API stream error: {e}") from e
        except Exception as e:
            raise LLMAPIError(f"An unexpected error occurred with Gemini API stream: {e}") from e

    def stream_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Generator[str, None, None]:
        model_name = config.model if config.model else self.default_model
        try:
            model = genai.GenerativeModel(model_name=model_name)
            generation_config = {
                "temperature": config.temperature,
                "max_output_tokens": config.max_tokens,
                "top_p": config.top_p,
            }

            gemini_history = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})

            chat = model.start_chat(history=gemini_history[:-1])
            last_message_content = gemini_history[-1]["parts"]

            response_stream = self._generate_content_with_retry(chat, last_message_content, generation_config, self.safety_settings, stream=True)

            for chunk in response_stream:
                if chunk.candidates and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if hasattr(part, 'text'):
                            yield part.text
                elif chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    raise LLMAPIError(f"Prompt blocked during stream: {chunk.prompt_feedback.block_reason}")

        except exceptions.ResourceExhausted as e:
            raise LLMRateLimitError(f"Gemini API rate limit exceeded during stream: {e}") from e
        except exceptions.GoogleAPICallError as e:
            raise LLMAPIError(f"Gemini API stream error: {e}") from e
        except Exception as e:
            raise LLMAPIError(f"An unexpected error occurred with Gemini API stream: {e}") from e

    def count_tokens(self, text: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None, model_name: Optional[str] = None) -> int:
        model_name = model_name if model_name else self.default_model
        model = genai.GenerativeModel(model_name=model_name)
        try:
            if text:
                response = model.count_tokens(text)
                return response.total_tokens
            elif messages:
                gemini_contents = []
                for msg in messages:
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_contents.append({"role": role, "parts": [msg["content"]]})
                response = model.count_tokens(gemini_contents)
                return response.total_tokens
            return 0
        except exceptions.GoogleAPICallError as e:
            logger.error(f"Gemini API token count error: {e}")
            return 0 # Return 0 on error, or raise if critical
        except Exception as e:
            logger.error(f"An unexpected error occurred during Gemini token count: {e}")
            return 0

    def get_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        model_name = model_name if model_name else self.default_model
        # Gemini does not expose a direct API for capabilities like max tokens, etc.
        # We need to rely on documentation or hardcoded values.
        # This is a mock for common capabilities.
        capabilities = {
            "model_name": model_name,
            "provider": "Gemini",
            "max_context_length": 32768 if "pro" in model_name else 4096, # Example, check docs for actual
            "input_modalities": ["text", "image"] if "vision" in model_name else ["text"],
            "output_modalities": ["text"],
            "supported_features": ["text_completion", "chat_completion", "streaming"],
            "safety_settings_configurable": True
        }
        return capabilities

# Register the GeminiProvider with the LLMFactory
LLMFactory.register_provider("gemini", GeminiProvider)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Set dummy API key for testing purposes (replace with your actual key in .env)
    os.environ["GEMINI_API_KEY"] = "YOUR_GEMINI_API_KEY" # Replace with a valid API key for live testing

    if os.getenv("GEMINI_API_KEY") == "YOUR_GEMINI_API_KEY" or not os.getenv("GEMINI_API_KEY"):
        logger.warning("Please set a valid GEMINI_API_KEY in your environment for live testing.")
        logger.warning("Skipping live Gemini API tests.")
    else:
        print("\n--- Live Gemini API Tests (if API_KEY is valid) ---")
        try:
            gemini_config = LLMConfig(model="gemini-pro", temperature=0.7, max_tokens=200)
            gemini_llm = GeminiProvider(api_key=os.getenv("GEMINI_API_KEY"), model="gemini-pro")

            print("\n--- Testing generate_text ---")
            response = gemini_llm.generate_text("Explain the concept of quantum entanglement in simple terms.", gemini_config)
            print(f"Generated Text: {response.generated_text[:200]}...")
            print(f"Tokens: Prompt={response.prompt_tokens}, Completion={response.completion_tokens}, Total={response.total_tokens}")

            print("\n--- Testing generate_chat_response ---")
            chat_messages = [
                {"role": "user", "content": "Hello, how are you?"},
                {"role": "model", "content": "I'm doing well, thank you for asking! How can I assist you today?"},
                {"role": "user", "content": "What is the capital of France?"}
            ]
            response_chat = gemini_llm.generate_chat_response(chat_messages, gemini_config)
            print(f"Generated Chat Response: {response_chat.generated_text}")
            print(f"Tokens: Prompt={response_chat.prompt_tokens}, Completion={response_chat.completion_tokens}, Total={response_chat.total_tokens}")

            print("\n--- Testing stream_text ---")
            print("Streaming Text: ", end="")
            for chunk in gemini_llm.stream_text("Tell me a short, inspiring story about perseverance.", gemini_config):
                print(chunk, end="")
            print("\n")

            print("\n--- Testing stream_chat_response ---")
            chat_messages_stream = [
                {"role": "user", "content": "Tell me a joke."},
            ]
            print("Streaming Chat Response: ", end="")
            for chunk in gemini_llm.stream_chat_response(chat_messages_stream, gemini_config):
                print(chunk, end="")
            print("\n")

            print("\n--- Testing token count ---")
            tokens_text = gemini_llm.count_tokens(text="This is a sentence to count tokens for.")
            print(f"Tokens in text: {tokens_text}")
            tokens_messages = gemini_llm.count_tokens(messages=[{"role": "user", "content": "Hi"}, {"role": "model", "content": "Hello there!"}])
            print(f"Tokens in messages: {tokens_messages}")

            print("\n--- Testing capabilities ---")
            caps = gemini_llm.get_model_capabilities("gemini-pro")
            print(f"Gemini Pro Capabilities: {caps}")

            print("\n--- Test error handling (e.g., invalid model) ---")
            try:
                invalid_config = LLMConfig(model="non-existent-gemini-model")
                gemini_llm.generate_text("Test", invalid_config)
            except LLMAPIError as e:
                print(f"Caught expected error for invalid model: {e}")

        except ValueError as e:
            print(f"Initialization error: {e}")
        except LLMAPIError as e:
            print(f"API Error during test: {e}")
        except LLMRateLimitError as e:
            print(f"Rate Limit Error during test: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during tests: {e}")