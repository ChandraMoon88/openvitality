# Purpose: OpenAI LLM integration
# What to add:
# Implement LLMInterface for OpenAI (GPT-3.5, GPT-4)
# Use openai Python SDK
# Handle API key authentication
# Rate limiting and error handling (retry, exponential backoff)
# Model selection
# Streaming support
# Function calling support (if applicable)

import os
import time
import logging
from typing import Dict, Any, List, Generator, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import openai
from openai import OpenAI # New client library
from openai.types.chat import ChatCompletionMessageParam # For type hinting messages

from .llm_interface import LLMInterface, LLMConfig, LLMResponse, LLMAPIError, LLMRateLimitError
from .llm_factory import LLMFactory # To register itself

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMInterface):
    """
    OpenAI LLM integration adhering to the LLMInterface.
    Uses the official OpenAI Python SDK for interacting with GPT models.
    """
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", **kwargs):
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = OpenAI(api_key=api_key)
        self.default_model = model
        self.organization = kwargs.pop("organization", None) # Optional OpenAI organization ID
        if self.organization:
            self.client.organization = self.organization
        logger.info(f"OpenAIProvider initialized with default model: {self.default_model}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), 
           retry=retry_if_exception_type((openai.APITimeoutError, openai.APIStatusError)))
    def _create_completion_with_retry(self, client_method, model: str, **kwargs):
        """Helper to call OpenAI API with retry logic."""
        try:
            return client_method(model=model, **kwargs)
        except openai.RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI API rate limit exceeded: {e}") from e
        except openai.APIConnectionError as e:
            raise LLMAPIError(f"OpenAI API connection error: {e}") from e
        except openai.APIStatusError as e:
            if e.status_code == 429: # Explicitly handle rate limit if not caught by Tenacity
                raise LLMRateLimitError(f"OpenAI API rate limit exceeded (status 429): {e}") from e
            raise LLMAPIError(f"OpenAI API status error: {e.status_code} - {e.response}") from e
        except Exception as e:
            raise LLMAPIError(f"An unexpected error occurred with OpenAI API: {e}") from e

    def generate_text(self, prompt: str, config: LLMConfig) -> LLMResponse:
        model_name = config.model if config.model else self.default_model
        messages: List[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]

        completion_params = {
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "stop": config.stop_sequences if config.stop_sequences else None,
            # Add other OpenAI specific params from config.extra_config if needed
        }

        response = self._create_completion_with_retry(self.client.chat.completions.create, model_name, **completion_params)

        generated_text = response.choices[0].message.content if response.choices else ""
        usage = response.usage
        
        return LLMResponse(
            generated_text=generated_text,
            model=model_name,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            raw_response=response.model_dump(), # Serialize pydantic model to dict
            finish_reason=response.choices[0].finish_reason if response.choices else None
        )

    def generate_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> LLMResponse:
        model_name = config.model if config.model else self.default_model
        
        # Type conversion for OpenAI SDK
        openai_messages: List[ChatCompletionMessageParam] = [{"role": m["role"], "content": m["content"]} for m in messages]

        completion_params = {
            "messages": openai_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "stop": config.stop_sequences if config.stop_sequences else None,
            # Add other OpenAI specific params from config.extra_config if needed
        }

        response = self._create_completion_with_retry(self.client.chat.completions.create, model_name, **completion_params)
        
        generated_text = response.choices[0].message.content if response.choices else ""
        usage = response.usage

        return LLMResponse(
            generated_text=generated_text,
            model=model_name,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            raw_response=response.model_dump(),
            finish_reason=response.choices[0].finish_reason if response.choices else None
        )

    def stream_text(self, prompt: str, config: LLMConfig) -> Generator[str, None, None]:
        model_name = config.model if config.model else self.default_model
        messages: List[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]

        stream_params = {
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "stop": config.stop_sequences if config.stop_sequences else None,
            "stream": True,
        }

        try:
            stream = self._create_completion_with_retry(self.client.chat.completions.create, model_name, **stream_params)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except LLMAPIError as e:
            logger.error(f"OpenAI API error during stream_text: {e}")
            raise
        except LLMRateLimitError as e:
            logger.error(f"OpenAI API rate limit during stream_text: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during OpenAI stream_text: {e}")
            raise

    def stream_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Generator[str, None, None]:
        model_name = config.model if config.model else self.default_model
        openai_messages: List[ChatCompletionMessageParam] = [{"role": m["role"], "content": m["content"]} for m in messages]

        stream_params = {
            "messages": openai_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "stop": config.stop_sequences if config.stop_sequences else None,
            "stream": True,
        }

        try:
            stream = self._create_completion_with_retry(self.client.chat.completions.create, model_name, **stream_params)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except LLMAPIError as e:
            logger.error(f"OpenAI API error during stream_chat_response: {e}")
            raise
        except LLMRateLimitError as e:
            logger.error(f"OpenAI API rate limit during stream_chat_response: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during OpenAI stream_chat_response: {e}")
            raise

    def count_tokens(self, text: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None) -> int:
        # This is a simplified token counting. For exact token counts,
        # one should use OpenAI's tokenizer (tiktoken) which is model-dependent.
        # For a rough estimate, we'll count words.
        logger.warning("Using approximate token counting. For exact counts, integrate 'tiktoken'.")
        if text:
            return len(text.split()) * 4 // 3 # Rough estimate, 1 token ~= 4 chars ~= 3 words
        elif messages:
            total_words = 0
            for msg in messages:
                total_words += len(msg.get("content", "").split())
            return total_words * 4 // 3
        return 0

    def get_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        model_name = model_name if model_name else self.default_model
        # These are common capabilities; specific models might have different limits.
        # For accurate max_context_length, refer to OpenAI's model documentation.
        capabilities = {
            "model_name": model_name,
            "provider": "OpenAI",
            "max_context_length": 128000 if "gpt-4-turbo" in model_name else (16384 if "gpt-3.5-turbo-16k" in model_name else 4096),
            "input_modalities": ["text", "image"] if "vision" in model_name else ["text"],
            "output_modalities": ["text"],
            "supported_features": ["text_completion", "chat_completion", "streaming", "function_calling"],
            "function_calling_supported": True if model_name.startswith("gpt-4") or model_name.startswith("gpt-3.5-turbo") else False
        }
        return capabilities

