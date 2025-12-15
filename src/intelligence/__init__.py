# Purpose: Intelligence module initialization
# What to add:
# Factory method: get_llm_provider(name)
# LLM Provider registry
# Default LLM provider based on config

import logging
from typing import Dict, Type, Any, Optional

# Import concrete LLM implementations to ensure they register themselves with LLMFactory
from . import openai_provider
from . import gemini_provider
from . import huggingface_provider

logger = logging.getLogger(__name__)

# Placeholder for actual LLM Provider classes
# These would be imported from other files within the 'intelligence' package
class BaseLLMProvider:
    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

# Factory and registry for LLM providers
_llm_provider_registry: Dict[str, Type[BaseLLMProvider]] = {}

def register_llm_provider(name: str, provider_class: Type[BaseLLMProvider]):
    """Registers an LLM provider class."""
    if name in _llm_provider_registry:
        logger.warning(f"LLM provider '{name}' already registered. Overwriting.")
    _llm_provider_registry[name] = provider_class
    logger.debug(f"LLM provider '{name}' registered.")

def get_llm_provider(name: str, **kwargs) -> BaseLLMProvider:
    """Retrieves an LLM provider instance by name."""
    provider_class = _llm_provider_registry.get(name)
    if not provider_class:
        raise ValueError(f"LLM provider '{name}' not found in registry.")
    logger.debug(f"Instantiating LLM provider '{name}'.")
    return provider_class(**kwargs)

# Module-level configuration for default LLM
_default_llm_provider_instance: Optional[BaseLLMProvider] = None

def initialize_intelligence_module(default_llm_provider_name: Optional[str] = None):
    """
    Initializes the intelligence module, setting up the default LLM provider.
    """
    global _default_llm_provider_instance
    if default_llm_provider_name:
        try:
            _default_llm_provider_instance = get_llm_provider(default_llm_provider_name)
            logger.info(f"Default LLM provider set to: {default_llm_provider_name}")
        except ValueError as e:
            logger.error(f"Failed to load default LLM provider '{default_llm_provider_name}': {e}")
    else:
        logger.info("Intelligence module initialized without a default LLM provider specified.")

def get_default_llm_provider() -> Optional[BaseLLMProvider]:
    """Returns the globally configured default LLM provider instance."""
    return _default_llm_provider_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Dummy LLM Provider for testing
    class DummyLLMProvider(BaseLLMProvider):
        def __init__(self, model_version: str = "default"):
            self.model_version = model_version
            logger.info(f"DummyLLMProvider initialized with model: {model_version}")

        def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
            logger.debug(f"DummyLLM generating response for prompt: {prompt}")
            response_text = f"Dummy response to '{prompt}' using {self.model_version}."
            if "medical" in prompt.lower():
                response_text += " (Medical context detected)."
            return {"text": response_text, "model": self.model_version, "usage": {"prompt_tokens": len(prompt.split()), "completion_tokens": len(response_text.split())}}

    # Register the dummy provider
    register_llm_provider("dummy_llm", DummyLLMProvider)

    # Initialize the module with the dummy provider
    initialize_intelligence_module(default_llm_provider_name="dummy_llm")

    # Get and use the default LLM provider
    default_llm = get_default_llm_provider()
    if default_llm:
        print("\n--- Using Default LLM Provider ---")
        response1 = default_llm.generate_response("Tell me about medical advances.")
        print(f"Response 1: {response1['text']}")

        response2 = default_llm.generate_response("What is the capital of France?")
        print(f"Response 2: {response2['text']}")

    # Get another instance of the dummy provider with different settings
    try:
        print("\n--- Using a specific LLM Provider instance ---")
        specific_llm = get_llm_provider("dummy_llm", model_version="advanced_dummy_v2")
        response3 = specific_llm.generate_response("Summarize this document.")
        print(f"Response 3: {response3['text']}")
    except ValueError as e:
        print(f"Error: {e}")