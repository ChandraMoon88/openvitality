# src/intelligence/response_generator.py

from typing import List, Dict, Any
import asyncio

# Assuming these imports will be available from other modules
# from src.intelligence.llm_factory import get_llm_provider
# from src.intelligence.prompt_manager import PromptManager
# from src.language.profanity_filter import ProfanityFilter
# from src.core.telemetry_emitter import TelemetryEmitter


class ResponseGenerator:
    """
    Orchestrates the generation of AI responses, combining LLM calls with safety checks,
    cultural context, and persona adherence.
    """
    def __init__(self, llm_provider_instance, prompt_manager_instance, profanity_filter_instance, telemetry_emitter_instance):
        """
        Initializes the ResponseGenerator with instances of its dependencies.
        
        :param llm_provider_instance: An initialized LLMProvider instance.
        :param prompt_manager_instance: An initialized PromptManager instance.
        :param profanity_filter_instance: An initialized ProfanityFilter instance.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.llm = llm_provider_instance
        self.prompt_manager = prompt_manager_instance
        self.profanity_filter = profanity_filter_instance
        self.telemetry = telemetry_emitter_instance
        print("✅ ResponseGenerator initialized.")

    async def generate_ai_response(self, user_input: str, history: List[Dict], session_context: Dict) -> Dict[str, Any]:
        """
        Generates an AI response based on user input, conversation history, and session context.
        
        :param user_input: The current text input from the user.
        :param history: The conversation history (list of {"role": str, "text": str}).
        :param session_context: A dictionary containing session-specific information
                                (e.g., detected_language, country_code, patient_name, current_persona).
        :return: A dictionary containing the AI's response and metadata.
        """
        response_data = {
            "response_text": "",
            "detected_language": session_context.get("detected_language", "en"),
            "safety_flags": [],
            "error": None
        }

        try:
            # 1. Apply profanity filter to user input
            if self.profanity_filter.contains_profanity(user_input):
                response_data["safety_flags"].append("profanity_detected_user")
                response_data["response_text"] = "I cannot process requests containing inappropriate language. Please rephrase."
                self.telemetry.emit_event("profanity_detected", {"source": "user_input", "session_id": session_context.get("session_id")})
                return response_data

            # 2. Build the system prompt using PromptManager
            country_code = session_context.get("country_code")
            persona_name = session_context.get("current_persona", "base_persona")
            system_prompt = self.prompt_manager.get_full_system_prompt(
                persona_name=persona_name,
                country_code=country_code,
                **session_context # Pass other context for templating
            )

            # Prepend system prompt to history for LLM
            llm_history = [{"role": "system", "text": system_prompt}] + history

            # 3. Generate response using LLM
            llm_response = await self.llm.generate_response(user_input, llm_history)

            # 4. Apply profanity filter to AI response (self-censor)
            if self.profanity_filter.contains_profanity(llm_response):
                response_data["safety_flags"].append("profanity_detected_ai")
                response_data["response_text"] = self.profanity_filter.censor(llm_response)
                self.telemetry.emit_event("profanity_detected", {"source": "ai_output", "session_id": session_context.get("session_id")})
            else:
                response_data["response_text"] = llm_response

            # 5. Emit telemetry for the generated response
            self.telemetry.emit_event(
                "response_generated",
                {
                    "session_id": session_context.get("session_id"),
                    "llm_model": self.llm.get_model_name(),
                    "response_length": len(llm_response),
                    "safety_flags": response_data["safety_flags"]
                }
            )

        except Exception as e:
            print(f"🚨 Error during AI response generation: {e}")
            response_data["error"] = str(e)
            response_data["response_text"] = "I apologize, but I encountered a technical issue. Please try again later."
            self.telemetry.emit_event("response_generation_error", {"error": str(e), "session_id": session_context.get("session_id")})
        
        return response_data

# Example Usage (with mock dependencies)
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockLLMProvider:
        def __init__(self, config):
            self.model_name = config.get('llm_model', 'mock-llm')
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            print(f"Mock LLM received prompt: {prompt}")
            print(f"Mock LLM received history: {history}")
            if "technical issue" in prompt:
                raise ValueError("Simulated LLM error")
            return f"Mock AI response to: '{prompt}'"
        def get_model_name(self): return self.model_name

    class MockPromptManager:
        def get_full_system_prompt(self, persona_name: str, country_code: str = None, **kwargs) -> str:
            base = f"You are {persona_name}. "
            cultural = f"Cultural context for {country_code or 'none'}. "
            templated = f"Patient: {kwargs.get('patient_name', 'N/A')}. "
            return base + cultural + templated

    class MockProfanityFilter:
        def contains_profanity(self, text: str) -> bool:
            return "badword" in text.lower()
        def censor(self, text: str) -> str:
            return text.replace("badword", "****")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {data}")

    # --- Initialize ---
    mock_llm = MockLLMProvider({"llm_model": "gemini-1.5-flash"})
    mock_pm = MockPromptManager()
    mock_pf = MockProfanityFilter()
    mock_te = MockTelemetryEmitter()

    generator = ResponseGenerator(mock_llm, mock_pm, mock_pf, mock_te)

    # --- Test 1: Normal interaction ---
    print("\n--- Test 1: Normal interaction ---")
    session_ctx = {"session_id": "s1", "detected_language": "en", "country_code": "us", "patient_name": "Alice"}
    history_norm = [{"role": "user", "text": "Hello"}, {"role": "assistant", "text": "Hi Alice!"}]
    response_norm = asyncio.run(generator.generate_ai_response("How are you feeling?", history_norm, session_ctx))
    print(f"Final Response: {response_norm}")

    # --- Test 2: User profanity ---
    print("\n--- Test 2: User profanity ---")
    response_profane_user = asyncio.run(generator.generate_ai_response("You are a badword!", history_norm, session_ctx))
    print(f"Final Response (User Profanity): {response_profane_user}")

    # --- Test 3: LLM error ---
    print("\n--- Test 3: LLM error ---")
    response_llm_error = asyncio.run(generator.generate_ai_response("Simulate technical issue", history_norm, session_ctx))
    print(f"Final Response (LLM Error): {response_llm_error}")

    # --- Test 4: LLM generates profanity (should be censored) ---
    print("\n--- Test 4: LLM generates profanity (censored) ---")
    class MockProfaneLLM(MockLLMProvider):
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            return "This is a badword response from the AI."
    
    profane_llm = MockProfaneLLM({"llm_model": "mock-profane-llm"})
    profane_generator = ResponseGenerator(profane_llm, mock_pm, mock_pf, mock_te)
    response_profane_ai = asyncio.run(profane_generator.generate_ai_response("Give me a response.", history_norm, session_ctx))
    print(f"Final Response (AI Profanity): {response_profane_ai}")
