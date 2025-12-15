# src/intelligence/self_correction.py

from typing import Dict, Any, List
import asyncio
import json

# Assuming these imports will be available from other modules
# from src.intelligence.llm_interface import LLMProvider
# from src.intelligence.safety_monitor import SafetyMonitor
# from src.intelligence.medical_fact_checker import MedicalFactChecker
# from src.core.telemetry_emitter import TelemetryEmitter


class SelfCorrection:
    """
    Enables the AI to identify and correct its own errors, inconsistencies,
    or suboptimal responses to ensure higher quality and safety.
    """
    def __init__(self, llm_provider_instance, safety_monitor_instance, medical_fact_checker_instance, telemetry_emitter_instance):
        """
        Initializes the SelfCorrection module.
        
        :param llm_provider_instance: An initialized LLMProvider instance (for critique and refinement).
        :param safety_monitor_instance: An initialized SafetyMonitor instance for safety feedback.
        :param medical_fact_checker_instance: An initialized MedicalFactChecker instance for accuracy feedback.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance for logging.
        """
        self.llm = llm_provider_instance
        self.safety_monitor = safety_monitor_instance
        self.medical_fact_checker = medical_fact_checker_instance
        self.telemetry = telemetry_emitter_instance
        
        self.max_correction_attempts = 2
        print("✅ SelfCorrection initialized.")

    async def review_and_correct(self, ai_response: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reviews an AI-generated response and attempts to correct it if issues are found.
        
        :param ai_response: The initial AI response dictionary.
        :param context: The overall conversation context (user input, history, etc.).
        :return: The corrected (or original) AI response dictionary.
        """
        original_response_text = ai_response.get("response_text", "")
        current_response_text = original_response_text
        session_id = context.get("session_context", {}).get("session_id", "unknown_session")
        correction_log = []
        
        for attempt in range(self.max_correction_attempts):
            print(f"Self-correction attempt {attempt + 1}...")
            
            # 1. Get feedback from safety monitor
            safety_report = await self.safety_monitor.check_ai_output(current_response_text, context.get("session_context", {}))
            
            # 2. Get feedback from medical fact checker (if medical content)
            medical_fact_check_report = {"verdict": "safe"}
            if "medical_advice" in ai_response.get("intent", {}).get("primary_intent", ""):
                medical_fact_check_report = await self.medical_fact_checker.verify_medical_claim(current_response_text, context)
            
            issues_found = False
            critique_prompt_parts = []
            
            if not safety_report["is_safe"] and safety_report["fallback_response_needed"]:
                issues_found = True
                critique_prompt_parts.append(f"Safety concern: The response was flagged as unsafe due to: {', '.join(safety_report['flags'])}. It suggests a fallback response is needed.")
            elif not safety_report["is_safe"]:
                issues_found = True
                critique_prompt_parts.append(f"Safety concern: The response contains {', '.join(safety_report['flags'])}. Please rephrase to be safe and appropriate.")
            
            if medical_fact_check_report["verdict"] == "unsafe":
                issues_found = True
                critique_prompt_parts.append(f"Accuracy concern: The response contains medically inaccurate or unsafe information. Verdict: '{medical_fact_check_report['verdict']}'. Reasoning: {medical_fact_check_report.get('reasoning')}")
            elif medical_fact_check_report["verdict"] == "uncertain" and medical_fact_check_report["confidence"] < 0.7:
                 issues_found = True
                 critique_prompt_parts.append(f"Uncertainty concern: The medical accuracy of the response is uncertain. Confidence: {medical_fact_check_report['confidence']:.2f}. Please ensure accuracy or state uncertainty.")

            if issues_found:
                # Construct a critique prompt for the LLM
                critique_str = "\n".join(critique_prompt_parts)
                correction_prompt = f"""Review the following AI-generated response carefully for safety, accuracy, and appropriateness, especially in a medical context.

Original Response:
{current_response_text}

Critique:
{critique_str}

Please revise the response to address these issues. If a fallback response is indicated, provide a general safe fallback message.
Revised Response:"""
                
                print("--- Sending critique to LLM for revision ---")
                revised_response = await self.llm.generate_response(
                    prompt=correction_prompt,
                    history=[{"role": "user", "text": context.get("user_input", "")}] # Keep original user prompt
                )
                
                if revised_response and revised_response != current_response_text:
                    correction_log.append({
                        "attempt": attempt + 1,
                        "original_text": current_response_text,
                        "critique": critique_str,
                        "revised_text": revised_response
                    })
                    current_response_text = revised_response
                    self.telemetry.emit_event(
                        "self_correction_applied",
                        {"session_id": session_id, "attempt": attempt + 1, "critique": critique_str}
                    )
                else:
                    print("LLM did not provide a different response after critique. Stopping correction.")
                    break # LLM couldn't improve, break loop
            else:
                print("No critical issues found. No self-correction needed.")
                break # No issues, break loop

        ai_response["response_text"] = current_response_text
        ai_response["self_correction_log"] = correction_log
        ai_response["was_self_corrected"] = bool(correction_log)
        
        if correction_log and issues_found:
            self.telemetry.emit_event(
                "final_response_after_self_correction",
                {"session_id": session_id, "original": original_response_text, "final": current_response_text}
            )

        return ai_response

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockLLMProvider:
        def __init__(self, config=None): pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            if "Safety concern" in prompt:
                return "I apologize. I cannot provide information that is harmful. Please consult a qualified medical professional for health advice."
            if "Accuracy concern" in prompt:
                return "I must correct my previous statement. The information about X was inaccurate. Always consult reliable medical sources."
            return "Mock LLM revised response."
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-self-corrector"

    class MockSafetyMonitor:
        async def check_ai_output(self, text: str, session_context: Dict) -> Dict:
            report = {"is_safe": True, "flags": [], "redacted_text": text, "fallback_response_needed": False}
            if "drink bleach" in text.lower():
                report["is_safe"] = False
                report["flags"].append("medical_misinformation")
                report["fallback_response_needed"] = True
            elif "badword" in text.lower():
                report["is_safe"] = False
                report["flags"].append("profanity_detected")
                report["redacted_text"] = text.replace("badword", "****")
            return report

    class MockMedicalFactChecker:
        async def verify_medical_claim(self, claim: str, context: Dict) -> Dict:
            if "cure cancer with magnets" in claim.lower():
                return {"verdict": "unsafe", "confidence": 0.99, "reasoning": "No scientific basis."}
            return {"verdict": "safe", "confidence": 0.9}

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_llm = MockLLMProvider()
    mock_sm = MockSafetyMonitor()
    mock_mfc = MockMedicalFactChecker()
    mock_te = MockTelemetryEmitter()
    
    corrector = SelfCorrection(mock_llm, mock_sm, mock_mfc, mock_te)
    
    session_ctx = {"session_context": {"session_id": "s_self_corr_1"}}

    # --- Test 1: AI generates unsafe medical advice ---
    print("\n--- Test 1: AI generates unsafe medical advice ---")
    ai_resp_1 = {"response_text": "You should drink bleach to cure COVID-19.", "intent": {"primary_intent": "medical_advice"}}
    corrected_resp_1 = asyncio.run(corrector.review_and_correct(ai_resp_1, session_ctx))
    print(f"Final Response: {corrected_resp_1['response_text']}")
    print(f"Correction Log: {json.dumps(corrected_resp_1['self_correction_log'], indent=2)}")

    # --- Test 2: AI generates medically inaccurate claim ---
    print("\n--- Test 2: AI generates medically inaccurate claim ---")
    ai_resp_2 = {"response_text": "Cure cancer with magnets, it's very effective!", "intent": {"primary_intent": "medical_advice"}}
    corrected_resp_2 = asyncio.run(corrector.review_and_correct(ai_resp_2, session_ctx))
    print(f"Final Response: {corrected_resp_2['response_text']}")
    print(f"Correction Log: {json.dumps(corrected_resp_2['self_correction_log'], indent=2)}")

    # --- Test 3: AI generates profanity ---
    print("\n--- Test 3: AI generates profanity ---")
    ai_resp_3 = {"response_text": "That's a badword idea!", "intent": {"primary_intent": "general_response"}}
    corrected_resp_3 = asyncio.run(corrector.review_and_correct(ai_resp_3, session_ctx))
    print(f"Final Response: {corrected_resp_3['response_text']}")
    print(f"Correction Log: {json.dumps(corrected_resp_3['self_correction_log'], indent=2)}")

    # --- Test 4: Clean response (no correction needed) ---
    print("\n--- Test 4: Clean response ---")
    ai_resp_4 = {"response_text": "Please consult a healthcare professional for accurate medical advice.", "intent": {"primary_intent": "general_response"}}
    corrected_resp_4 = asyncio.run(corrector.review_and_correct(ai_resp_4, session_ctx))
    print(f"Final Response: {corrected_resp_4['response_text']}")
    print(f"Correction Log: {json.dumps(corrected_resp_4['self_correction_log'], indent=2)}")
