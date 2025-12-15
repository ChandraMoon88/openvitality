import os
import sys
from src.intelligence.llm_factory import LLMFactory
from src.intelligence.llm_interface import LLMConfig
import logging

# Add the project root to sys.path if not already there
# This allows running the script directly from any subdirectory
script_dir = os.path.dirname(__file__)
# Go up two levels to reach the project root (from src/intelligence to project_root)
project_root = os.path.abspath(os.path.join(script_dir, "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"DEBUG: project_root = {project_root}")
print(f"DEBUG: sys.path = {sys.path}")

logging.basicConfig(level=logging.INFO) # Set logging level for better output

# --- IMPORTANT ---
# 1. Obtain a Hugging Face API Token from huggingface.co/settings/tokens
# 2. Set this token as an environment variable named `HF_API_TOKEN`
#    Example: os.environ["HF_API_TOKEN"] = "hf_YOUR_ACTUAL_TOKEN_HERE"
#    (It's best practice to set this outside the script, e.g., in your shell or a .env file)

# 3. Choose your model ID from Hugging Face Hub. Ensure it supports the Inference API.
#    Examples: "HuggingFaceH4/zephyr-7b-beta", "mistralai/Mistral-7B-Instruct-v0.2"
model_id = "HuggingFaceH4/zephyr-7b-beta" 

if __name__ == "__main__":
    if "HF_API_TOKEN" not in os.environ:
        print("ERROR: HF_API_TOKEN environment variable is not set.")
        print("Please set it with your Hugging Face API token before running this script.")
        exit(1)



    print(f"Attempting to initialize HuggingFaceProvider for model: {model_id}")

    try:
        # Define LLM configuration for the factory and subsequent calls
        hf_config_for_factory = LLMConfig(
            model=model_id,
            temperature=0.7,
            max_tokens=100,
            extra_config={"use_inference_api": True} # Ensures Inference API is used
        )

        # Instantiate the provider using the LLMFactory
        hf_llm = LLMFactory.get_llm(
            provider_name="huggingface",
            model_name=model_id,
            config=hf_config_for_factory
        )

        # The 'config' object for generate_text, stream_text etc. can be the same
        # as hf_config_for_factory if no further modifications are needed.
        config = hf_config_for_factory

        # --- Test generate_text ---
        print("\n--- Testing generate_text ---")
        prompt = "Write a short, engaging story about a brave knight and a mischievous dragon."
        response = hf_llm.generate_text(prompt, config)
        print(f"Generated Text:\n{response.generated_text}")
        print(f"Tokens: Prompt={response.prompt_tokens}, Completion={response.completion_tokens}, Total={response.total_tokens}")

        # --- Test stream_text ---
        print("\n--- Testing stream_text ---")
        print("Streaming Text: ", end="")
        stream_prompt = "Describe a futuristic city where flying cars are common."
        for chunk in hf_llm.stream_text(stream_prompt, config):
            print(chunk, end="")
        print("\n")

        # --- Test generate_chat_response (for instruct models) ---
        print("\n--- Testing generate_chat_response ---")
        messages = [
            {"role": "user", "content": "What is the capital of France?"},
            {"role": "assistant", "content": "The capital of France is Paris."},
            {"role": "user", "content": "And what is the capital of Japan?"}
        ]
        chat_response = hf_llm.generate_chat_response(messages, config)
        print(f"Chat Response:\n{chat_response.generated_text}")

    except Exception as e:
        print(f"An error occurred during Hugging Face API usage: {e}")
        if "token" in str(e).lower() or "authentication" in str(e).lower():
            print("Please ensure your HF_API_TOKEN environment variable is set correctly.")
        elif "model" in str(e).lower():
            print(f"Please check if the model '{model_id}' is available via the Inference API or if there's a typo.")
