# src/intelligence/cultural_adapter.py

from typing import Dict, Any
import re

# Assuming these imports will be available from other modules
# from src.intelligence.prompt_manager import PromptManager

class CulturalAdapter:
    """
    Adapts AI communication style, tone, and content based on the cultural context
    of the user's region, leveraging information from the PromptManager's cultural nuances.
    """
    def __init__(self, prompt_manager_instance):
        """
        Initializes the CulturalAdapter.
        
        :param prompt_manager_instance: An initialized PromptManager instance to fetch cultural nuances.
        """
        self.prompt_manager = prompt_manager_instance
        print("✅ CulturalAdapter initialized.")

    def adapt_response(self, text: str, session_context: Dict[str, Any]) -> str:
        """
        Adapts the given AI response text based on the session's cultural context.
        
        :param text: The AI generated text to adapt.
        :param session_context: A dictionary containing session-specific information,
                                including 'country_code' and 'detected_language'.
        :return: The culturally adapted text.
        """
        country_code = session_context.get("country_code", "default").lower()
        
        # Retrieve cultural nuances. PromptManager provides a formatted string,
        # but here we might want the raw dictionary for structured processing.
        # For simplicity, we'll get the raw dict by directly accessing the loader
        # or by having a specific method in PromptManager for it.
        
        # Mock cultural nuances for demonstration purposes if PromptManager doesn't expose raw dict
        cultural_nuances = self._get_raw_cultural_nuances(country_code)

        if not cultural_nuances:
            return text # No specific adaptations for this country

        adapted_text = text

        # 1. Apply respectful suffixes (e.g., "Ji" for India)
        if cultural_nuances.get("use_respectful_suffixes") and country_code == "in":
            # Simple heuristic: if the AI is addressing the user directly, add 'Ji'
            # This is a very basic example; a proper implementation needs NLP to detect direct address.
            if re.search(r'\b(you|your)\b', adapted_text, re.IGNORECASE):
                # Only add if not already present or if the sentence structure allows
                if not adapted_text.strip().endswith("Ji.") and not adapted_text.strip().endswith("Ji?"):
                    adapted_text = adapted_text.replace("Thank you.", "Thank you, Ji.")
                    adapted_text = adapted_text.replace("How can I help you?", "How can I help you, Ji.")

        # 2. Adjust communication style (e.g., direct for USA)
        communication_style = cultural_nuances.get("communication_style")
        if communication_style == "direct" and country_code == "us":
            # Ensure AI responses are concise and to the point.
            # This is hard to implement via simple string manipulation.
            # It implies the LLM itself should be guided by this.
            pass # The LLM prompt is the primary place for this.

        # 3. Terminology adjustments (e.g., "GP" for UK vs "Physician" for US)
        terminology = cultural_nuances.get("terminology")
        if terminology == "british_english" and country_code == "gb":
            adapted_text = adapted_text.replace("physician", "GP")
            adapted_text = adapted_text.replace("emergency room", "A&E")
            adapted_text = adapted_text.replace("pharmacy", "chemist")

        # 4. Integrate specific notes into response if relevant (e.g., insurance upfront)
        if cultural_nuances.get("insurance_upfront") and country_code == "us":
            # If the response is about services, add a note about insurance
            if "service" in adapted_text.lower() or "treatment" in adapted_text.lower():
                if "insurance" not in adapted_text.lower():
                    adapted_text += " Please note, we'll discuss insurance coverage upfront."
        
        return adapted_text

    def _get_raw_cultural_nuances(self, country_code: str) -> Dict[str, Any]:
        """
        Helper to get the raw dictionary of cultural nuances.
        In a real system, PromptManager might have a dedicated method for this.
        """
        # For example, by directly calling the config loader (mocked here)
        # This bypasses the prompt manager's formatting.
        mock_data = {
            "in": {
                "use_respectful_suffixes": True,
                "family_context_important": True,
                "prefer_generic_drugs": True,
                "festivals_affect_availability": ["Diwali", "Eid"]
            },
            "us": {
                "communication_style": "direct",
                "insurance_upfront": True,
                "litigation_risk": "high"
            },
            "gb": {
                "terminology": "british_english",
                "nhs_number_validation": True
            }
        }
        return mock_data.get(country_code.lower(), {})


# Example Usage
if __name__ == "__main__":
    
    # Mock PromptManager (only need the part that provides cultural nuances)
    class MockPromptManager:
        def get_cultural_nuance_prompt(self, country_code: str) -> str:
            # This mock just returns a simple string, not the raw dict needed by adapter
            # The CulturalAdapter directly accesses _get_raw_cultural_nuances in this example
            return ""

    # --- Initialize ---
    mock_pm = MockPromptManager()
    adapter = CulturalAdapter(mock_pm)

    # --- Test 1: US context ---
    print("\n--- Test 1: US Context ---")
    session_ctx_us = {"session_id": "s_us_1", "country_code": "us", "detected_language": "en"}
    response_us = "We can offer you various medical services."
    adapted_response_us = adapter.adapt_response(response_us, session_ctx_us)
    print(f"Original (US): '{response_us}'")
    print(f"Adapted (US):  '{adapted_response_us}'")

    # --- Test 2: India context ---
    print("\n--- Test 2: India Context ---")
    session_ctx_in = {"session_id": "s_in_1", "country_code": "in", "detected_language": "hi"}
    response_in = "Thank you. How can I help you?"
    adapted_response_in = adapter.adapt_response(response_in, session_ctx_in)
    print(f"Original (IN): '{response_in}'")
    print(f"Adapted (IN):  '{adapted_response_in}'")

    # --- Test 3: UK context ---
    print("\n--- Test 3: UK Context ---")
    session_ctx_gb = {"session_id": "s_gb_1", "country_code": "gb", "detected_language": "en"}
    response_gb = "Please consult your physician or visit the emergency room."
    adapted_response_gb = adapter.adapt_response(response_gb, session_ctx_gb)
    print(f"Original (GB): '{response_gb}'")
    print(f"Adapted (GB):  '{adapted_response_gb}'")

    # --- Test 4: Default/unconfigured country ---
    print("\n--- Test 4: Default Country ---")
    session_ctx_default = {"session_id": "s_default_1", "country_code": "fr", "detected_language": "fr"}
    response_default = "Hello, how are you?"
    adapted_response_default = adapter.adapt_response(response_default, session_ctx_default)
    print(f"Original (FR): '{response_default}'")
    print(f"Adapted (FR):  '{adapted_response_default}'")
