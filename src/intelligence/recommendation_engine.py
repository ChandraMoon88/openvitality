# src/intelligence/recommendation_engine.py

from typing import Dict, Any, List
import asyncio

# Assuming these imports will be available from other modules
# from src.intelligence.reasoning_engine import ReasoningEngine
# from src.intelligence.knowledge_graph import KnowledgeGraph
# from src.core.memory_manager import MemoryManager
# from src.intelligence.llm_interface import LLMProvider


class RecommendationEngine:
    """
    Provides personalized, actionable, and safe recommendations based on patient
    profile, current context, and medical knowledge.
    """
    def __init__(self, reasoning_engine_instance, knowledge_graph_instance, memory_manager_instance, llm_provider_instance):
        """
        Initializes the RecommendationEngine.
        
        :param reasoning_engine_instance: An initialized ReasoningEngine instance.
        :param knowledge_graph_instance: An initialized KnowledgeGraph instance.
        :param memory_manager_instance: An initialized MemoryManager instance (for patient history).
        :param llm_provider_instance: An initialized LLMProvider instance for advanced recommendations.
        """
        self.reasoning_engine = reasoning_engine_instance
        self.knowledge_graph = knowledge_graph_instance
        self.memory_manager = memory_manager_instance
        self.llm = llm_provider_instance
        
        # Rule-based recommendations (can be loaded from config)
        self.recommendation_rules = [
            {"condition": "Headache", "duration_days": 3, "recommendation": "Consult a doctor for persistent headache.", "priority": "high"},
            {"condition": "Diabetes", "recommendation": "Monitor blood sugar regularly and follow dietary guidelines.", "priority": "medium"},
            {"symptom": "Fever", "recommendation": "Stay hydrated and get plenty of rest.", "priority": "low"},
            {"action": "Booking Appointment", "recommendation": "Prepare a list of your symptoms and questions for the doctor.", "priority": "low"}
        ]
        
        print("✅ RecommendationEngine initialized.")

    async def get_recommendations(self, patient_profile: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generates a list of personalized recommendations for the user.
        
        :param patient_profile: A dictionary containing patient-specific data (e.g., known conditions, allergies).
        :param context: The current conversation context (user input, session history, extracted entities).
        :return: A list of recommendation dictionaries.
        """
        recommendations: List[Dict[str, Any]] = []
        
        user_id = patient_profile.get("user_id")
        
        # 1. Incorporate reasoning engine conclusions
        inference_result = await self.reasoning_engine.infer(context.get("user_input", ""), context)
        for conclusion in inference_result.get("conclusions", []):
            if conclusion.get("type") == "Possible Condition" and conclusion.get("likelihood") == "high":
                recommendations.append({
                    "type": "Health Suggestion",
                    "text": f"Based on your symptoms, there's a high likelihood of {conclusion['value']}. Consider consulting a doctor for a definitive diagnosis.",
                    "source": "Reasoning Engine",
                    "priority": "high"
                })

        # 2. Rule-based recommendations
        recommendations.extend(self._apply_rule_based_recommendations(patient_profile, context))
        
        # 3. LLM-based personalized recommendations (more advanced)
        llm_based_recs = await self._llm_generate_recommendations(patient_profile, context, inference_result)
        recommendations.extend(llm_based_recs)

        # 4. Integrate relevant long-term memory for follow-up actions
        if user_id:
            follow_ups = await self.memory_manager.get_pending_follow_ups(user_id)
            for fu in follow_ups:
                recommendations.append({
                    "type": "Follow-up Action",
                    "text": f"Reminder: {fu['description']} (Due {fu['due_date']})",
                    "source": "Memory Manager",
                    "priority": "medium"
                })

        # Sort recommendations by priority (high to low)
        recommendations.sort(key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x.get("priority", "low"), 0), reverse=True)
        
        return recommendations

    def _apply_rule_based_recommendations(self, patient_profile: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Applies predefined rules to generate recommendations."""
        rules_based_recs = []
        
        current_symptoms = [e['value'] for e in context.get("entities", []) if e['type'] == 'SYMPTOM']
        current_intents = [context.get("intent", {}).get("primary_intent")]
        
        for rule in self.recommendation_rules:
            # Simple matching logic for conditions/symptoms/actions
            if "condition" in rule and rule["condition"] in patient_profile.get("known_conditions", []):
                rules_based_recs.append({"type": "Rule-Based", "text": rule["recommendation"], "source": "Rules", "priority": rule["priority"]})
            elif "symptom" in rule and rule["symptom"] in current_symptoms:
                rules_based_recs.append({"type": "Rule-Based", "text": rule["recommendation"], "source": "Rules", "priority": rule["priority"]})
            elif "action" in rule and rule["action"] in current_intents:
                 rules_based_recs.append({"type": "Rule-Based", "text": rule["recommendation"], "source": "Rules", "priority": rule["priority"]})

        return rules_based_recs

    async def _llm_generate_recommendations(self, patient_profile: Dict[str, Any], context: Dict[str, Any], inference_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Uses the LLM to generate personalized recommendations based on all available data.
        """
        llm_recs = []
        
        # Construct a detailed prompt for the LLM
        system_prompt = f"""You are a helpful medical assistant. Based on the patient's profile and current interaction,
        provide safe, actionable, and personalized recommendations. Always prioritize patient safety.
        Do not diagnose or prescribe. End with a disclaimer to consult a professional.
        Patient Profile: {patient_profile}
        Conversation Context: {context}
        Reasoning Engine Inferences: {inference_result}"""
        
        user_prompt = "What are 2-3 key recommendations for this patient right now?"
        
        # Call LLM
        llm_response_text = await self.llm.generate_response(user_prompt, [{"role": "system", "text": system_prompt}])
        
        # Parse LLM's response into structured recommendations (e.g., using regex or a simpler LLM for parsing)
        # For simplicity, we'll just return the full text as one recommendation.
        llm_recs.append({
            "type": "Personalized Advice",
            "text": llm_response_text,
            "source": "LLM",
            "priority": "medium" # LLM output is usually medium priority by default
        })
        
        return llm_recs

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockReasoningEngine:
        async def infer(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
            if "headache" in query.lower():
                return {"conclusions": [{"type": "Possible Condition", "value": "Tension Headache", "likelihood": "high"}], "reasoning_steps": ["mock"]}
            if "fever" in query.lower():
                return {"conclusions": [{"type": "Possible Condition", "value": "Common Cold", "likelihood": "medium"}], "reasoning_steps": ["mock"]}
            return {"conclusions": [], "reasoning_steps": ["mock"]}
    
    class MockKnowledgeGraph:
        def __init__(self):
            pass # Not directly used in this example's methods
    
    class MockMemoryManager:
        async def get_pending_follow_ups(self, user_id: str) -> List[Dict]:
            if user_id == "u1":
                return [{"description": "Check blood pressure", "due_date": "2025-01-15"}]
            return []
    
    class MockLLMProvider:
        def __init__(self, config=None):
            pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            return "Consider drinking more water and getting rest. If symptoms persist, please consult a healthcare professional."
        async def count_tokens(self, text: str) -> int:
            return len(text.split())
        def supports_streaming(self) -> bool:
            return False
        def supports_multimodality(self) -> bool:
            return False
        def get_model_name(self) -> str:
            return "mock-llm-recommender"

    # --- Initialize ---
    mock_re = MockReasoningEngine()
    mock_kg = MockKnowledgeGraph()
    mock_mm = MockMemoryManager()
    mock_llm = MockLLMProvider()
    
    engine = RecommendationEngine(mock_re, mock_kg, mock_mm, mock_llm)

    # --- Test 1: Patient with headache and follow-up ---
    print("\n--- Test 1: Patient with headache and follow-up ---")
    patient_profile_1 = {"user_id": "u1", "known_conditions": []}
    context_1 = {"user_input": "I have a headache.", "entities": [{"type": "SYMPTOM", "value": "Headache"}]}
    recs_1 = asyncio.run(engine.get_recommendations(patient_profile_1, context_1))
    print(f"Recommendations for user u1 (headache): {json.dumps(recs_1, indent=2)}")

    # --- Test 2: Patient with fever, no specific history ---
    print("\n--- Test 2: Patient with fever, no specific history ---")
    patient_profile_2 = {"user_id": "u2", "known_conditions": []}
    context_2 = {"user_input": "I have a fever.", "entities": [{"type": "SYMPTOM", "value": "Fever"}]}
    recs_2 = asyncio.run(engine.get_recommendations(patient_profile_2, context_2))
    print(f"Recommendations for user u2 (fever): {json.dumps(recs_2, indent=2)}")

    # --- Test 3: Patient with known diabetes, no current symptoms ---
    print("\n--- Test 3: Patient with known diabetes, no current symptoms ---")
    patient_profile_3 = {"user_id": "u3", "known_conditions": ["Diabetes"]}
    context_3 = {"user_input": "Hello there.", "entities": []}
    recs_3 = asyncio.run(engine.get_recommendations(patient_profile_3, context_3))
    print(f"Recommendations for user u3 (diabetes): {json.dumps(recs_3, indent=2)}")
