# Purpose: Abstract interface for all LLMs
# What to add:
# Abstract base class for LLM providers
# Methods:
# generate_text(prompt, config)
# generate_chat_response(messages, config)
# stream_text(prompt, config)
# stream_chat_response(messages, config)
# count_tokens(text/messages)
# get_model_capabilities()
# Enforce common interface for all LLMs (OpenAI, Gemini, HuggingFace)
# Exception handling: Define custom exceptions for rate limits, API errors

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Generator, Optional

logger = logging.getLogger(__name__)

class LLMConfig:
    """Configuration class for LLM parameters."""
    def __init__(self,
                 model: str = "default-model",
                 temperature: float = 0.7,
                 max_tokens: int = 1024,
                 top_p: float = 1.0,
                 stop_sequences: Optional[List[str]] = None,
                 api_key: Optional[str] = None,
                 **kwargs):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.stop_sequences = stop_sequences if stop_sequences is not None else []
        self.api_key = api_key
        self.extra_config = kwargs # For provider-specific configs
        logger.debug(f"LLMConfig created for model: {model}")

class LLMResponse:
    """Standardized response object for LLM outputs."""
    def __init__(self,
                 generated_text: str,
                 model: str,
                 prompt_tokens: int = 0,
                 completion_tokens: int = 0,
                 total_tokens: int = 0,
                 raw_response: Optional[Dict[str, Any]] = None,
                 finish_reason: Optional[str] = None):
        self.generated_text = generated_text
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.raw_response = raw_response
        self.finish_reason = finish_reason
        logger.debug(f"LLMResponse generated. Model: {model}, Tokens: {total_tokens}")

class LLMAPIError(Exception):
    """Custom exception for LLM API errors."""
    pass

class LLMRateLimitError(LLMAPIError):
    """Custom exception for LLM rate limit errors."""
    pass