# Register the OpenAIProvider with the LLMFactory
LLMFactory.register_provider("openai", OpenAIProvider)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Set dummy API key for testing purposes (replace with your actual key in .env)
    os.environ["OPENAI_API_KEY"] = "YOUR_OPENAI_API_KEY" # Replace with a valid API key for live testing

    if os.getenv("OPENAI_API_KEY") == "YOUR_OPENAI_API_KEY" or not os.getenv("OPENAI_API_KEY"):
        logger.warning("Please set a valid OPENAI_API_KEY in your environment for live testing.")
        logger.warning("Skipping live OpenAI API tests.")
    else:
        print("\n--- Live OpenAI API Tests (if API_KEY is valid) ---")
        try:
            openai_config = LLMConfig(model="gpt-3.5-turbo", temperature=0.7, max_tokens=200)
            openai_llm = OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-3.5-turbo")

            print("\n--- Testing generate_text ---")
            response = openai_llm.generate_text("Explain the concept of neural networks.", openai_config)
            print(f"Generated Text: {response.generated_text[:200]}...")
            print(f"Tokens: Prompt={response.prompt_tokens}, Completion={response.completion_tokens}, Total={response.total_tokens}")

            print("\n--- Testing generate_chat_response ---")
            chat_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of Canada?"}
            ]
            response_chat = openai_llm.generate_chat_response(chat_messages, openai_config)
            print(f"Generated Chat Response: {response_chat.generated_text}")
            print(f"Tokens: Prompt={response_chat.prompt_tokens}, Completion={response_chat.completion_tokens}, Total={response_chat.total_tokens}")

            print("\n--- Testing stream_text ---")
            print("Streaming Text: ", end="")
            for chunk in openai_llm.stream_text("Describe a beautiful sunset over the ocean.", openai_config):
                print(chunk, end="")
            print("\n")

            print("\n--- Testing stream_chat_response ---")
            chat_messages_stream = [
                {"role": "user", "content": "Tell me about large language models."},
            ]
            print("Streaming Chat Response: ", end="")
            for chunk in openai_llm.stream_chat_response(chat_messages_stream, openai_config):
                print(chunk, end="")
            print("\n")

            print("\n--- Testing token count ---")
            tokens_text = openai_llm.count_tokens(text="This is a test sentence for token counting.")
            print(f"Tokens in text: {tokens_text}")
            tokens_messages = openai_llm.count_tokens(messages=[{"role": "user", "content": "How are you?"}, {"role": "assistant", "content": "I'm fine!"}])
            print(f"Tokens in messages: {tokens_messages}")

            print("\n--- Testing capabilities ---")
            caps = openai_llm.get_model_capabilities("gpt-4")
            print(f"GPT-4 Capabilities: {caps}")

            print("\n--- Test error handling (e.g., invalid model) ---")
            try:
                invalid_config = LLMConfig(model="non-existent-gpt-model")
                openai_llm.generate_text("Test", invalid_config)
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