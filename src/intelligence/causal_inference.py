# src/intelligence/causal_inference.py

from typing import Dict, Any, List
import asyncio
import json
import random

# Assuming these imports will be available from other modules
# from src.intelligence.llm_interface import LLMProvider
# from src.intelligence.knowledge_graph import KnowledgeGraph # For known causal links


class CausalInference:
    """
    Focuses on understanding cause-and-effect relationships in medical data,
    moving beyond mere correlation. This is crucial for personalized treatment
    recommendations and effective interventions.
    """
    def __init__(self, llm_provider_instance, knowledge_graph_instance):
        """
        Initializes the CausalInference module.
        
        :param llm_provider_instance: An initialized LLMProvider instance for advanced causal reasoning.
        :param knowledge_graph_instance: An initialized KnowledgeGraph instance for known causal links.
        """
        self.llm = llm_provider_instance
        self.knowledge_graph = knowledge_graph_instance
        
        print("✅ CausalInference initialized.")

    async def analyze_causality(self, data: Dict[str, Any], hypothesis: str = None) -> Dict[str, Any]:
        """
        Analyzes provided data to infer potential cause-and-effect relationships.
        
        :param data: A dictionary containing relevant observational data or patient history.
                     Example: {"patient_history": [...], "lab_results": [...], "treatment_outcomes": [...]} 
        :param hypothesis: An optional hypothesis to test (e.g., "Does X cause Y?").
        :return: A dictionary detailing inferred causal links, their likelihood, and reasoning.
        """
        causal_report = {
            "hypothesis": hypothesis,
            "inferred_causal_links": [], # List of {"cause": "...", "effect": "...", "likelihood": "...", "reasoning": "..."}
            "limitations": [],
            "llm_confidence": 0.0
        }
        
        # 1. Look for known causal links in the Knowledge Graph
        kg_causal_links = await self._check_knowledge_graph_for_causality(data, hypothesis)
        if kg_causal_links:
            causal_report["inferred_causal_links"].extend(kg_causal_links)
            causal_report["llm_confidence"] = max(causal_report["llm_confidence"], 0.7)

        # 2. LLM-based Counterfactual Reasoning and Causal Inference
        # This is where the LLM's understanding of medical science comes into play.
        llm_causal_analysis = await self._llm_perform_causal_analysis(data, hypothesis)
        causal_report["inferred_causal_links"].extend(llm_causal_analysis["inferred_causal_links"])
        causal_report["limitations"].extend(llm_causal_analysis["limitations"])
        causal_report["llm_confidence"] = max(causal_report["llm_confidence"], llm_causal_analysis["llm_confidence"])

        # Deduplicate and refine links
        unique_links = {}
        for link in causal_report["inferred_causal_links"]:
            key = (link["cause"], link["effect"])
            if key not in unique_links or unique_links[key]["likelihood"] < link["likelihood"]:
                unique_links[key] = link
        causal_report["inferred_causal_links"] = list(unique_links.values())

        if not causal_report["inferred_causal_links"]:
            causal_report["limitations"].append("No strong causal links could be inferred from the provided data.")
            
        return causal_report

    async def _check_knowledge_graph_for_causality(self, data: Dict[str, Any], hypothesis: str = None) -> List[Dict[str, Any]]:
        """
        Queries the knowledge graph for established causal relationships relevant to the data.
        """
        kg_links = []
        # Example: if "smoking" is in patient history, look for "smoking causes lung cancer"
        patient_history = " ".join(data.get("patient_history", []))
        if "smoking" in patient_history.lower():
            # In a real KG, query: "MATCH (p:FACTOR {name: 'Smoking'})-[:CAUSES]->(d:DISEASE) RETURN d"
            # Mock result:
            kg_links.append({
                "cause": "Smoking",
                "effect": "Lung Cancer",
                "likelihood": "high",
                "reasoning": "Established medical fact from knowledge graph.",
                "source": "Knowledge Graph"
            })
        
        return kg_links

    async def _llm_perform_causal_analysis(self, data: Dict[str, Any], hypothesis: str = None) -> Dict[str, Any]:
        """
        Uses the LLM for advanced causal inference, especially useful for observational data
        where traditional statistical methods might be insufficient or complex to apply.
        """
        llm_causal_report = {
            "inferred_causal_links": [],
            "limitations": ["LLM inference is based on its training data and may not reflect specific study designs."],
            "llm_confidence": 0.5
        }
        
        # Construct a detailed prompt for the LLM
        prompt_parts = [
            "You are a medical causal inference expert. Analyze the following patient data to identify potential cause-and-effect relationships. Differentiate correlation from causation where possible. Always state limitations due to observational data."
            f"Patient Data: {json.dumps(data)}"
        ]
        if hypothesis:
            prompt_parts.append(f"Specifically, evaluate the hypothesis: '{hypothesis}'.")
        prompt_parts.append("Identify 1-3 most likely causal links, their likelihood (low, medium, high), and brief reasoning. Also list inherent limitations of this analysis.")
        
        user_prompt = "\n".join(prompt_parts)
        
        llm_response_text = await self.llm.generate_response(user_prompt, [])
        
        # --- Simulate LLM parsing ---
        # In a real system, you'd have more robust parsing (e.g., another LLM call or regex).
        if "smoking causes lung cancer" in llm_response_text.lower():
            llm_causal_report["inferred_causal_links"].append({
                "cause": "Smoking",
                "effect": "Lung Cancer",
                "likelihood": "high",
                "reasoning": "Consistent findings in trained data."
            })
            llm_causal_report["llm_confidence"] = 0.8
        
        if "high blood pressure leads to heart disease" in llm_response_text.lower():
             llm_causal_report["inferred_causal_links"].append({
                "cause": "High Blood Pressure",
                "effect": "Heart Disease",
                "likelihood": "high",
                "reasoning": "Well-established medical link."
            })
             llm_causal_report["llm_confidence"] = 0.85

        if "coffee consumption associated with longer life" in llm_response_text.lower():
            llm_causal_report["inferred_causal_links"].append({
                "cause": "Coffee Consumption",
                "effect": "Longer Life",
                "likelihood": "medium",
                "reasoning": "Observed correlation, but direct causation is still debated and confounded by lifestyle factors."
            })
            llm_causal_report["limitations"].append("Observational data often shows correlation, not causation. Confounding variables not controlled.")
            llm_causal_report["llm_confidence"] = 0.6
        
        if "limitations" in llm_response_text.lower():
            if "observational data" in llm_response_text.lower():
                llm_causal_report["limitations"].append("Analysis is based on observational data, which limits strong causal claims.")
            if "confounding variables" in llm_response_text.lower():
                llm_causal_report["limitations"].append("Potential confounding variables may not have been accounted for.")
        
        return llm_causal_report


# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockLLMProvider:
        def __init__(self, config=None): pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            if "smoking" in prompt.lower():
                return "Based on extensive medical literature, smoking is a significant causal factor for lung cancer. High blood pressure also leads to heart disease. Coffee consumption is associated with longer life, but causation is not fully established due to observational data and confounding variables. Limitations: This analysis is based on available data and general medical knowledge; specific patient context might vary."
            if "diet" in prompt.lower():
                return "A healthy diet reduces the risk of many diseases. This is a causal link. Limitations: Diet is complex and interacts with many lifestyle factors."
            return "No clear causal links found from LLM analysis. Limitations: Observational data only."
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-causal-inference"

    class MockKnowledgeGraph:
        def __init__(self):
            # Simulate known causal links
            self.causal_links = {
                "smoking": [
                    {"cause": "Smoking", "effect": "Lung Cancer", "likelihood": "high", "source": "Medical Literature"}
                ],
                "high blood pressure": [
                    {"cause": "High Blood Pressure", "effect": "Heart Disease", "likelihood": "high", "source": "Medical Guidelines"}
                ]
            }
        async def query_causal_links(self, keywords: List[str]) -> List[Dict[str, Any]]:
            found_links = []
            for kw in keywords:
                found_links.extend(self.causal_links.get(kw.lower(), []))
            return found_links


    # --- Initialize ---
    mock_llm = MockLLMProvider()
    mock_kg = MockKnowledgeGraph()
    
    causal_analyst = CausalInference(mock_llm, mock_kg)

    # --- Test 1: Analyze patient history with smoking ---
    print("\n--- Test 1: Analyze patient history with smoking ---")
    patient_data_1 = {
        "patient_history": ["Patient has a history of heavy smoking for 20 years.", "Recently diagnosed with a persistent cough."],
        "lab_results": [],
        "treatment_outcomes": []
    }
    hypothesis_1 = "Does smoking cause lung cancer in this patient?"
    report_1 = asyncio.run(causal_analyst.analyze_causality(patient_data_1, hypothesis_1))
    print(f"Causal Report for Hypothesis 1: {json.dumps(report_1, indent=2)}")

    # --- Test 2: Analyze general lifestyle data ---
    print("\n--- Test 2: Analyze general lifestyle data ---")
    patient_data_2 = {
        "patient_history": ["Patient eats a balanced diet and exercises regularly.", "Has lower risk of heart disease."],
        "lab_results": {"cholesterol": "low"},
        "treatment_outcomes": []
    }
    hypothesis_2 = "Does diet and exercise causally improve heart health?"
    report_2 = asyncio.run(causal_analyst.analyze_causality(patient_data_2, hypothesis_2))
    print(f"Causal Report for Hypothesis 2: {json.dumps(report_2, indent=2)}")

    # --- Test 3: Analyze data with complex correlation (coffee) ---
    print("\n--- Test 3: Analyze data with complex correlation ---")
    patient_data_3 = {
        "patient_history": ["Patient drinks 2 cups of coffee daily.", "Enjoys long walks."],
        "lab_results": {},
        "treatment_outcomes": {"overall_health": "good"}
    }
    hypothesis_3 = "Does coffee consumption cause longer life?"
    report_3 = asyncio.run(causal_analyst.analyze_causality(patient_data_3, hypothesis_3))
    print(f"Causal Report for Hypothesis 3: {json.dumps(report_3, indent=2)}")
