import os
import sys
import logging
from src.intelligence.llm_factory import LLMFactory
from src.intelligence.llm_interface import LLMConfig, LLMAPIError, LLMRateLimitError

# Add the project root to sys.path if not already there
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- IMPORTANT ---
# 1. Obtain a Google Gemini API Key from Google AI Studio or Google Cloud.
# 2. Set this token as an environment variable named `GEMINI_API_KEY`
#    Example: os.environ["GEMINI_API_KEY"] = "YOUR_ACTUAL_GEMINI_API_KEY_HERE"
#    (It's best practice to set this outside the script, e.g., in your shell or a .env file)

# 3. Choose your model ID.
model_id = os.getenv("GEMINI_MODEL_NAME", "gemini-pro")

if __name__ == "__main__":
    if "GEMINI_API_KEY" not in os.environ or not os.environ["GEMINI_API_KEY"]:
        logger.error("ERROR: GEMINI_API_KEY environment variable is not set.")
        logger.error("Please set it with your Google Gemini API key before running this script.")
        exit(1)

    print(f"Attempting to initialize GeminiProvider for model: {model_id}")

    try:
        # Define LLM configuration for the factory and subsequent calls
        gemini_config = LLMConfig(
            model=model_id,
            temperature=0.7,
            max_tokens=200,
            # Add any specific Gemini extra_config here if needed, e.g., safety_settings
            # extra_config={"safety_settings": [...]}
        )

        # Instantiate the provider using the LLMFactory
        gemini_llm = LLMFactory.get_llm(
            provider_name="gemini",
            model_name=model_id,
            config=gemini_config
        )

        # --- Test generate_text ---
        print("\n--- Testing generate_text ---")
        prompt = "Explain the concept of quantum entanglement in simple terms."
        response = gemini_llm.generate_text(prompt, gemini_config)
        print(f"Generated Text:\n{response.generated_text[:200]}...")
        print(f"Tokens: Prompt={response.prompt_tokens}, Completion={response.completion_tokens}, Total={response.total_tokens}")

        # --- Test stream_text ---
        print("\n--- Testing stream_text ---")
        print("Streaming Text: ", end="")
        stream_prompt = "Tell me a short, inspiring story about perseverance."
        for chunk in gemini_llm.stream_text(stream_prompt, gemini_config):
            print(chunk, end="")
        print("\n")

        # --- Test generate_chat_response (for conversational models) ---
        print("\n--- Testing generate_chat_response ---")
        messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "model", "content": "I'm doing well, thank you for asking! How can I assist you today?"},
            {"role": "user", "content": "What is the capital of France?"}
        ]
        chat_response = gemini_llm.generate_chat_response(messages, gemini_config)
        print(f"Generated Chat Response:\n{chat_response.generated_text}")
        print(f"Tokens: Prompt={chat_response.prompt_tokens}, Completion={chat_response.completion_tokens}, Total={chat_response.total_tokens}")

        # --- Test stream_chat_response ---
        print("\n--- Testing stream_chat_response ---")
        chat_messages_stream = [
            {"role": "user", "content": "Tell me a joke."},
        ]
        print("Streaming Chat Response: ", end="")
        for chunk in gemini_llm.stream_chat_response(chat_messages_stream, gemini_config):
            print(chunk, end="")
        print("\n")

        # --- Test token count ---
        print("\n--- Testing token count ---")
        tokens_text = gemini_llm.count_tokens(text="This is a sentence to count tokens for.")
        print(f"Tokens in text: {tokens_text}")
        tokens_messages = gemini_llm.count_tokens(messages=[{"role": "user", "content": "Hi"}, {"role": "model", "content": "Hello there!"}])
        print(f"Tokens in messages: {tokens_messages}")

        print("\n--- Testing capabilities ---")
        caps = gemini_llm.get_model_capabilities(model_id)
        print(f"Gemini Capabilities: {caps}")

    except ValueError as e:
        logger.error(f"Initialization error: {e}")
    except LLMAPIError as e:
        logger.error(f"API Error during test: {e}")
    except LLMRateLimitError as e:
        logger.error(f"Rate Limit Error during test: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during tests: {e}")
