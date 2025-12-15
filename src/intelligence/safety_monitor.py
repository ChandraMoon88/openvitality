# src/intelligence/safety_monitor.py

from typing import Dict, Any, List
import re
import asyncio

# Assuming these imports will be available from other modules
# from src.language.profanity_filter import ProfanityFilter
# from src.core.telemetry_emitter import TelemetryEmitter
# from src.intelligence.llm_interface import LLMProvider


class SafetyMonitor:
    """
    Performs real-time safety checks on AI generated outputs to prevent
    medical misinformation, PII disclosure, profanity, and ensure proper
    handling of emergency situations.
    """
    def __init__(self, profanity_filter_instance, telemetry_emitter_instance, llm_provider_instance):
        """
        Initializes the SafetyMonitor with its dependencies.
        
        :param profanity_filter_instance: An initialized ProfanityFilter instance.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        :param llm_provider_instance: An initialized LLMProvider instance (for fact-checking).
        """
        self.profanity_filter = profanity_filter_instance
        self.telemetry = telemetry_emitter_instance
        self.llm_fact_checker = llm_provider_instance # Assuming this LLM can be used for fact-checking
        
        # Regex patterns for common PII. This is NOT exhaustive and should be used with caution.
        # A proper PII detection system would use a dedicated library (e.g., Presidio).
        self.pii_patterns = {
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone_us": r"\b(?:\+?1[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}\b",
            "ssn_us": r"\b\d{3}-\d{2}-\d{4}\b",
            # Add more patterns as needed for different regions/types
        }

        self.emergency_phrases = [
            "call 911", "call 108", "emergency services", "ambulance", "police", "fire department"
        ]
        
        print("✅ SafetyMonitor initialized.")

    async def check_ai_output(self, text: str, session_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs a series of safety checks on the given AI generated text.
        
        :param text: The AI generated text.
        :param session_context: The session context, used for logging and custom rules.
        :return: A dictionary indicating safety status and any detected issues.
        """
        safety_report = {
            "is_safe": True,
            "flags": [],
            "redacted_text": text, # Start with original, redact if needed
            "fallback_response_needed": False
        }
        
        session_id = session_context.get("session_id", "unknown_session")

        # 1. Profanity Check
        if self.profanity_filter.contains_profanity(text):
            safety_report["is_safe"] = False
            safety_report["flags"].append("profanity_detected")
            safety_report["redacted_text"] = self.profanity_filter.censor(text)
            self.telemetry.emit_event("safety_violation", {"session_id": session_id, "type": "profanity", "severity": "medium"})

        # 2. PII Disclosure Check & Redaction
        for pii_type, pattern in self.pii_patterns.items():
            found_pii = False
            for match in re.finditer(pattern, text):
                safety_report["is_safe"] = False
                safety_report["flags"].append(f"pii_disclosure_{pii_type}")
                # Replace with placeholder (e.g., "[REDACTED_EMAIL]")
                safety_report["redacted_text"] = safety_report["redacted_text"].replace(match.group(0), f"[REDACTED_{pii_type.upper()}]")
                found_pii = True
            if found_pii:
                self.telemetry.emit_event("safety_violation", {"session_id": session_id, "type": f"pii_disclosure_{pii_type}", "severity": "high"})

        # 3. Medical Misinformation/Hallucination Check (conceptual)
        # This is a complex task and would typically involve a dedicated fact-checking LLM
        # or a knowledge graph lookup.
        # For this example, we simulate a simple check.
        # If the LLM generates something like "drink bleach for COVID", this would be caught.
        is_misinformation = await self._check_misinformation(text)
        if is_misinformation:
            safety_report["is_safe"] = False
            safety_report["flags"].append("medical_misinformation")
            safety_report["fallback_response_needed"] = True # Critical, require fallback
            self.telemetry.emit_event("safety_violation", {"session_id": session_id, "type": "medical_misinformation", "severity": "critical"})

        # 4. Emergency Phrase Detection (in AI's response)
        for phrase in self.emergency_phrases:
            if phrase in text.lower():
                safety_report["flags"].append("ai_mentioned_emergency")
                self.telemetry.emit_event("safety_alert", {"session_id": session_id, "type": "ai_mentioned_emergency", "details": phrase, "severity": "low"})
                # This might not make the response 'unsafe' but is a flag for monitoring

        # If any critical safety flag is raised, force a fallback response
        if safety_report["fallback_response_needed"]:
            safety_report["redacted_text"] = "I cannot provide that information for safety reasons. Please consult a qualified medical professional."
            
        return safety_report

    async def _check_misinformation(self, text: str) -> bool:
        """
        Simulates checking for medical misinformation using an LLM.
        In a real system, this would involve prompting a highly constrained LLM
        or querying a trusted medical knowledge base.
        
        :param text: The AI generated text.
        :return: True if misinformation is detected, False otherwise.
        """
        # Example: if the text mentions a known harmful "remedy"
        harmful_keywords = ["drink bleach", "cure cancer with magnets", "skip vaccines"]
        for keyword in harmful_keywords:
            if keyword in text.lower():
                print(f"Detected potentially harmful keyword: {keyword}")
                return True
        
        # More realistically, you'd use the LLM to evaluate the claim:
        # prompt = f"Is the following statement medically accurate and safe? '{text}' Answer only 'yes' or 'no'."
        # response = await self.llm_fact_checker.generate_response(prompt, [])
        # return "no" in response.lower()
        
        # For this example, we'll just check for specific phrases.
        return False


# Example Usage
if __name__ == "__main__":
    # --- Mock Dependencies ---
    class MockProfanityFilter:
        def contains_profanity(self, text: str) -> bool:
            return "badword" in text.lower()
        def censor(self, text: str) -> str:
            return text.replace("badword", "****")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {data}")

    class MockLLMProvider: # Only used for fact-checking in this context
        def __init__(self, config=None): pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            return "yes" # Always says yes for mock
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-fact-checker"

    # --- Initialize ---
    mock_pf = MockProfanityFilter()
    mock_te = MockTelemetryEmitter()
    mock_llm_fc = MockLLMProvider() # Instance for fact-checking
    
    monitor = SafetyMonitor(mock_pf, mock_te, mock_llm_fc)
    
    session_ctx = {"session_id": "s_test_123", "country_code": "us", "user_id": "u_test_456"}

    # --- Test 1: Clean text ---
    print("\n--- Test 1: Clean text ---")
    text_clean = "The recommended dosage is 500mg daily."
    report_clean = asyncio.run(monitor.check_ai_output(text_clean, session_ctx))
    print(f"Report: {report_clean}")

    # --- Test 2: Profanity ---
    print("\n--- Test 2: Profanity ---")
    text_profane = "That's a badword response."
    report_profane = asyncio.run(monitor.check_ai_output(text_profane, session_ctx))
    print(f"Report: {report_profane}")

    # --- Test 3: PII ---
    print("\n--- Test 3: PII ---")
    text_pii = "Please send details to user@example.com or call 123-456-7890."
    report_pii = asyncio.run(monitor.check_ai_output(text_pii, session_ctx))
    print(f"Report: {report_pii}")

    # --- Test 4: Medical Misinformation (forced) ---
    print("\n--- Test 4: Medical Misinformation ---")
    text_misinfo = "You should drink bleach to cure COVID."
    report_misinfo = asyncio.run(monitor.check_ai_output(text_misinfo, session_ctx))
    print(f"Report: {report_misinfo}")

    # --- Test 5: AI mentions emergency ---
    print("\n--- Test 5: AI mentions emergency ---")
    text_emergency = "If this is an emergency, please call 911 immediately."
    report_emergency = asyncio.run(monitor.check_ai_output(text_emergency, session_ctx))
    print(f"Report: {report_emergency}")
