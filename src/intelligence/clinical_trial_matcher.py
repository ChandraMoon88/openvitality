# src/intelligence/clinical_trial_matcher.py

from typing import Dict, Any, List
import asyncio
import json
import random

# Assuming these imports will be available from other modules
# from src.intelligence.llm_interface import LLMProvider # For summarizing trial info
# from src.core.telemetry_emitter import TelemetryEmitter


class ClinicalTrialMatcher:
    """
    Matches eligible patients to relevant clinical trials based on their
    medical profile, conditions, demographics, and genetic information.
    """
    def __init__(self, llm_provider_instance, telemetry_emitter_instance):
        """
        Initializes the ClinicalTrialMatcher.
        
        :param llm_provider_instance: An initialized LLMProvider instance for summarizing trial info.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.llm = llm_provider_instance
        self.telemetry = telemetry_emitter_instance
        
        # Mock clinical trial database (simplified for demonstration)
        self.mock_trials_db = [
            {
                "trial_id": "CT001",
                "title": "Study of Novel Drug X for Type 2 Diabetes",
                "condition": "Type 2 Diabetes",
                "phase": "Phase 3",
                "age_min": 18, "age_max": 75,
                "gender": "Any",
                "inclusion_criteria": ["Diagnosed with Type 2 Diabetes", "HbA1c between 7.0-10.0%", "No history of cardiovascular events"],
                "exclusion_criteria": ["Pregnant or breastfeeding", "Severe kidney disease"],
                "contact": {"name": "Dr. Smith", "email": "trials@example.com"},
                "location": "Major City Hospital"
            },
            {
                "trial_id": "CT002",
                "title": "Immunotherapy for Advanced Lung Cancer",
                "condition": "Lung Cancer",
                "phase": "Phase 2",
                "age_min": 50, "age_max": 90,
                "gender": "Any",
                "inclusion_criteria": ["Diagnosed with Stage III/IV Lung Cancer", "ECOG performance status 0-1"],
                "exclusion_criteria": ["Active autoimmune disease", "Previous organ transplant"],
                "contact": {"name": "Dr. Jones", "phone": "555-123-4567"},
                "location": "Regional Cancer Center"
            },
            {
                "trial_id": "CT003",
                "title": "Genetic Therapy for BRCA1 Mutation Breast Cancer",
                "condition": "Breast Cancer",
                "phase": "Phase 1",
                "age_min": 25, "age_max": 65,
                "gender": "Female",
                "inclusion_criteria": ["Confirmed BRCA1 mutation", "Diagnosed with Stage II/III Breast Cancer"],
                "exclusion_criteria": ["History of other cancers", "Systemic chemotherapy within 6 months"],
                "contact": {"name": "Dr. Williams", "email": "genetics_trials@example.com"},
                "location": "University Research Hospital"
            }
        ]
        
        print("✅ ClinicalTrialMatcher initialized.")

    async def match_patient_to_trials(self, patient_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Matches a patient's medical profile against the criteria of available clinical trials.
        
        :param patient_profile: A dictionary containing the patient's medical profile.
                                Example: {"age": 62, "gender": "male", "conditions": ["Type 2 Diabetes"],
                                          "genetics": {}, "lab_results": {"HbA1c": 8.5}}
        :return: A list of dictionaries, where each dict represents a matched trial and eligibility details.
        """
        matched_trials: List[Dict[str, Any]] = []
        
        patient_age = patient_profile.get("age")
        patient_gender = patient_profile.get("gender")
        patient_conditions = patient_profile.get("conditions", [])
        patient_genetics = patient_profile.get("genetics", {})
        patient_lab_results = patient_profile.get("lab_results", {})

        print(f"Matching patient {patient_profile.get('user_id', 'unknown')} to trials...")

        for trial in self.mock_trials_db:
            eligibility_status = {"eligible": True, "reasons": []}

            # Check Age
            if patient_age is not None:
                if patient_age < trial["age_min"]:
                    eligibility_status["eligible"] = False
                    eligibility_status["reasons"].append(f"Too young (minimum age {trial['age_min']})")
                if patient_age > trial["age_max"]:
                    eligibility_status["eligible"] = False
                    eligibility_status["reasons"].append(f"Too old (maximum age {trial['age_max']})")

            # Check Gender
            if trial["gender"] != "Any" and patient_gender != trial["gender"]:
                eligibility_status["eligible"] = False
                eligibility_status["reasons"].append(f"Gender mismatch (requires {trial['gender']})")

            # Check Inclusion Criteria
            for criterion in trial["inclusion_criteria"]:
                if "Diabetes" in criterion and "Type 2 Diabetes" in patient_conditions:
                    # Specific check for HbA1c
                    if "HbA1c" in criterion and patient_lab_results.get("HbA1c") is not None:
                        hba1c_val = patient_lab_results["HbA1c"]
                        if not (7.0 <= hba1c_val <= 10.0):
                            eligibility_status["eligible"] = False
                            eligibility_status["reasons"].append(f"HbA1c {hba1c_val}% not in range 7.0-10.0%")
                elif "Lung Cancer" in criterion and "Lung Cancer" in patient_conditions:
                    pass # Simplified, assume condition matches
                elif "BRCA1 mutation" in criterion and patient_genetics.get("BRCA1") == "positive":
                    pass # Simplified, assume genetics match
                elif not any(cond in criterion for cond in patient_conditions + [patient_genetics.get("BRCA1")]): # General check
                    # This logic needs to be much more robust for real trials
                    # For demo, if a condition is mentioned in inclusion, it must be present in patient.
                    is_met = False
                    for p_cond in patient_conditions:
                        if p_cond in criterion:
                            is_met = True
                            break
                    if not is_met and "BRCA1 mutation" in criterion and patient_genetics.get("BRCA1") != "positive":
                        is_met = False
                    
                    if not is_met:
                        eligibility_status["eligible"] = False
                        eligibility_status["reasons"].append(f"Missing inclusion criterion: {criterion}")

            # Check Exclusion Criteria
            for criterion in trial["exclusion_criteria"]:
                if "Pregnant" in criterion and patient_profile.get("is_pregnant"):
                    eligibility_status["eligible"] = False
                    eligibility_status["reasons"].append(f"Exclusion criterion met: {criterion}")
                if "Severe kidney disease" in criterion and "Kidney Disease" in patient_conditions:
                    eligibility_status["eligible"] = False
                    eligibility_status["reasons"].append(f"Exclusion criterion met: {criterion}")
                if "Active autoimmune disease" in criterion and "Autoimmune Disease" in patient_conditions:
                    eligibility_status["eligible"] = False
                    eligibility_status["reasons"].append(f"Exclusion criterion met: {criterion}")
            
            if eligibility_status["eligible"]:
                summary = await self._summarize_trial_llm(trial)
                matched_trials.append({
                    "trial_id": trial["trial_id"],
                    "title": trial["title"],
                    "condition": trial["condition"],
                    "phase": trial["phase"],
                    "location": trial["location"],
                    "contact": trial["contact"],
                    "eligibility_status": eligibility_status,
                    "summary": summary
                })
            else:
                 self.telemetry.emit_event("clinical_trial_match_failed", {"patient_id": patient_profile.get("user_id"), "trial_id": trial["trial_id"], "reasons": eligibility_status["reasons"]})

        self.telemetry.emit_event("clinical_trial_match_complete", {"patient_id": patient_profile.get("user_id"), "matched_count": len(matched_trials)})
        return matched_trials

    async def _summarize_trial_llm(self, trial_details: Dict[str, Any]) -> str:
        """
        Uses an LLM to generate a patient-friendly summary of the clinical trial.
        """
        system_prompt = """You are a medical AI assistant. Summarize the following clinical trial details
        into a concise, patient-friendly description. Highlight the main purpose, what's involved, and who might be eligible.
        Always include a disclaimer that this is for informational purposes and they should discuss with their doctor."""
        
        user_prompt = f"""Clinical Trial Details: {json.dumps(trial_details, indent=2)}
        
        Provide a summary."""
        
        llm_response = await self.llm.generate_response(user_prompt, [{"role": "system", "text": system_prompt}])
        return llm_response

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockLLMProvider:
        def __init__(self, config=None): pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            if "Study of Novel Drug X for Type 2 Diabetes" in prompt:
                return "This trial is testing a new drug for people with Type 2 Diabetes. It's for adults aged 18-75 with a certain blood sugar level. Talk to your doctor to see if it's right for you. This is for informational purposes only."
            if "Immunotherapy for Advanced Lung Cancer" in prompt:
                return "This trial is investigating immunotherapy for advanced lung cancer. It's for older adults with specific cancer stages. Discuss with your oncologist. This is for informational purposes only."
            if "Genetic Therapy for BRCA1 Mutation Breast Cancer" in prompt:
                return "This trial explores genetic therapy for women with BRCA1-positive breast cancer. It's for certain age groups and cancer stages. Consult your doctor. This is for informational purposes only."
            return "Mock LLM trial summary. This is for informational purposes only."
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-trial-summarizer"

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_llm = MockLLMProvider()
    mock_te = MockTelemetryEmitter()
    
    matcher = ClinicalTrialMatcher(mock_llm, mock_te)

    # --- Test 1: Patient for Diabetes Trial ---
    print("\n--- Test 1: Patient for Diabetes Trial ---")
    patient_1 = {
        "user_id": "p_trial_1", "age": 62, "gender": "male", 
        "conditions": ["Type 2 Diabetes", "Hypertension"],
        "genetics": {},
        "lab_results": {"HbA1c": 8.5}
    }
    matched_trials_1 = asyncio.run(matcher.match_patient_to_trials(patient_1))
    print(f"Matched Trials for Patient 1: {json.dumps(matched_trials_1, indent=2)}")

    # --- Test 2: Patient for Lung Cancer Trial (Eligible) ---
    print("\n--- Test 2: Patient for Lung Cancer Trial ---")
    patient_2 = {
        "user_id": "p_trial_2", "age": 70, "gender": "female",
        "conditions": ["Lung Cancer"],
        "lab_results": {"ECOG_performance_status": 0}
    }
    matched_trials_2 = asyncio.run(matcher.match_patient_to_trials(patient_2))
    print(f"Matched Trials for Patient 2: {json.dumps(matched_trials_2, indent=2)}")
    
    # --- Test 3: Patient for Lung Cancer Trial (Too young) ---
    print("\n--- Test 3: Patient for Lung Cancer Trial (Too Young) ---")
    patient_3 = {
        "user_id": "p_trial_3", "age": 45, "gender": "male",
        "conditions": ["Lung Cancer"],
        "lab_results": {"ECOG_performance_status": 0}
    }
    matched_trials_3 = asyncio.run(matcher.match_patient_to_trials(patient_3))
    print(f"Matched Trials for Patient 3: {json.dumps(matched_trials_3, indent=2)}")

    # --- Test 4: Patient for BRCA1 Breast Cancer Trial ---
    print("\n--- Test 4: Patient for BRCA1 Breast Cancer Trial ---")
    patient_4 = {
        "user_id": "p_trial_4", "age": 40, "gender": "Female",
        "conditions": ["Breast Cancer"],
        "genetics": {"BRCA1": "positive"}
    }
    matched_trials_4 = asyncio.run(matcher.match_patient_to_trials(patient_4))
    print(f"Matched Trials for Patient 4: {json.dumps(matched_trials_4, indent=2)}")
