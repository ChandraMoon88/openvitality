# src/intelligence/personalized_medicine_engine.py

from typing import Dict, Any, List
import asyncio
import json
import datetime

# Assuming these imports will be available from other modules
# from src.intelligence.knowledge_graph import KnowledgeGraph
# from src.intelligence.reasoning_engine import ReasoningEngine
# from src.intelligence.recommendation_engine import RecommendationEngine
# from src.intelligence.causal_inference import CausalInference
# from src.core.memory_manager import MemoryManager
# from src.intelligence.llm_interface import LLMProvider
# from src.intelligence.ethical_guidelines_enforcer import EthicalGuidelinesEnforcer


class PersonalizedMedicineEngine:
    """
    Provides highly individualized medical advice and treatment plans based on
    a patient's unique profile, integrating various AI capabilities.
    """
    def __init__(self, kg_instance, re_instance, rec_engine_instance, ci_instance, mm_instance, llm_instance, ethical_enforcer_instance):
        """
        Initializes the PersonalizedMedicineEngine with all its core dependencies.
        """
        self.knowledge_graph = kg_instance
        self.reasoning_engine = re_instance
        self.recommendation_engine = rec_engine_instance
        self.causal_inference = ci_instance
        self.memory_manager = mm_instance
        self.llm = llm_instance
        self.ethical_enforcer = ethical_enforcer_instance
        
        print("✅ PersonalizedMedicineEngine initialized.")

    async def generate_personalized_plan(self, patient_profile: Dict[str, Any], current_symptoms: List[str], current_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a highly individualized medical advice and treatment plan.
        
        :param patient_profile: A dictionary containing the patient's unique profile (genetics, history, lifestyle).
                                Example: {"user_id": "p123", "age": 45, "gender": "female", "genetics": {"BRCA1": "negative"},
                                          "medical_history": ["Hypertension"], "allergies": ["Penicillin"], "lifestyle": {"smoking": "no"}}
        :param current_symptoms: A list of the patient's currently reported symptoms.
        :param current_context: The current conversation context from the user.
        :return: A dictionary containing the personalized plan, including insights and recommendations.
        """
        personalized_plan = {
            "patient_id": patient_profile.get("user_id"),
            "timestamp": datetime.datetime.now().isoformat(),
            "insights": [],
            "potential_conditions": [],
            "recommendations": [],
            "ethical_review": {}
        }
        
        # 1. Retrieve comprehensive patient history from MemoryManager
        full_patient_history = await self.memory_manager.get_full_patient_record(patient_profile.get("user_id"))
        
        # Merge current profile with full history
        combined_profile = {**full_patient_history, **patient_profile, "current_symptoms": current_symptoms}

        # 2. Reasoning Engine: Infer potential conditions based on symptoms & history
        inference_query = f"Given patient's profile: {json.dumps(combined_profile)}, and current symptoms: {', '.join(current_symptoms)}. What are potential conditions?"
        inference_result = await self.reasoning_engine.infer(inference_query, current_context)
        
        personalized_plan["potential_conditions"].extend(inference_result.get("conclusions", []))
        personalized_plan["insights"].append(f"Reasoning: {inference_result.get('reasoning_steps')}")

        # 3. Causal Inference: Analyze potential cause-effect for conditions
        causal_analysis = await self.causal_inference.analyze_causality(
            data={"patient_profile": combined_profile, "current_symptoms": current_symptoms},
            hypothesis="What are the likely causes of these symptoms in this patient?"
        )
        personalized_plan["insights"].append(f"Causal Analysis: {causal_analysis.get('inferred_causal_links')}, Limitations: {causal_analysis.get('limitations')}")

        # 4. Recommendation Engine: Generate tailored recommendations
        recommendations = await self.recommendation_engine.get_recommendations(patient_profile, current_context)
        personalized_plan["recommendations"].extend(recommendations)
        
        # 5. LLM Synthesis for a coherent plan
        final_plan_text = await self._llm_synthesize_plan(combined_profile, personalized_plan)
        personalized_plan["summary_plan_text"] = final_plan_text

        # 6. Ethical Review of the generated plan
        # The ethical enforcer would check the final plan text and recommendations for bias, safety, etc.
        ethical_review_result = await self.ethical_enforcer.enforce_guidelines(
            {"response_text": final_plan_text, "recommendations": recommendations, "intent": {"primary_intent": "personalized_plan"}},
            current_context # Pass full current_context for session_id etc.
        )
        personalized_plan["ethical_review"] = ethical_review_result
        if not ethical_review_result.get("is_safe", True) or ethical_review_result.get("ethical_flags"):
            print(f"⚠️ Ethical concerns detected in personalized plan for {patient_profile.get('user_id')}.")

        return personalized_plan

    async def _llm_synthesize_plan(self, combined_profile: Dict[str, Any], interim_plan: Dict[str, Any]) -> str:
        """
        Uses the LLM to synthesize all insights and recommendations into a coherent,
        human-readable personalized plan.
        """
        system_prompt = f"""You are a medical AI assistant tasked with synthesizing a personalized health plan.
        Based on the patient's unique profile, current symptoms, and AI analyses, provide a concise, actionable plan.
        Crucially, always include a disclaimer that this is AI-generated advice and not a replacement for a medical professional.
        Patient Profile: {json.dumps(combined_profile, indent=2)}
        AI Analyses (Inferences, Causal Links, Recommendations): {json.dumps(interim_plan, indent=2)}
        """
        
        user_prompt = "Generate a clear, polite, and comprehensive personalized health plan based on the above information. Focus on actionable advice."
        
        llm_response = await self.llm.generate_response(user_prompt, [{"role": "system", "text": system_prompt}])
        return llm_response


# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockKnowledgeGraph:
        def __init__(self):
            pass
    class MockReasoningEngine:
        async def infer(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
            if "diabetes" in query.lower():
                return {"conclusions": [{"type": "Possible Condition", "value": "Diabetes Mellitus Type 2", "likelihood": "high"}], "reasoning_steps": ["mock-re"]}
            if "headache" in query.lower():
                return {"conclusions": [{"type": "Possible Condition", "value": "Tension Headache", "likelihood": "medium"}], "reasoning_steps": ["mock-re"]}
            return {"conclusions": [], "reasoning_steps": ["mock-re"]}
    class MockRecommendationEngine:
        async def get_recommendations(self, patient_profile: Dict, context: Dict) -> List[Dict]:
            if "Diabetes" in str(patient_profile):
                return [{"type": "Action", "text": "Consult an endocrinologist.", "priority": "high"}]
            if "Tension Headache" in str(context):
                return [{"type": "Advice", "text": "Try relaxation techniques and over-the-counter pain relievers.", "priority": "medium"}]
            return []
    class MockCausalInference:
        async def analyze_causality(self, data: Dict, hypothesis: str = None) -> Dict:
            if "Hypertension" in str(data):
                return {"inferred_causal_links": [{"cause": "Unhealthy Diet", "effect": "Hypertension", "likelihood": "high"}], "limitations": []}
            return {"inferred_causal_links": [], "limitations": ["mock-ci"]}
    class MockMemoryManager:
        async def get_full_patient_record(self, user_id: str) -> Dict:
            if user_id == "p123":
                return {"user_id": "p123", "medical_history": ["Hypertension"], "allergies": []}
            return {"user_id": user_id}
    class MockLLMProvider:
        def __init__(self, config=None):
            pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            return "This is a synthesized personalized health plan. Remember to consult your doctor."
        async def count_tokens(self, text: str) -> int:
            return len(text.split())
        def supports_streaming(self) -> bool:
            return False
        def supports_multimodality(self) -> bool:
            return False
        def get_model_name(self) -> str:
            return "mock-llm-planner"
    class MockEthicalGuidelinesEnforcer:
        def __init__(self, te_instance=None, llm_instance=None):
            pass
        async def enforce_guidelines(self, ai_response: Dict, session_context: Dict) -> Dict:
            ai_response["ethical_flags"] = []
            ai_response["is_safe"] = True
            return ai_response

    # --- Initialize ---
    mock_kg = MockKnowledgeGraph()
    mock_re = MockReasoningEngine()
    mock_rec_eng = MockRecommendationEngine()
    mock_ci = MockCausalInference()
    mock_mm = MockMemoryManager()
    mock_llm = MockLLMProvider()
    mock_ethical = MockEthicalGuidelinesEnforcer() # Needs telemetry and llm, but mocked for simplicity
    
    engine = PersonalizedMedicineEngine(mock_kg, mock_re, mock_rec_eng, mock_ci, mock_mm, mock_llm, mock_ethical)

    # --- Test 1: Patient with known hypertension and new headache ---
    print("\n--- Test 1: Patient with known hypertension and new headache ---")
    patient_profile_1 = {"user_id": "p123", "age": 45, "gender": "female", "lifestyle": {"smoking": "no"}}
    current_symptoms_1 = ["headache"]
    current_context_1 = {"user_input": "I have a new headache.", "session_id": "s_pme_1"}
    
    plan_1 = asyncio.run(engine.generate_personalized_plan(patient_profile_1, current_symptoms_1, current_context_1))
    print(f"Personalized Plan 1: {json.dumps(plan_1, indent=2)}")

    # --- Test 2: Patient with new symptoms (diabetes-like) ---
    print("\n--- Test 2: Patient with new symptoms (diabetes-like) ---")
    patient_profile_2 = {"user_id": "p124", "age": 60, "gender": "male"}
    current_symptoms_2 = ["frequent urination", "increased thirst"]
    current_context_2 = {"user_input": "I am always thirsty and urinate a lot.", "session_id": "s_pme_2"}
    
    plan_2 = asyncio.run(engine.generate_personalized_plan(patient_profile_2, current_symptoms_2, current_context_2))
    print(f"Personalized Plan 2: {json.dumps(plan_2, indent=2)}")
