import google.generativeai as genai
import os

# Configure the API key. Use a dummy if not available to avoid immediate failure,
# though actual list_models might fail without a valid key.
api_key = os.getenv("GEMINI_API_KEY", "YOUR_DUMMY_API_KEY")
genai.configure(api_key=api_key)

print("Attempting to list available Gemini models...")
try:
    for m in genai.list_models():
        print(f"Name: {m.name}")
        print(f"  Description: {m.description}")
        print(f"  Supported Generation Methods: {m.supported_generation_methods}")
        print("-" * 20)
except Exception as e:
    print(f"Error listing models: {e}")
    print("Please ensure your GEMINI_API_KEY is correctly set and valid.")
