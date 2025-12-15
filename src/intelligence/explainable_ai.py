# src/intelligence/explainable_ai.py

from typing import Dict, Any, List
import asyncio
import json

# Assuming these imports will be available from other modules
# from src.intelligence.reasoning_engine import ReasoningEngine
# from src.intelligence.knowledge_graph import KnowledgeGraph
# from src.intelligence.llm_interface import LLMProvider


class ExplainableAI:
    """
    Provides human-readable explanations for the AI's decisions, classifications,
    and recommendations, enhancing transparency and trust, especially in sensitive
    domains like healthcare.
    """
    def __init__(self, reasoning_engine_instance, knowledge_graph_instance, llm_provider_instance):
        """
        Initializes the ExplainableAI module.
        
        :param reasoning_engine_instance: An initialized ReasoningEngine instance.
        :param knowledge_graph_instance: An initialized KnowledgeGraph instance.
        :param llm_provider_instance: An initialized LLMProvider instance for generating natural language explanations.
        """
        self.reasoning_engine = reasoning_engine_instance
        self.knowledge_graph = knowledge_graph_instance
        self.llm = llm_provider_instance
        
        print("✅ ExplainableAI initialized.")

    async def explain_decision(self, decision_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates an explanation for a specific AI decision or recommendation.
        
        :param decision_context: A dictionary containing all relevant information about the decision,
                                 e.g., user input, inferred intent, recommendations, safety flags, etc.
        :return: A dictionary containing the explanation text and breakdown.
        """
        explanation_report = {
            "decision_type": decision_context.get("decision_type", "unknown"),
            "summary_explanation": "Could not generate a specific explanation.",
            "detailed_steps": [],
            "llm_explanation_confidence": 0.0
        }
        
        # Determine what kind of explanation is needed
        decision_type = decision_context.get("decision_type")
        
        if decision_type == "intent_classification":
            explanation_report = await self._explain_intent_classification(decision_context)
        elif decision_type == "recommendation":
            explanation_report = await self._explain_recommendation(decision_context)
        elif decision_type == "safety_flag":
            explanation_report = await self._explain_safety_flag(decision_context)
        elif decision_type == "diagnostic_inference":
            explanation_report = await self._explain_diagnostic_inference(decision_context)
        
        return explanation_report

    async def _explain_intent_classification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Explains why a particular intent was classified."""
        primary_intent = context.get("intent", {}).get("primary_intent")
        user_input = context.get("user_input", "")
        
        explanation = {
            "decision_type": "intent_classification",
            "summary_explanation": f"The AI understood your intent as '{primary_intent}'.",
            "detailed_steps": [f"You said: '{user_input}'"],
            "llm_explanation_confidence": 0.8
        }
        
        # Use LLM to elaborate
        llm_prompt = f"Explain in simple terms why the phrase '{user_input}' might be classified as '{primary_intent}'. Focus on keywords or patterns."
        llm_explanation = await self.llm.generate_response(llm_prompt, [])
        explanation["detailed_steps"].append(f"LLM insight: {llm_explanation}")
        
        return explanation

    async def _explain_recommendation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Explains the rationale behind a given recommendation."""
        recommendation = context.get("recommendation", {})
        patient_profile = context.get("patient_profile", {})
        
        explanation = {
            "decision_type": "recommendation",
            "summary_explanation": f"The AI recommended '{recommendation.get('text')}'",
            "detailed_steps": [f"Based on your profile: {json.dumps(patient_profile)}"],
            "llm_explanation_confidence": 0.85
        }
        
        # Integrate reasoning engine's output
        if context.get("inference_result"):
            explanation["detailed_steps"].append(f"Reasoning engine concluded: {context['inference_result'].get('conclusions')}")
            explanation["detailed_steps"].append(f"Reasoning steps: {context['inference_result'].get('reasoning_steps')}")
        
        # Integrate knowledge graph evidence
        if recommendation.get("source") == "Knowledge Graph":
            explanation["detailed_steps"].append(f"Supported by medical facts from Knowledge Graph.")
            
        llm_prompt = f"Explain the medical rationale for recommending '{recommendation.get('text')}' given the patient profile {json.dumps(patient_profile)} and any inferred conditions."
        llm_explanation = await self.llm.generate_response(llm_prompt, [])
        explanation["detailed_steps"].append(f"LLM insight: {llm_explanation}")
        
        return explanation

    async def _explain_safety_flag(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Explains why a safety flag was raised."""
        flag_type = context.get("flag_type")
        flag_details = context.get("flag_details", {})
        original_text = context.get("original_text", "")

        explanation = {
            "decision_type": "safety_flag",
            "summary_explanation": f"A safety flag was raised for '{flag_type}'.",
            "detailed_steps": [f"Original text: '{original_text}'"],
            "llm_explanation_confidence": 0.9
        }
        
        if flag_type == "profanity_detected":
            explanation["detailed_steps"].append("Inappropriate language was detected.")
        elif flag_type == "pii_disclosure":
            explanation["detailed_steps"].append(f"Personal Identifiable Information (PII) of type '{flag_details.get('pii_type')}' was detected and redacted.")
        elif flag_type == "medical_misinformation":
            explanation["detailed_steps"].append(f"The statement '{original_text}' was flagged as potentially medically inaccurate or harmful based on fact-checking.")
            
        llm_prompt = f"Explain why {flag_type} is a safety concern in a medical AI context, referring to the text '{original_text}' if applicable."
        llm_explanation = await self.llm.generate_response(llm_prompt, [])
        explanation["detailed_steps"].append(f"LLM context: {llm_explanation}")
        
        return explanation

    async def _explain_diagnostic_inference(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Explains how a diagnostic inference was made."""
        inference = context.get("inference", {})
        user_input = context.get("user_input", "")

        explanation = {
            "decision_type": "diagnostic_inference",
            "summary_explanation": f"The AI inferred potential conditions based on your symptoms.",
            "detailed_steps": [f"Your input: '{user_input}'"],
            "llm_explanation_confidence": 0.8
        }
        
        for conclusion in inference.get("conclusions", []):
            explanation["detailed_steps"].append(f"Conclusion: {conclusion.get('value')} (Likelihood: {conclusion.get('likelihood')}) from {conclusion.get('source')}.")
        
        for step in inference.get("reasoning_steps", []):
            explanation["detailed_steps"].append(f"Reasoning Step: {step}")
            
        llm_prompt = f"Based on symptoms like '{user_input}', explain how medical AI might infer conditions like '{', '.join([c.get('value') for c in inference.get('conclusions', [])])}'."
        llm_explanation = await self.llm.generate_response(llm_prompt, [])
        explanation["detailed_steps"].append(f"LLM synthesis: {llm_explanation}")

        return explanation


# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockReasoningEngine:
        async def infer(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
            if "headache" in query.lower():
                return {
                    "conclusions": [{"type": "Possible Condition", "value": "Tension Headache", "likelihood": "high", "source": "Rule-Based Engine"}],
                    "reasoning_steps": ["Extracted entity: Headache", "Rule matched: Headache -> Tension Headache"],
                    "confidence": 0.8
                }
            return {"conclusions": [], "reasoning_steps": [], "confidence": 0.0}

    class MockKnowledgeGraph:
        def __init__(self):
            pass # Not directly used in explanation generation example
    
    class MockLLMProvider:
        def __init__(self, config=None):
            pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            if "explain in simple terms why the phrase" in prompt:
                return "The AI looked for keywords like 'headache' and identified it as a symptom report."
            if "medical rationale for recommending" in prompt:
                return "This recommendation is based on general health guidelines for fever."
            if "explain why medical_misinformation is a safety concern" in prompt:
                return "Medical misinformation is dangerous as it can lead to incorrect self-treatment."
            if "explain how medical AI might infer conditions" in prompt:
                return "AI uses patterns in symptoms to suggest common conditions."
            return "Mock LLM explanation."
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-explainer"

    # --- Initialize ---
    mock_re = MockReasoningEngine()
    mock_kg = MockKnowledgeGraph()
    mock_llm = MockLLMProvider()
    
    explainer = ExplainableAI(mock_re, mock_kg, mock_llm)

    # --- Test 1: Explain intent classification ---
    print("\n--- Test 1: Explain intent classification ---")
    intent_context = {
        "decision_type": "intent_classification",
        "user_input": "I have a headache.",
        "intent": {"primary_intent": "symptom_report", "confidence": 0.9}
    }
    explanation_1 = asyncio.run(explainer.explain_decision(intent_context))
    print(f"Explanation for intent: {json.dumps(explanation_1, indent=2)}")

    # --- Test 2: Explain a recommendation ---
    print("\n--- Test 2: Explain a recommendation ---")
    recommendation_context = {
        "decision_type": "recommendation",
        "recommendation": {"text": "Stay hydrated and get plenty of rest.", "source": "Rule-Based", "priority": "low"},
        "patient_profile": {"user_id": "u1", "known_conditions": []},
        "inference_result": {"conclusions": [{"type": "Possible Condition", "value": "Common Cold", "likelihood": "medium"}], "reasoning_steps": ["mock"]}
    }
    explanation_2 = asyncio.run(explainer.explain_decision(recommendation_context))
    print(f"Explanation for recommendation: {json.dumps(explanation_2, indent=2)}")

    # --- Test 3: Explain a safety flag ---
    print("\n--- Test 3: Explain a safety flag ---")
    safety_context = {
        "decision_type": "safety_flag",
        "flag_type": "medical_misinformation",
        "flag_details": {"claim": "Drink bleach to cure COVID.",},
        "original_text": "AI suggested to drink bleach to cure COVID."
    }
    explanation_3 = asyncio.run(explainer.explain_decision(safety_context))
    print(f"Explanation for safety flag: {json.dumps(explanation_3, indent=2)}")

    # --- Test 4: Explain diagnostic inference ---
    print("\n--- Test 4: Explain diagnostic inference ---")
    diagnostic_inference_context = {
        "decision_type": "diagnostic_inference",
        "user_input": "I have a terrible headache.",
        "inference": asyncio.run(mock_re.infer("I have a terrible headache.", {}))
    }
    explanation_4 = asyncio.run(explainer.explain_decision(diagnostic_inference_context))
    print(f"Explanation for diagnostic inference: {json.dumps(explanation_4, indent=2)}")
