# Purpose: Centralized creation of LLM instances
# What to add:
# Factory method: get_llm(provider_name, model_name, config)
# Cache LLM instances (avoid re-initialization)
# Handle API key management (load from env)
# Register specific LLM providers (OpenAI, Gemini, HuggingFace)
# Error handling for unsupported providers or invalid configs

import logging
import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Import the abstract interface
from .llm_interface import LLMInterface, LLMConfig

# Import concrete LLM implementations (will be created in subsequent files)
# For now, we'll use placeholder/mock classes
class OpenAIProvider(LLMInterface):
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        logger.debug("OpenAIProvider initialized.")
    # Implement abstract methods here

logger = logging.getLogger(__name__)
load_dotenv() # Load environment variables from .env

class LLMFactory:
    """
    Centralized factory for creating and managing LLM provider instances.
    Handles configuration, API key management, and caching of instances.
    """
    _llm_instances: Dict[str, LLMInterface] = {}
    _provider_map: Dict[str, type[LLMInterface]] = {
        "openai": OpenAIProvider,
        #"gemini": GeminiProvider, # Removed placeholder mapping
        # "huggingface": HuggingFaceProvider,  # Removed initial registration
        # Register other providers here
    }

    @staticmethod
    def register_provider(name: str, provider_class: type[LLMInterface]):
        """
        Registers a new LLM provider with the factory.
        :param name: The unique name for the provider (e.g., "custom_llm").
        :param provider_class: The class of the LLM provider, must inherit from LLMInterface.
        """
        if not issubclass(provider_class, LLMInterface):
            raise TypeError("Provider class must inherit from LLMInterface.")
        LLMFactory._provider_map[name.lower()] = provider_class
        logger.info(f"LLM provider '{name}' registered with factory.")

    @staticmethod
    def get_llm(provider_name: str, model_name: str, config: Optional[LLMConfig] = None) -> LLMInterface:
        """
        Retrieves or creates an LLM instance for the specified provider and model.
        Instances are cached to avoid redundant initialization.

        :param provider_name: The name of the LLM provider (e.g., "openai", "gemini").
        :param model_name: The specific model to use (e.g., "gpt-4", "gemini-pro").
        :param config: Optional LLMConfig object for specific parameters.
                       If not provided, a default config will be used.
        :return: An initialized instance of the LLMInterface.
        :raises ValueError: If the provider is not supported or configuration is invalid.
        """
        provider_name_lower = provider_name.lower()
        instance_key = f"{provider_name_lower}-{model_name}"

        if instance_key in LLMFactory._llm_instances:
            logger.debug(f"Returning cached LLM instance for {instance_key}")
            return LLMFactory._llm_instances[instance_key]

        if provider_name_lower not in LLMFactory._provider_map:
            raise ValueError(f"Unsupported LLM provider: {provider_name}. Available: {list(LLMFactory._provider_map.keys())}")

        provider_class = LLMFactory._provider_map[provider_name_lower]

        if not config:
            config = LLMConfig(model=model_name)
            logger.debug(f"Using default LLMConfig for {instance_key}")

        # Load API key from environment variables based on provider name
        api_key = None
        if provider_name_lower == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider_name_lower == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
        # Add logic for other providers if their API keys differ in naming convention
        # For HuggingFace, it might be a token or depend on the model hosted.

        if not api_key and provider_name_lower in ["openai", "gemini"]:
             # If API key is critical for instantiation and not found, raise an error
            logger.error(f"API key for {provider_name} not found in environment variables.")
            #raise ValueError(f"API key for {provider_name} not set in environment.")


        # Pass the config and API key (if applicable) to the provider's constructor
        # Note: Concrete providers will handle how they use the config and api_key
        # For HuggingFace, model_id might be passed instead of api_key if it's a local/hosted model
        try:
            if provider_name_lower == "huggingface":
                hf_extra_config = config.extra_config.copy() if config.extra_config else {}
                use_inference_api_flag = hf_extra_config.pop("use_inference_api", False)
                print(f"[DEBUG] LLMFactory.get_llm - use_inference_api_flag for HuggingFace: {use_inference_api_flag}")
                instance = provider_class(model_id=model_name, use_inference_api=use_inference_api_flag, **hf_extra_config)
            else:
                instance = provider_class(api_key=api_key, **config.extra_config, model=model_name)

            LLMFactory._llm_instances[instance_key] = instance
            logger.info(f"Created and cached new LLM instance for {instance_key}")
            return instance
        except Exception as e:
            logger.error(f"Error initializing LLM provider '{provider_name}' with model '{model_name}': {e}")
            raise ValueError(f"Failed to initialize LLM provider: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # --- Dummy Implementations (for testing LLMFactory itself) ---
    class MockOpenAI(LLMInterface):
        def __init__(self, api_key: str, model: str, **kwargs):
            self.api_key = api_key
            self.model = model
            self.kwargs = kwargs
            logger.info(f"MockOpenAI initialized for model {self.model}")
        def generate_text(self, prompt: str, config: LLMConfig) -> Any: return {"text": f"Mock OpenAI text for {prompt}"}
        def generate_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Any: return {"text": f"Mock OpenAI chat for {messages[-1]['content']}"}
        def stream_text(self, prompt: str, config: LLMConfig) -> Any: yield f"Mock stream for {prompt}"
        def stream_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Any: yield f"Mock stream chat for {messages[-1]['content']}"
        def count_tokens(self, text: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None) -> int: return 10
        def get_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]: return {"provider": "OpenAI", "model": self.model}

    class MockGemini(LLMInterface):
        def __init__(self, api_key: str, model: str, **kwargs):
            self.api_key = api_key
            self.model = model
            self.kwargs = kwargs
            logger.info(f"MockGemini initialized for model {self.model}")
        def generate_text(self, prompt: str, config: LLMConfig) -> Any: return {"text": f"Mock Gemini text for {prompt}"}
        def generate_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Any: return {"text": f"Mock Gemini chat for {messages[-1]['content']}"}
        def stream_text(self, prompt: str, config: LLMConfig) -> Any: yield f"Mock stream for {prompt}"
        def stream_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Any: yield f"Mock stream chat for {messages[-1]['content']}"
        def count_tokens(self, text: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None) -> int: return 10
        def get_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]: return {"provider": "Gemini", "model": self.model}

    class MockHuggingFace(LLMInterface):
        def __init__(self, model_id: str, **kwargs):
            self.model_id = model_id
            self.kwargs = kwargs
            logger.info(f"MockHuggingFace initialized for model {self.model_id}")
        def generate_text(self, prompt: str, config: LLMConfig) -> Any: return {"text": f"Mock HF text for {prompt}"}
        def generate_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Any: return {"text": f"Mock HF chat for {messages[-1]['content']}"}
        def stream_text(self, prompt: str, config: LLMConfig) -> Any: yield f"Mock stream for {prompt}"
        def stream_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Any: yield f"Mock stream chat for {messages[-1]['content']}"
        def count_tokens(self, text: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None) -> int: return 10
        def get_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]: return {"provider": "HuggingFace", "model": self.model_id}

    # Register mock providers (overwriting placeholders)
    LLMFactory.register_provider("openai", MockOpenAI)
    LLMFactory.register_provider("gemini", MockGemini)
    LLMFactory.register_provider("huggingface", MockHuggingFace)

    # --- Test Cases ---
    os.environ["OPENAI_API_KEY"] = "sk-test-openai"
    os.environ["GEMINI_API_KEY"] = "gemini-test-key"

    print("\n--- Test 1: Get OpenAI instance ---")
    openai_llm = LLMFactory.get_llm("openai", "gpt-4")
    print(f"OpenAI LLM created: {openai_llm.get_model_capabilities()}")
    # Test caching
    openai_llm_cached = LLMFactory.get_llm("openai", "gpt-4")
    print(f"OpenAI LLM (cached): {openai_llm_cached.get_model_capabilities()}")
    assert openai_llm is openai_llm_cached

    print("\n--- Test 2: Get Gemini instance with custom config ---")
    gemini_config = LLMConfig(model="gemini-pro", temperature=0.9, extra_config={"region": "us-east"})
    gemini_llm = LLMFactory.get_llm("gemini", "gemini-pro", config=gemini_config)
    print(f"Gemini LLM created: {gemini_llm.get_model_capabilities()}")
    # Test using it (will return mock text)
    print(f"Gemini response: {gemini_llm.generate_text('test', gemini_config)}")

    print("\n--- Test 3: Get HuggingFace instance ---")
    hf_llm = LLMFactory.get_llm("huggingface", "facebook/opt-live-1.3b")
    print(f"HuggingFace LLM created: {hf_llm.get_model_capabilities()}")
    print(f"HuggingFace response: {hf_llm.generate_text('test', LLMConfig(model='facebook/opt-live-1.3b'))}")

    print("\n--- Test 4: Unsupported provider ---")
    try:
        LLMFactory.get_llm("unsupported_llm", "model-x")
    except ValueError as e:
        print(f"Error caught as expected: {e}")

    print("\n--- Test 5: Register custom provider ---")
    class CustomLLM(LLMInterface):
        def __init__(self, api_key: str, model: str, **kwargs): self.model = model; logger.info(f"CustomLLM initialized for {model}")
        def generate_text(self, prompt: str, config: LLMConfig) -> Any: return {"text": "Custom LLM response"}
        def generate_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Any: return {"text": "Custom LLM chat response"}
        def stream_text(self, prompt: str, config: LLMConfig) -> Any: yield "Custom stream"
        def stream_chat_response(self, messages: List[Dict[str, str]], config: LLMConfig) -> Any: yield "Custom stream chat"
        def count_tokens(self, text: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None) -> int: return 10
        def get_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]: return {"provider": "Custom", "model": self.model}

    LLMFactory.register_provider("custom_llm", CustomLLM)
    custom_llm_instance = LLMFactory.get_llm("custom_llm", "my-custom-model", LLMConfig(api_key="my-key"))
    print(f"Custom LLM created: {custom_llm_instance.get_model_capabilities()}")
    print(f"Custom LLM response: {custom_llm_instance.generate_text('query', LLMConfig(model='my-custom-model'))}")