class LLMInterface(ABC):
    """
    Abstract Base Class defining the common interface for all Large Language Model (LLM) providers.
    All specific LLM provider implementations (e.g., OpenAI, Gemini, HuggingFace) must inherit
    from this class and implement its abstract methods.
    """

    @abstractmethod
    def generate_text(self, prompt: str, config: LLMConfig) -> LLMResponse:
        """
        Generates a single text completion based on a given prompt.

        :param prompt: The input text prompt.
        :param config: LLMConfig object containing model parameters.
        :return: A LLMResponse object.
        """
        pass

    @abstractmethod
    def generate_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> LLMResponse:
        """
        Generates a chat completion based on a list of messages (conversation history).

        :param messages: List of message dictionaries, e.g., [{"role": "user", "content": "Hello!"}].
        :param config: LLMConfig object containing model parameters.
        :return: A LLMResponse object.
        """
        pass

    @abstractmethod
    def stream_text(self, prompt: str, config: LLMConfig) -> Generator[str, None, None]:
        """
        Streams text completions based on a given prompt, yielding tokens as they are generated.

        :param prompt: The input text prompt.
        :param config: LLMConfig object containing model parameters.
        :return: A generator that yields string tokens.
        """
        pass

    @abstractmethod
    def stream_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Generator[str, None, None]:
        """
        Streams chat completions based on a list of messages, yielding tokens as they are generated.

        :param messages: List of message dictionaries.
        :param config: LLMConfig object containing model parameters.
        :return: A generator that yields string tokens.
        """
        pass

    @abstractmethod
    def count_tokens(self, text: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None, model_name: Optional[str] = None) -> int:
        """
        Counts the number of tokens in a given text or list of messages for a specific model.
        Either `text` or `messages` must be provided.

        :param text: The text string to count tokens for.
        :param messages: The list of message dictionaries to count tokens for.
        :param model_name: Optional. The name of the model to use for token counting.
        :return: The number of tokens.
        # Added a comment to force file modification for caching purposes.
        """
        pass

    @abstractmethod
    def get_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns the capabilities and metadata for a specific model or the default model.

        :param model_name: Optional. The name of the model to query capabilities for.
                           If None, returns capabilities for the default model.
        :return: A dictionary of model capabilities (e.g., max_context_length, supported_features).
        """
        pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example Dummy Implementation for demonstration
    class DummyLLMProvider(LLMInterface):
        def generate_text(self, prompt: str, config: LLMConfig) -> LLMResponse:
            logger.info(f"DummyLLM: Generating text for '{prompt[:50]}...'")
            generated_text = f"This is a dummy text response for: '{prompt}'. Model: {config.model}, Temp: {config.temperature}"
            return LLMResponse(generated_text, config.model, len(prompt.split()), len(generated_text.split()), len(prompt.split()) + len(generated_text.split()))

        def generate_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> LLMResponse:
            logger.info(f"DummyLLM: Generating chat response for {len(messages)} messages.")
            last_message_content = messages[-1]['content'] if messages else "empty message"
            generated_text = f"This is a dummy chat response to '{last_message_content}'. Model: {config.model}, Temp: {config.temperature}"
            return LLMResponse(generated_text, config.model, 10, 20, 30) # Dummy token counts

        def stream_text(self, prompt: str, config: LLMConfig) -> Generator[str, None, None]:
            logger.info(f"DummyLLM: Streaming text for '{prompt[:50]}...'")
            words = f"This is a dummy streamed text response for: '{prompt}'. Model: {config.model}, Temp: {config.temperature}".split()
            for word in words:
                yield word + " "
                time.sleep(0.05) # Simulate streaming delay

        def stream_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Generator[str, None, None]:
            logger.info(f"DummyLLM: Streaming chat response for {len(messages)} messages.")
            last_message_content = messages[-1]['content'] if messages else "empty message"
            words = f"This is a dummy streamed chat response to '{last_message_content}'. Model: {config.model}, Temp: {config.temperature}".split()
            for word in words:
                yield word + " "
                time.sleep(0.05) # Simulate streaming delay

        def count_tokens(self, text: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None) -> int:
            if text:
                return len(text.split())
            elif messages:
                total_words = 0
                for msg in messages:
                    total_words += len(msg.get("content", "").split())
                return total_words
            return 0

        def get_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]:
            model_name = model_name or "default-dummy-model"
            return {
                "model_name": model_name,
                "max_context_length": 4096,
                "supported_features": ["text_completion", "chat_completion", "streaming"],
                "provider": "DummyLLM"
            }

    import time # Needed for dummy streaming delay

    # Demonstrate usage
    llm_provider = DummyLLMProvider()
    config = LLMConfig(model="test-model-v1", temperature=0.5)

    # Generate text
    text_response = llm_provider.generate_text("Hello, how are you?", config)
    print(f"\nGenerated Text: {text_response.generated_text}")

    # Generate chat response
    chat_messages = [{"role": "user", "content": "Tell me a joke."}, {"role": "assistant", "content": "Why did the scarecrow win an award? Because he was outstanding in his field!"}]
    config.model = "test-chat-model"
    chat_response = llm_provider.generate_chat_response(chat_messages, config)
    print(f"\nGenerated Chat Response: {chat_response.generated_text}")

    # Stream text
    print("\nStreaming Text:")
    for token in llm_provider.stream_text("Write a short story about a brave knight.", config):
        print(token, end="")
    print("\n")

    # Stream chat response
    print("\nStreaming Chat Response:")
    for token in llm_provider.stream_chat_response(chat_messages + [{"role": "user", "content": "That's a good one!"}], config):
        print(token, end="")
    print("\n")

    # Count tokens
    token_count_text = llm_provider.count_tokens(text="This is a test sentence.")
    print(f"\nTokens in text: {token_count_text}")
    token_count_messages = llm_provider.count_tokens(messages=[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there"}])
    print(f"Tokens in messages: {token_count_messages}")

    # Get model capabilities
    capabilities = llm_provider.get_model_capabilities()
    print(f"\nModel Capabilities: {capabilities}")