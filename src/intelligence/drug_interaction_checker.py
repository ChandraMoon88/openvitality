# src/intelligence/drug_interaction_checker.py

from typing import Dict, Any, List
import asyncio
import json

# Assuming these imports will be available from other modules
# from src.intelligence.knowledge_graph import KnowledgeGraph # For drug-condition links
# from src.intelligence.llm_interface import LLMProvider # For nuanced interpretations
# from src.core.telemetry_emitter import TelemetryEmitter


class DrugInteractionChecker:
    """
    Identifies potential adverse drug-drug or drug-condition interactions
    to enhance patient safety.
    """
    def __init__(self, kg_instance, llm_provider_instance, telemetry_emitter_instance):
        """
        Initializes the DrugInteractionChecker.
        
        :param kg_instance: An initialized KnowledgeGraph instance containing drug, condition, and interaction data.
        :param llm_provider_instance: An initialized LLMProvider instance for nuanced interpretation of interactions.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.knowledge_graph = kg_instance
        self.llm = llm_provider_instance
        self.telemetry = telemetry_emitter_instance
        
        # Mock drug interaction database (simplified for demonstration)
        self.mock_drug_db = {
            "Aspirin": {
                "interactions": [
                    {"drug": "Warfarin", "severity": "high", "effect": "Increased bleeding risk"},
                    {"condition": "Asthma", "severity": "medium", "effect": "May worsen asthma symptoms"},
                ],
                "contraindications": ["Gastric Ulcer"],
            },
            "Metformin": {
                "interactions": [
                    {"drug": "Iodinated Contrast Media", "severity": "high", "effect": "Risk of lactic acidosis"},
                ],
                "contraindications": ["Kidney Disease"],
            },
            "Paracetamol": {
                "interactions": [],
                "contraindications": ["Severe Liver Disease"],
            },
            "Warfarin": {
                "interactions": [
                    {"drug": "Aspirin", "severity": "high", "effect": "Increased bleeding risk"},
                ],
                "contraindications": [],
            }
        }
        
        print("✅ DrugInteractionChecker initialized.")

    async def check_interactions(self, drug_list: List[str], patient_conditions: List[str]) -> List[Dict[str, Any]]:
        """
        Checks for interactions between a list of drugs and the patient's existing conditions.
        
        :param drug_list: A list of drug names (e.g., ["Aspirin", "Metformin"]).
        :param patient_conditions: A list of patient's medical conditions (e.g., ["Asthma", "Hypertension"]).
        :return: A list of detected interactions, including severity and recommendations.
        """
        detected_interactions: List[Dict[str, Any]] = []
        
        # Standardize drug and condition names (e.g., lowercase, canonical forms)
        normalized_drugs = [drug.title() for drug in drug_list] # Simple title case normalization
        normalized_conditions = [condition.title() for condition in patient_conditions]

        print(f"Checking interactions for drugs: {normalized_drugs}, conditions: {normalized_conditions}")

        for drug_name in normalized_drugs:
            drug_info = self.mock_drug_db.get(drug_name)
            if not drug_info:
                print(f"⚠️ Warning: Drug '{drug_name}' not found in database.")
                self.telemetry.emit_event("drug_interaction_check_warning", {"drug": drug_name, "reason": "not_found"})
                continue
            
            # 1. Check drug-drug interactions
            for interaction in drug_info.get("interactions", []):
                if "drug" in interaction and interaction["drug"] in normalized_drugs:
                    if interaction["drug"] != drug_name: # Avoid self-interaction check
                        detected_interactions.append(await self._format_interaction_report(
                            drug1=drug_name,
                            drug2=interaction["drug"],
                            interaction_type="drug-drug",
                            severity=interaction["severity"],
                            effect=interaction["effect"]
                        ))
            
            # 2. Check drug-condition contraindications
            for condition in normalized_conditions:
                if condition in drug_info.get("contraindications", []):
                     detected_interactions.append(await self._format_interaction_report(
                        drug1=drug_name,
                        condition=condition,
                        interaction_type="drug-condition_contraindication",
                        severity="high", # Contraindications are generally high severity
                        effect=f"{drug_name} is contraindicated in patients with {condition}."
                    ))
                # Also check for drug-condition warnings (not full contraindications)
                for interaction in drug_info.get("interactions", []):
                    if "condition" in interaction and interaction["condition"] == condition:
                        detected_interactions.append(await self._format_interaction_report(
                            drug1=drug_name,
                            condition=condition,
                            interaction_type="drug-condition_warning",
                            severity=interaction["severity"],
                            effect=interaction["effect"]
                        ))

        # 3. Use LLM for nuanced interpretation or to suggest alternatives/monitoring
        if detected_interactions:
            for interaction in detected_interactions:
                llm_recommendation = await self._llm_suggest_recommendation(interaction, normalized_drugs, normalized_conditions)
                interaction["llm_recommendation"] = llm_recommendation
        else:
             detected_interactions.append({"message": "No significant drug or drug-condition interactions detected from current data.", "severity": "none"})

        self.telemetry.emit_event("drug_interaction_check_complete", {"drugs": drug_list, "conditions": patient_conditions, "interactions_count": len(detected_interactions)})
        return detected_interactions

    async def _format_interaction_report(self, drug1: str, drug2: str = None, condition: str = None, interaction_type: str = "", severity: str = "medium", effect: str = "") -> Dict[str, Any]:
        """Helper to format interaction reports consistently."""
        report = {
            "type": interaction_type,
            "severity": severity,
            "effect": effect,
            "drugs_involved": [drug1],
            "conditions_involved": []
        }
        if drug2:
            report["drugs_involved"].append(drug2)
        if condition:
            report["conditions_involved"].append(condition)
        
        # Generate a general recommendation based on severity
        if severity == "high":
            report["recommendation"] = "Avoid this combination. Consult a medical professional immediately."
        elif severity == "medium":
            report["recommendation"] = "Monitor closely for adverse effects. Consult a medical professional."
        elif severity == "low":
            report["recommendation"] = "Generally safe, but be aware of potential minor effects."
        
        return report

    async def _llm_suggest_recommendation(self, interaction: Dict[str, Any], all_drugs: List[str], all_conditions: List[str]) -> str:
        """
        Uses an LLM to provide a nuanced recommendation for a detected interaction.
        """
        system_prompt = f"""You are a medical AI assistant providing advice on drug interactions.
        Given the detected interaction, current drugs ({', '.join(all_drugs)}) and patient conditions ({', '.join(all_conditions)}),
        suggest a cautious, medically sound recommendation for the patient. Always include a disclaimer.
        
        Interaction details: {json.dumps(interaction, indent=2)}
        """
        user_prompt = "Provide a concise, actionable recommendation regarding this interaction. What should the patient do?"
        
        llm_response = await self.llm.generate_response(user_prompt, [{"role": "system", "text": system_prompt}])
        return llm_response

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockKnowledgeGraph:
        def __init__(self):
            pass # Not directly used in interaction logic for this mock
    
    class MockLLMProvider:
        def __init__(self, config=None):
            pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            if "Increased bleeding risk" in prompt:
                return "The combination of Aspirin and Warfarin significantly increases the risk of bleeding. Your doctor may need to adjust your Warfarin dosage or consider an alternative medication. Do not make any changes to your medication without consulting your doctor."
            if "May worsen asthma symptoms" in prompt:
                return "Aspirin may worsen asthma symptoms in some individuals. If you have asthma, discuss this with your doctor before taking Aspirin. Monitor your breathing closely."
            if "Risk of lactic acidosis" in prompt:
                return "The use of Metformin with iodinated contrast media can increase the risk of lactic acidosis, a serious condition. Ensure your doctor is aware of all medications, especially before any imaging procedures involving contrast. Your Metformin may need to be temporarily stopped."
            return "Mock LLM recommendation: Consult a healthcare professional for specific advice."
        async def count_tokens(self, text: str) -> int:
            return len(text.split())
        def supports_streaming(self) -> bool:
            return False
        def supports_multimodality(self) -> bool:
            return False
        def get_model_name(self) -> str:
            return "mock-llm-drug-recommender"

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_kg = MockKnowledgeGraph()
    mock_llm = MockLLMProvider()
    mock_te = MockTelemetryEmitter()
    
    checker = DrugInteractionChecker(mock_kg, mock_llm, mock_te)

    # --- Test 1: Drug-drug interaction (Aspirin + Warfarin) ---
    print("\n--- Test 1: Drug-drug interaction (Aspirin + Warfarin) ---")
    drugs_1 = ["Aspirin", "Warfarin"]
    conditions_1 = []
    interactions_1 = asyncio.run(checker.check_interactions(drugs_1, conditions_1))
    print(f"Interactions for {drugs_1}: {json.dumps(interactions_1, indent=2)}")

    # --- Test 2: Drug-condition interaction (Aspirin + Asthma) ---
    print("\n--- Test 2: Drug-condition interaction (Aspirin + Asthma) ---")
    drugs_2 = ["Aspirin"]
    conditions_2 = ["Asthma"]
    interactions_2 = asyncio.run(checker.check_interactions(drugs_2, conditions_2))
    print(f"Interactions for {drugs_2} with {conditions_2}: {json.dumps(interactions_2, indent=2)}")

    # --- Test 3: Drug-condition contraindication (Metformin + Kidney Disease) ---
    print("\n--- Test 3: Drug-condition contraindication (Metformin + Kidney Disease) ---")
    drugs_3 = ["Metformin"]
    conditions_3 = ["Kidney Disease"]
    interactions_3 = asyncio.run(checker.check_interactions(drugs_3, conditions_3))
    print(f"Interactions for {drugs_3} with {conditions_3}: {json.dumps(interactions_3, indent=2)}")

    # --- Test 4: No interactions ---
    print("\n--- Test 4: No interactions ---")
    drugs_4 = ["Paracetamol"]
    conditions_4 = ["Headache"]
    interactions_4 = asyncio.run(checker.check_interactions(drugs_4, conditions_4))
    print(f"Interactions for {drugs_4} with {conditions_4}: {json.dumps(interactions_4, indent=2)}")
