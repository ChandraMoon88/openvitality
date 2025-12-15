# src/intelligence/prompt_manager.py

import os
import yaml
from functools import lru_cache
from typing import Dict, Any, List

class PromptManager:
    """
    Manages and dynamically loads LLM prompts from configuration files,
    supporting templating and cultural adjustments.
    """
    def __init__(self, config_loader_func):
        """
        Initializes the PromptManager.
        
        :param config_loader_func: A callable function that can load YAML
                                   configuration files (e.g., from src/core/config_loader.py).
        """
        self.config_loader = config_loader_func
        self.prompts_dir = "config/prompts"
        print("✅ PromptManager initialized.")

    @lru_cache(maxsize=16) # Cache loaded YAML files
    def _load_prompt_file(self, filename: str) -> Dict[str, Any]:
        """Loads a specific YAML prompt file."""
        file_path = os.path.join(self.prompts_dir, filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        
        # Use the provided config_loader_func to load the YAML
        # Assuming it handles file reading and YAML parsing.
        return self.config_loader(file_path)

    def get_base_persona_prompt(self, persona_name: str = "base_persona") -> str:
        """
        Retrieves a base persona prompt from 'system_personas.yaml'.
        
        :param persona_name: The key for the desired persona in the YAML.
        :return: The string prompt for the base persona.
        """
        try:
            personas = self._load_prompt_file("system_personas.yaml")
            prompt = personas.get(persona_name)
            if not prompt:
                raise ValueError(f"Persona '{persona_name}' not found in system_personas.yaml")
            return prompt
        except Exception as e:
            print(f"🚨 Error loading base persona prompt: {e}")
            return "You are a helpful assistant." # Fallback

    def get_cultural_nuance_prompt(self, country_code: str) -> str:
        """
        Retrieves cultural nuances for a given country code from 'cultural_nuances.yaml'.
        
        :param country_code: The ISO 3166-1 alpha-2 code for the country (e.g., "in" for India).
        :return: A string describing cultural nuances, or an empty string if none found.
        """
        try:
            nuances = self._load_prompt_file("cultural_nuances.yaml")
            cultural_notes = nuances.get(country_code.lower(), {})
            
            if not cultural_notes:
                return "" # No specific nuances for this country
            
            # Format cultural notes into a string for the LLM
            formatted_notes = f"\nConsider the following cultural nuances for interactions in {country_code.upper()}:\n"
            for key, value in cultural_notes.items():
                if isinstance(value, list):
                    formatted_notes += f"- {key.replace('_', ' ').capitalize()}: {', '.join(value)}\n"
                else:
                    formatted_notes += f"- {key.replace('_', ' ').capitalize()}: {value}\n"
            return formatted_notes
        except Exception as e:
            print(f"🚨 Error loading cultural nuance prompt for {country_code}: {e}")
            return ""

    def get_full_system_prompt(self, persona_name: str, country_code: str = None, **kwargs) -> str:
        """
        Constructs a complete system prompt by combining base persona and cultural nuances,
        and then applying any additional templating.
        
        :param persona_name: The name of the base persona.
        :param country_code: Optional, the country code for cultural adjustments.
        :param kwargs: Additional key-value pairs for prompt templating.
        :return: The fully constructed system prompt string.
        """
        base_prompt = self.get_base_persona_prompt(persona_name)
        cultural_prompt = ""
        if country_code:
            cultural_prompt = self.get_cultural_nuance_prompt(country_code)
            
        final_prompt = base_prompt + cultural_prompt

        # Apply templating
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            if placeholder in final_prompt:
                final_prompt = final_prompt.replace(placeholder, str(value))
        
        return final_prompt

# Example Usage
if __name__ == "__main__":
    # Mock config loader function for demonstration
    def mock_config_loader(file_path: str) -> Dict[str, Any]:
        """A simple mock to load local YAML files."""
        # For this example, we'll manually create the YAML structure in memory
        # In a real app, this would read from the actual config/prompts directory.
        if "system_personas.yaml" in file_path:
            return {
                "base_persona": """You are a compassionate, multilingual medical assistant.
WHAT YOU ARE NOT: Not a licensed physician. Cannot diagnose diseases.
YOUR PRIME DIRECTIVES: 1. Safety first. 2. Never guess. 3. Cite sources.
COMMUNICATION STYLE: Warm and empathetic. Ask one question at a time.
Patient: {patient_name}""",
                "emergency_persona": "EMERGENCY MODE ACTIVATED. Speak calmly and clearly."
            }
        elif "cultural_nuances.yaml" in file_path:
            return {
                "in": {
                    "use_respectful_suffixes": True,
                    "family_context_important": True,
                    "prefer_generic_drugs": True,
                    "festivals_affect_availability": ["Diwali", "Eid"]
                },
                "us": {
                    "communication_style": "direct",
                    "insurance_upfront": True
                }
            }
        raise FileNotFoundError(f"Mock config loader: File not found {file_path}")

    # Create the prompts directory for the mock loader to work if it doesn't exist
    if not os.path.exists("config/prompts"):
        os.makedirs("config/prompts")
        # Create dummy YAML files for the mock loader to "find"
        with open("config/prompts/system_personas.yaml", "w") as f:
            yaml.dump(mock_config_loader("system_personas.yaml"), f)
        with open("config/prompts/cultural_nuances.yaml", "w") as f:
            yaml.dump(mock_config_loader("cultural_nuances.yaml"), f)


    prompt_manager = PromptManager(mock_config_loader)

    # --- Test 1: Get base persona ---
    print("\n--- Test 1: Get base persona ---")
    base_p = prompt_manager.get_base_persona_prompt()
    print(base_p)

    # --- Test 2: Get culturally-adjusted prompt (India) ---
    print("\n--- Test 2: Get culturally-adjusted prompt (India) ---")
    india_nuances = prompt_manager.get_cultural_nuance_prompt("in")
    print(india_nuances)

    # --- Test 3: Get full system prompt with templating ---
    print("\n--- Test 3: Get full system prompt with templating ---")
    full_prompt_india = prompt_manager.get_full_system_prompt(
        persona_name="base_persona",
        country_code="in",
        patient_name="Mr. Sharma"
    )
    print(full_prompt_india)

    # --- Test 4: Get full system prompt (USA) ---
    print("\n--- Test 4: Get full system prompt (USA) ---")
    full_prompt_usa = prompt_manager.get_full_system_prompt(
        persona_name="base_persona",
        country_code="us",
        patient_name="John Doe"
    )
    print(full_prompt_usa)
    
    # Clean up dummy files
    os.remove("config/prompts/system_personas.yaml")
    os.remove("config/prompts/cultural_nuances.yaml")
    os.rmdir("config/prompts")
