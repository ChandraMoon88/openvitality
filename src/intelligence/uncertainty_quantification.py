# src/intelligence/uncertainty_quantification.py

from typing import Dict, Any, List
import numpy as np
import random
import json

# Assuming these imports will be available from other modules
# from src.intelligence.llm_interface import LLMProvider


class UncertaintyQuantification:
    """
    Measures and communicates the AI's confidence in its predictions, inferences,
    and recommendations. This is critical for transparency and knowing when to
    escalate to a human in a medical context.
    """
    def __init__(self, llm_provider_instance):
        """
        Initializes the UncertaintyQuantification module.
        
        :param llm_provider_instance: An initialized LLMProvider instance, potentially for calibration.
        """
        self.llm = llm_provider_instance
        
        # Thresholds for what constitutes "high", "medium", "low" uncertainty
        self.uncertainty_thresholds = {
            "high": 0.3,  # Probability of error > 30%
            "medium": 0.1, # Probability of error between 10-30%
            "low": 0.05  # Probability of error < 5%
        }
        print("✅ UncertaintyQuantification initialized.")

    async def quantify_uncertainty(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Quantifies the uncertainty associated with a given AI prediction or output.
        
        :param prediction: A dictionary containing the prediction, typically including a 'confidence' score.
                          Example: {"type": "intent_classification", "value": "symptom_report", "confidence": 0.85}
        :return: A dictionary detailing the uncertainty, including a qualitative level.
        """
        uncertainty_report = {
            "prediction_type": prediction.get("type", "unknown"),
            "original_confidence": prediction.get("confidence", 1.0),
            "uncertainty_score": 0.0, # Higher score means more uncertain
            "uncertainty_level": "unknown", # high, medium, low
            "reasoning": []
        }
        
        original_confidence = prediction.get("confidence", 0.5) # Default to 0.5 if not provided
        
        # Simple inversion: uncertainty = 1 - confidence
        uncertainty_score = 1.0 - original_confidence
        uncertainty_report["uncertainty_score"] = uncertainty_score

        # Determine qualitative level
        if uncertainty_score > self.uncertainty_thresholds["high"]:
            uncertainty_report["uncertainty_level"] = "high"
            uncertainty_report["reasoning"].append("High uncertainty: Prediction confidence is very low.")
        elif uncertainty_score > self.uncertainty_thresholds["medium"]:
            uncertainty_report["uncertainty_level"] = "medium"
            uncertainty_report["reasoning"].append("Medium uncertainty: Prediction confidence is moderate.")
        elif uncertainty_score > self.uncertainty_thresholds["low"]:
            uncertainty_report["uncertainty_level"] = "low"
            uncertainty_report["reasoning"].append("Low uncertainty: Prediction confidence is relatively high.")
        else:
            uncertainty_report["uncertainty_level"] = "very_low"
            uncertainty_report["reasoning"].append("Very low uncertainty: Prediction confidence is high.")
        
        # More advanced methods would involve:
        # - Monte Carlo Dropout: Running the model multiple times with dropout enabled
        # - Ensemble Methods: Combining multiple models and measuring disagreement
        # - LLM-based self-assessment: Asking an LLM to rate its own confidence
        
        # Simulate LLM-based self-assessment for complex cases
        if uncertainty_score > self.uncertainty_thresholds["low"]:
            llm_uncertainty_assessment = await self._llm_assess_uncertainty(prediction)
            if llm_uncertainty_assessment:
                uncertainty_report["reasoning"].append(f"LLM Assessment: {llm_uncertainty_assessment}")

        return uncertainty_report

    async def _llm_assess_uncertainty(self, prediction: Dict[str, Any]) -> str:
        """
        Uses an LLM to provide a qualitative assessment of uncertainty,
        especially for predictions that are hard to quantify numerically.
        """
        # Construct a prompt for the LLM
        prompt = f"""Given the AI's prediction: {json.dumps(prediction)}.
        Consider typical challenges in AI for this type of prediction (e.g., ambiguity in user input, rare medical condition, complex interaction).
        How certain do you think an AI should be about this prediction? Provide a brief qualitative assessment (e.g., 'The input was ambiguous', 'This is a rare condition so data might be limited').
        Answer concisely."""
        
        llm_response = await self.llm.generate_response(prompt, [])
        return llm_response

    async def adjust_behavior_based_on_uncertainty(self, uncertainty_report: Dict[str, Any], current_action: str) -> str:
        """
        Adjusts AI behavior based on the quantified uncertainty.
        
        :param uncertainty_report: The report from `quantify_uncertainty`.
        :param current_action: The action the AI was about to take.
        :return: The adjusted action or a recommendation for escalation.
        """
        uncertainty_level = uncertainty_report["uncertainty_level"]
        
        if uncertainty_level == "high":
            print(f"HIGH uncertainty detected for {uncertainty_report['prediction_type']}. Escalating.")
            return "escalate_to_human"
        elif uncertainty_level == "medium":
            print(f"MEDIUM uncertainty detected for {uncertainty_report['prediction_type']}. Asking for clarification.")
            # In a real system, generate a clarifying question using LLM
            return "ask_for_clarification"
        elif uncertainty_level == "low":
            print(f"LOW uncertainty detected for {uncertainty_report['prediction_type']}. Proceeding with action.")
            return current_action
        else: # very_low or unknown
            return current_action


# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockLLMProvider:
        def __init__(self, config=None): pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            if "ambiguity in user input" in prompt:
                return "The user's symptoms were vague and could point to multiple conditions."
            return "LLM thinks this prediction is straightforward."
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-uncertainty"

    # --- Initialize ---
    mock_llm = MockLLMProvider()
    quantifier = UncertaintyQuantification(mock_llm)

    # --- Test 1: High confidence prediction (low uncertainty) ---
    print("\n--- Test 1: High confidence prediction ---")
    pred1 = {"type": "intent_classification", "value": "medical_emergency", "confidence": 0.98}
    report1 = asyncio.run(quantifier.quantify_uncertainty(pred1))
    print(f"Uncertainty Report: {json.dumps(report1, indent=2)}")
    action1 = asyncio.run(quantifier.adjust_behavior_based_on_uncertainty(report1, "route_to_emergency_agent"))
    print(f"Adjusted action: {action1}")

    # --- Test 2: Medium confidence prediction (medium uncertainty) ---
    print("\n--- Test 2: Medium confidence prediction ---")
    pred2 = {"type": "entity_extraction", "value": "Aspirin", "confidence": 0.75} # Thresholds: low=0.05, medium=0.1, high=0.3
    report2 = asyncio.run(quantifier.quantify_uncertainty(pred2))
    print(f"Uncertainty Report: {json.dumps(report2, indent=2)}")
    action2 = asyncio.run(quantifier.adjust_behavior_based_on_uncertainty(report2, "proceed_with_drug_info"))
    print(f"Adjusted action: {action2}")

    # --- Test 3: Low confidence prediction (high uncertainty) ---
    print("\n--- Test 3: Low confidence prediction ---")
    pred3 = {"type": "reasoning_inference", "value": "Possible diagnosis: Rare disease X", "confidence": 0.2}
    report3 = asyncio.run(quantifier.quantify_uncertainty(pred3))
    print(f"Uncertainty Report: {json.dumps(report3, indent=2)}")
    action3 = asyncio.run(quantifier.adjust_behavior_based_on_uncertainty(report3, "provide_diagnosis"))
    print(f"Adjusted action: {action3}")

    # --- Test 4: Prediction with no confidence score (default to medium) ---
    print("\n--- Test 4: Prediction with no confidence score ---")
    pred4 = {"type": "medical_fact_check", "value": "Claim: XYZ is true."}
    report4 = asyncio.run(quantifier.quantify_uncertainty(pred4))
    print(f"Uncertainty Report: {json.dumps(report4, indent=2)}")
    action4 = asyncio.run(quantifier.adjust_behavior_based_on_uncertainty(report4, "state_fact"))
    print(f"Adjusted action: {action4}")
