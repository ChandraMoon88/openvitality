# src/intelligence/reasoning_engine.py

from typing import Dict, Any, List
import asyncio
import json

# Assuming these imports will be available from other modules
# from src.intelligence.knowledge_graph import KnowledgeGraph
# from src.language.entity_extractor_medical import MedicalEntityExtractor
# from src.intelligence.llm_interface import LLMProvider


class ReasoningEngine:
    """
    Performs logical inference and derives conclusions from facts, especially
    useful for diagnostic support and complex medical queries.
    """
    def __init__(self, knowledge_graph_instance, entity_extractor_instance, llm_provider_instance):
        """
        Initializes the ReasoningEngine.
        
        :param knowledge_graph_instance: An initialized KnowledgeGraph instance.
        :param entity_extractor_instance: An initialized MedicalEntityExtractor instance.
        :param llm_provider_instance: An initialized LLMProvider instance for advanced reasoning.
        """
        self.knowledge_graph = knowledge_graph_instance
        self.entity_extractor = entity_extractor_instance
        self.llm = llm_provider_instance
        
        # Simple rule-based engine (could be loaded from YAML for extensibility)
        self.diagnostic_rules = [
            {"symptoms": ["Frequent Urination", "Increased Thirst"], "condition": "Diabetes", "likelihood": "high"},
            {"symptoms": ["Headache", "Nausea"], "condition": "Migraine", "likelihood": "moderate"},
            {"symptoms": ["Headache"], "condition": "Tension Headache", "likelihood": "low"},
        ]
        
        print("✅ ReasoningEngine initialized.")

    async def infer(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs inference based on a query and provided context.
        
        :param query: The natural language query or statement (e.g., "Given these symptoms, what could it be?").
        :param context: Aggregated context including user input, session history, extracted entities.
        :return: A dictionary containing inferred conclusions, their likelihoods, and reasoning steps.
        """
        inference_result = {
            "query": query,
            "conclusions": [],
            "reasoning_steps": [],
            "confidence": 0.0
        }
        
        # 1. Extract entities from the query and context to ground the reasoning
        all_text_for_entities = query + " " + context.get("user_input", "")
        for msg in context.get("history", []):
            all_text_for_entities += " " + msg.get("text", "")
        
        extracted_entities = self.entity_extractor.extract(all_text_for_entities)
        inference_result["reasoning_steps"].append(f"Extracted entities: {extracted_entities}")

        # 2. Rule-based Diagnostic Support (using extracted symptoms)
        present_symptoms = [e['value'] for e in extracted_entities if e['type'] == 'SYMPTOM']
        if present_symptoms:
            possible_conditions = self._rule_based_diagnose(present_symptoms)
            if possible_conditions:
                inference_result["conclusions"].extend(possible_conditions)
                inference_result["reasoning_steps"].append(f"Rule-based diagnosis: {possible_conditions}")
                inference_result["confidence"] = max(inference_result["confidence"], 0.7) # Rules are fairly confident

        # 3. Knowledge Graph Lookup for related information
        kg_query_results = self.knowledge_graph.query_graph(query)
        if kg_query_results:
            inference_result["reasoning_steps"].append(f"Knowledge graph lookup: {kg_query_results}")
            # Further process KG results to form conclusions
            for item in kg_query_results:
                if item["type"] == "SYMPTOM" and "symptoms of" in query.lower():
                    # If query was about symptoms, and KG found symptoms, add to conclusions
                    inference_result["conclusions"].append({
                        "type": "Associated Symptom",
                        "value": item["entity"]["properties"].get("description"),
                        "likelihood": "high",
                        "source": "Knowledge Graph"
                    })
                    inference_result["confidence"] = max(inference_result["confidence"], 0.8)
                elif item["type"] == "DRUG" and ("drugs for" in query.lower() or "medication for" in query.lower()):
                     inference_result["conclusions"].append({
                        "type": "Treatment Option",
                        "value": item["entity"]["properties"].get("description"),
                        "likelihood": "high",
                        "source": "Knowledge Graph"
                    })
                     inference_result["confidence"] = max(inference_result["confidence"], 0.8)


        # 4. LLM-based Advanced Reasoning (for complex or nuanced queries)
        if not inference_result["conclusions"] or inference_result["confidence"] < 0.8:
            llm_reasoning_output = await self._llm_based_reasoning(query, context, extracted_entities)
            if llm_reasoning_output:
                inference_result["conclusions"].extend(llm_reasoning_output["conclusions"])
                inference_result["reasoning_steps"].append(f"LLM-based reasoning: {llm_reasoning_output['reasoning']}")
                inference_result["confidence"] = max(inference_result["confidence"], llm_reasoning_output["confidence"])

        return inference_result

    def _rule_based_diagnose(self, symptoms: List[str]) -> List[Dict[str, Any]]:
        """
        Applies simple IF-THEN rules for diagnostic suggestions.
        """
        possible_conditions = []
        for rule in self.diagnostic_rules:
            # Check if all symptoms in the rule are present in the user's symptoms
            if all(s in symptoms for s in rule["symptoms"]):
                possible_conditions.append({
                    "type": "Possible Condition",
                    "value": rule["condition"],
                    "likelihood": rule["likelihood"],
                    "source": "Rule-Based Engine"
                })
        return possible_conditions

    async def _llm_based_reasoning(self, query: str, context: Dict[str, Any], extracted_entities: List[Dict]) -> Dict[str, Any]:
        """
        Uses the LLM to perform more complex reasoning or to provide a natural
        language explanation of deductions.
        """
        llm_reasoning_output = {
            "conclusions": [],
            "reasoning": "LLM performed analysis.",
            "confidence": 0.0
        }

        # Construct a prompt for the LLM to perform reasoning
        system_prompt = "You are a medical reasoning assistant. Analyze the given symptoms and context to provide potential conditions or insights."
        user_prompt = f"User query: '{query}'. Context: {json.dumps(context)}. Extracted entities: {json.dumps(extracted_entities)}. What are the most likely conditions or next steps, and why?"
        
        # In a real scenario, LLM would be called here
        # llm_raw_response = await self.llm.generate_response(user_prompt, [{"role": "system", "text": system_prompt}])
        
        # Mock LLM response
        mock_llm_response = ""
        if "diabetes" in query.lower() or "frequent urination" in query.lower():
            mock_llm_response = "Given frequent urination and increased thirst, Diabetes Type 2 is a strong possibility. Further tests are recommended."
            llm_reasoning_output["conclusions"].append({"type": "Possible Condition", "value": "Diabetes Type 2", "likelihood": "high", "source": "LLM"})
            llm_reasoning_output["confidence"] = 0.9
        elif "headache" in query.lower():
            mock_llm_response = "A headache can have many causes. Considering if there's nausea or sensitivity to light might help narrow it down."
            llm_reasoning_output["conclusions"].append({"type": "Advice", "value": "Seek further diagnostic questions", "likelihood": "high", "source": "LLM"})
            llm_reasoning_output["confidence"] = 0.7

        llm_reasoning_output["reasoning"] = mock_llm_response
        return llm_reasoning_output

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockKnowledgeGraph:
        def __init__(self):
            # Simplified mock for entities and relationships
            self.nodes = {
                "Diabetes": {"entity_type": "DISEASE", "properties": {"description": "Diabetes"}, "relationships": {"HAS_SYMPTOM": {"Frequent Urination", "Increased Thirst"}}},
                "Frequent Urination": {"entity_type": "SYMPTOM", "properties": {"description": "Frequent Urination"}},
                "Increased Thirst": {"entity_type": "SYMPTOM", "properties": {"description": "Increased Thirst"}},
                "Headache": {"entity_type": "SYMPTOM", "properties": {"description": "Headache"}},
                "Nausea": {"entity_type": "SYMPTOM", "properties": {"description": "Nausea"}},
                "Aspirin": {"entity_type": "DRUG", "properties": {"description": "Aspirin"}}
            }
        def query_graph(self, query_string: str) -> List[Dict[str, Any]]:
            results = []
            if "symptoms of Diabetes" in query_string:
                results.append({"type": "SYMPTOM", "entity": self.nodes["Frequent Urination"]})
                results.append({"type": "SYMPTOM", "entity": self.nodes["Increased Thirst"]})
            elif "drugs for Headache" in query_string:
                results.append({"type": "DRUG", "entity": self.nodes["Aspirin"]})
            return results

    class MockMedicalEntityExtractor:
        def extract(self, text: str) -> List[Dict]:
            entities = []
            if "frequent urination" in text.lower():
                entities.append({"type": "SYMPTOM", "value": "Frequent Urination"})
            if "increased thirst" in text.lower():
                entities.append({"type": "SYMPTOM", "value": "Increased Thirst"})
            if "headache" in text.lower():
                entities.append({"type": "SYMPTOM", "value": "Headache"})
            if "nausea" in text.lower():
                entities.append({"type": "SYMPTOM", "value": "Nausea"})
            return entities

    class MockLLMProvider:
        def __init__(self, config=None): pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            return "Simulated LLM reasoning."
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-reasoning-llm"

    # --- Initialize ---
    mock_kg = MockKnowledgeGraph()
    mock_ee = MockMedicalEntityExtractor()
    mock_llm = MockLLMProvider()
    
    engine = ReasoningEngine(mock_kg, mock_ee, mock_llm)

    # --- Test 1: Diagnostic support for diabetes symptoms ---
    print("\n--- Test 1: Diagnostic support for diabetes symptoms ---")
    query1 = "I have frequent urination and increased thirst."
    context1 = {"user_input": query1, "history": []}
    result1 = asyncio.run(engine.infer(query1, context1))
    print(f"Result for '{query1}': {json.dumps(result1, indent=2)}")

    # --- Test 2: Diagnostic support for headache with nausea ---
    print("\n--- Test 2: Diagnostic support for headache with nausea ---")
    query2 = "I have a headache and feel nauseous."
    context2 = {"user_input": query2, "history": []}
    result2 = asyncio.run(engine.infer(query2, context2))
    print(f"Result for '{query2}': {json.dumps(result2, indent=2)}")

    # --- Test 3: Query for drugs based on KG ---
    print("\n--- Test 3: Query for drugs based on KG ---")
    query3 = "What are some drugs for Headache?"
    context3 = {"user_input": query3, "history": []}
    result3 = asyncio.run(engine.infer(query3, context3))
    print(f"Result for '{query3}': {json.dumps(result3, indent=2)}")

    # --- Test 4: General query, LLM reasoning ---
    print("\n--- Test 4: General query, LLM reasoning ---")
    query4 = "What should I do if I have a persistent cough?"
    context4 = {"user_input": query4, "history": []}
    result4 = asyncio.run(engine.infer(query4, context4))
    print(f"Result for '{query4}': {json.dumps(result4, indent=2)}")
