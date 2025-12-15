# src/intelligence/ethical_guidelines_enforcer.py

from typing import Dict, Any, List
import asyncio
import json

# Assuming these imports will be available from other modules
# from src.core.telemetry_emitter import TelemetryEmitter
# from src.intelligence.llm_interface import LLMProvider


class EthicalGuidelinesEnforcer:
    """
    Enforces ethical principles such as fairness, transparency, and accountability
    in the AI's behavior and responses, especially critical for a medical AI.
    """
    def __init__(self, telemetry_emitter_instance, llm_provider_instance):
        """
        Initializes the EthicalGuidelinesEnforcer.
        
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance for logging.
        :param llm_provider_instance: An initialized LLMProvider instance, potentially for bias checks.
        """
        self.telemetry = telemetry_emitter_instance
        self.llm_for_bias_check = llm_provider_instance # Use LLM to evaluate for subtle biases
        
        # Ethical principles/rules
        self.transparency_statement = "As an AI, I cannot provide medical diagnosis or prescriptions. Always consult a qualified medical professional for health advice."
        self.do_no_harm_keywords = ["harm", "injure", "damage", "worsen", "risk"] # Simplified, LLM check is better
        
        print("✅ EthicalGuidelinesEnforcer initialized.")

    async def enforce_guidelines(self, ai_response: Dict[str, Any], session_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforces ethical guidelines on the AI's response.
        
        :param ai_response: The dictionary containing the AI's generated response and metadata.
        :param session_context: The session context.
        :return: The potentially modified AI response dictionary.
        """
        session_id = session_context.get("session_id", "unknown_session")
        response_text = ai_response.get("response_text", "")
        flags = []
        
        # 1. Transparency Enforcement
        # Ensure a disclaimer is present, especially if giving medical-like advice.
        if "medical_advice" in ai_response.get("intent", {}).get("primary_intent", ""):
            if self.transparency_statement not in response_text:
                ai_response["response_text"] = f"{response_text.strip()} {self.transparency_statement}"
                flags.append("transparency_disclaimer_added")
                self.telemetry.emit_event("ethical_action", {"session_id": session_id, "type": "transparency_added"})
        elif not any(keyword in response_text.lower() for keyword in self.do_no_harm_keywords): # Heuristic for medical content
            if self.transparency_statement not in response_text:
                ai_response["response_text"] = f"{response_text.strip()} {self.transparency_statement}"
                flags.append("transparency_disclaimer_added_heuristic")
                self.telemetry.emit_event("ethical_action", {"session_id": session_id, "type": "transparency_added_heuristic"})


        # 2. "Do No Harm" Principle (simplified check)
        # This is where outputs from medical_fact_checker would also be considered.
        if "unsafe" in ai_response.get("safety_flags", []):
            flags.append("do_no_harm_violation_safety_flag")
            # The safety monitor should have already handled the response text.
            self.telemetry.emit_event("ethical_violation", {"session_id": session_id, "type": "do_no_harm_violation", "details": "Flagged by safety monitor"})

        # 3. Bias Monitoring (requires LLM-based analysis)
        bias_check_result = await self._check_for_bias(response_text, session_context)
        if bias_check_result["bias_detected"]:
            ai_response["response_text"] = "I need to rephrase that response to ensure fairness. " + ai_response["response_text"]
            flags.append(f"bias_detected: {bias_check_result['bias_type']}")
            self.telemetry.emit_event("ethical_violation", {"session_id": session_id, "type": "bias_detected", "details": bias_check_result})

        ai_response["ethical_flags"] = flags
        self.telemetry.emit_event("ethical_check_complete", {"session_id": session_id, "flags": flags})
        
        return ai_response

    async def _check_for_bias(self, text: str, session_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses an LLM to evaluate the given text for potential biases (e.g., gender, race, socioeconomic).
        This is a complex task and requires a well-designed prompt and possibly a fine-tuned LLM.
        """
        bias_report = {
            "bias_detected": False,
            "bias_type": None,
            "reasoning": ""
        }
        
        # Simulate LLM call for bias detection
        # prompt_for_llm = f"Analyze the following text for potential biases (gender, race, socioeconomic status): '{text}'. If bias is found, identify the type and explain why."
        # llm_analysis = await self.llm_for_bias_check.generate_response(prompt_for_llm, [])
        
        # Simple keyword-based simulation for demonstration
        if "male doctor" in text.lower() and "female nurse" in text.lower():
            bias_report["bias_detected"] = True
            bias_report["bias_type"] = "gender_role_stereotype"
            bias_report["reasoning"] = "Implies traditional gender roles in healthcare professions."
        
        return bias_report

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    class MockLLMProvider: # For bias checking
        def __init__(self, config=None): pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            # Simulate an LLM that sometimes detects bias
            if "male doctor" in prompt.lower() and "female nurse" in prompt.lower():
                return "Bias detected: gender stereotype."
            return "No bias found."
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-bias-checker"

    # --- Initialize ---
    mock_te = MockTelemetryEmitter()
    mock_llm = MockLLMProvider()
    
    enforcer = EthicalGuidelinesEnforcer(mock_te, mock_llm)
    
    session_ctx = {"session_id": "s_ethical_123", "user_id": "u_ethical_456"}

    # --- Test 1: Medical advice, no disclaimer ---
    print("\n--- Test 1: Medical advice, no disclaimer ---")
    ai_resp_1 = {"response_text": "You might have the flu, consider resting.", "intent": {"primary_intent": "medical_advice"}}
    enforced_resp_1 = asyncio.run(enforcer.enforce_guidelines(ai_resp_1, session_ctx))
    print(f"Original: '{ai_resp_1['response_text']}'")
    print(f"Enforced: '{enforced_resp_1['response_text']}'")
    print(f"Flags: {enforced_resp_1['ethical_flags']}")

    # --- Test 2: Contains potential gender bias ---
    print("\n--- Test 2: Contains potential gender bias ---")
    ai_resp_2 = {"response_text": "A male doctor and a female nurse can help you.", "intent": {"primary_intent": "general_info"}}
    enforced_resp_2 = asyncio.run(enforcer.enforce_guidelines(ai_resp_2, session_ctx))
    print(f"Original: '{ai_resp_2['response_text']}'")
    print(f"Enforced: '{enforced_resp_2['response_text']}'")
    print(f"Flags: {enforced_resp_2['ethical_flags']}")

    # --- Test 3: Clean response, no medical context ---
    print("\n--- Test 3: Clean response, no medical context ---")
    ai_resp_3 = {"response_text": "I hope you have a great day!", "intent": {"primary_intent": "small_talk"}}
    enforced_resp_3 = asyncio.run(enforcer.enforce_guidelines(ai_resp_3, session_ctx))
    print(f"Original: '{ai_resp_3['response_text']}'")
    print(f"Enforced: '{enforced_resp_3['response_text']}'")
    print(f"Flags: {enforced_resp_3['ethical_flags']}")
