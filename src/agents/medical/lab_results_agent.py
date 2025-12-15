import logging
import re
import datetime # FIX: Added missing import
from typing import Dict, Any, List, Optional, Tuple

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class LabResultsAgent(BaseAgent):
    """
    A specialized AI agent for explaining medical lab test results.
    It processes raw lab data, compares it against reference ranges,
    translates complex jargon into plain English, tracks trends,
    and identifies critical values.
    """
    def __init__(self, nlu_engine: Any = None, medical_kg: Any = None):
        super().__init__(
            name="LabResultsAgent",
            description="Explains medical lab test results in plain language.",
            persona={
                "role": "clear and informative medical results assistant",
                "directives": [
                    "Translate medical jargon into easy-to-understand explanations.",
                    "Compare results against age/sex-adjusted reference ranges.",
                    "Highlight significant deviations (high/low) and explain their potential meaning.",
                    "Identify and alert to critical values that require immediate medical attention.",
                    "Provide context by comparing current results to previous ones (trends).",
                    "Suggest general action items (e.g., 'discuss with your doctor', 'monitor symptoms').",
                    "Emphasize that this is not a diagnosis and to consult a doctor for personalized advice."
                ],
                "style": "calm, clear, objective, educational"
            }
        )
        self.nlu_engine = nlu_engine
        self.medical_kg = medical_kg # Knowledge Graph for reference ranges, explanations
        
        self._memory["patient_info"] = {"age": None, "gender": None}
        self._memory["previous_results"] = {} # {test_name: [{date, value, unit}, ...]}
        self._memory["current_lab_report"] = {} # {test_name: {value, unit, date}}
        self._memory["conversation_stage"] = "waiting_for_report" # waiting_for_report, explaining_results, discussing_trends
        logger.info("LabResultsAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input, which may include uploading lab reports or asking questions about results.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = self.nlu_engine.process_text(text, context.get("language", "en"))
        
        text_lower = text.lower()

        if self._memory["conversation_stage"] == "waiting_for_report":
            if "upload" in text_lower or "my lab results" in text_lower or "blood test" in text_lower:
                self._memory["conversation_stage"] = "processing_report"
                return {
                    "response_text": "Please provide your lab results. You can type them out, or tell me if you have a PDF or image you'd like to share (though direct uploads are not yet supported).",
                    "context_update": {"lab_stage": "input_report"},
                    "action": "request_lab_data"
                }
            
            return {"response_text": "To help you, please tell me you want to upload or discuss lab results.", "context_update": {}, "action": "clarify_lab"}
        
        elif self._memory["conversation_stage"] == "processing_report":
            # Assuming 'text' now contains the unstructured lab results
            return self._process_and_explain_results(text, context, nlu_output)
            
        elif self._memory["conversation_stage"] == "explaining_results":
            # User is asking follow-up questions about the explained results
            return await self._handle_follow_up_questions(text, context, nlu_output)
        
        return {"response_text": "I'm not sure how to respond to that in the context of lab results. Would you like me to re-explain anything?", "context_update": {}, "action": "clarify_lab"}

    def _extract_results_from_text(self, report_text: str) -> List[Dict[str, Any]]:
        """
        (Conceptual) Extracts test names, values, and units from unstructured text.
        In a real system, this would involve sophisticated NLP and regex patterns
        tuned for lab report formats, or OCR integration for images/PDFs.
        """
        extracted_results = []
        # Example: Hemoglobin 10.5 g/dL, Glucose 95 mg/dL, WBC 7.2 x 10^3/uL
        
        # Regex for common lab values
        patterns = {
            "Hemoglobin": r"(hemoglobin|hgb)\s*[:=]?\s*(\d+\.?\d*)\s*(g/dL|g/l)?",
            "Glucose": r"(glucose|sugar)\s*[:=]?\s*(\d+\.?\d*)\s*(mg/dL|mg/dl|mmol/L)?",
            "WBC": r"(wbc|white blood cell)\s*[:=]?\s*(\d+\.?\d*)\s*(x\s*10\^3/uL|\/uL)?",
            "Creatinine": r"(creatinine)\s*[:=]?\s*(\d+\.?\d*)\s*(mg/dL|mg/dl|umol/L)?",
            "TSH": r"(tsh)\s*[:=]?\s*(\d+\.?\d*)\s*(mIU/L|uIU/mL)?",
            # Add more patterns for other tests
        }

        for test_name, pattern_str in patterns.items():
            for match in re.finditer(pattern_str, report_text, re.IGNORECASE):
                value = float(match.group(2))
                unit = match.group(3) if match.group(3) else "unknown"
                extracted_results.append({"test_name": test_name, "value": value, "unit": unit})
        
        logger.debug(f"Extracted raw results: {extracted_results}")
        return extracted_results

    def _get_reference_range(self, test_name: str, age: Optional[int], gender: Optional[str]) -> Tuple[Optional[float], Optional[float], str]:
        """
        (Conceptual) Retrieves age/sex-adjusted reference ranges from a medical knowledge graph.
        Returns (lower_bound, upper_bound, unit).
        """
        # This would query a database or API (e.g., KnowledgeGraph tool)
        # For example: self.medical_kg.get_reference_range(test_name, age, gender)
        
        # Mock values for demonstration
        if test_name == "Hemoglobin":
            if gender == "male" and age and age >= 18: return (13.5, 17.5, "g/dL")
            if gender == "female" and age and age >= 18: return (12.0, 15.5, "g/dL")
            return (11.0, 14.0, "g/dL") # General
        elif test_name == "Glucose": return (70.0, 99.0, "mg/dL") # Fasting
        elif test_name == "WBC": return (4.5, 11.0, "x 10^3/uL")
        elif test_name == "Creatinine": return (0.6, 1.3, "mg/dL")
        elif test_name == "TSH": return (0.4, 4.0, "mIU/L")
        
        return (None, None, "unknown")

    def _process_and_explain_results(self, report_text: str, context: Dict[str, Any], nlu_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts, interprets, and explains lab results.
        """
        patient_age = context.get("patient_age")
        patient_gender = context.get("patient_gender")

        # Store patient info for later use
        self._memory["patient_info"]["age"] = patient_age
        self._memory["patient_info"]["gender"] = patient_gender

        extracted_results = self._extract_results_from_text(report_text)
        self._memory["current_lab_report"] = {res["test_name"]: res for res in extracted_results}

        explanation_parts = ["Here are your lab results in plain English:"]
        action_items = []
        red_flags_detected = False

        for result in extracted_results:
            test_name = result["test_name"]
            value = result["value"]
            unit = result["unit"]
            lower_bound, upper_bound, ref_unit = self._get_reference_range(test_name, patient_age, patient_gender)

            if lower_bound is None or upper_bound is None:
                explanation_parts.append(f"- Your {test_name} is {value} {unit}. I don't have a specific reference range for this test, please consult your doctor.")
                continue

            explanation = f"- Your {test_name} level is {value} {unit}. The normal range is typically between {lower_bound} and {upper_bound} {ref_unit}."
            
            if value < lower_bound:
                explanation += f" This is lower than normal."
                if test_name == "Hemoglobin":
                    explanation += " A low Hemoglobin often suggests anemia, meaning you have fewer red blood cells than normal."
                    action_items.append("Discuss with your doctor about potential causes of anemia and iron supplementation.")
                # Check for critical low
                if test_name == "Glucose" and value < 50:
                    explanation += " This is a critically low glucose level and needs immediate medical attention."
                    red_flags_detected = True
                    explanation_parts.append(f"CRITICAL ALERT: {test_name} is dangerously low ({value} {unit}). Seek immediate medical attention.")
                    continue # Skip further explanation for critical alerts
            elif value > upper_bound:
                explanation += f" This is higher than normal."
                if test_name == "Glucose":
                    explanation += " A high glucose level can indicate hyperglycemia, common in diabetes."
                    action_items.append("Discuss high glucose levels with your doctor, especially if you have diabetes or symptoms.")
                # Check for critical high
                if test_name == "Glucose" and value > 400:
                    explanation += " This is a critically high glucose level and needs immediate medical attention."
                    red_flags_detected = True
                    explanation_parts.append(f"CRITICAL ALERT: {test_name} is dangerously high ({value} {unit}). Seek immediate medical attention.")
                    continue
            else:
                explanation += " This is within the normal range."
            
            explanation_parts.append(explanation)
            self._update_trends(test_name, value, unit)

        explanation_parts.append("\nImportant Action Items:")
        if not action_items:
            action_items.append("All results appear within normal limits, but always review with your doctor.")
        explanation_parts.extend([f"- {item}" for item in action_items])

        final_response = " ".join(explanation_parts)
        final_response += "\nPlease remember, I am an AI and cannot provide medical advice or diagnosis. Always discuss your lab results with a qualified healthcare professional."
        
        self._memory["conversation_stage"] = "explaining_results"
        return {
            "response_text": final_response,
            "context_update": {"lab_stage": "explained_results", "red_flags_detected": red_flags_detected},
            "action": "explain_results"
        }

    def _update_trends(self, test_name: str, current_value: float, unit: str):
        """
        Updates the memory with current result for trend comparison.
        """
        if test_name not in self._memory["previous_results"]:
            self._memory["previous_results"][test_name] = []
        
        # Add current result to previous for next time (simulate storage)
        self._memory["previous_results"][test_name].append({
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "value": current_value,
            "unit": unit
        })
        # Keep only the last few for a simple trend (e.g., 5 results)
        self._memory["previous_results"][test_name] = self._memory["previous_results"][test_name][-5:]

        # Simple trend analysis
        if len(self._memory["previous_results"][test_name]) > 1:
            all_values = [res["value"] for res in self._memory["previous_results"][test_name]]
            latest = all_values[-1]
            previous = all_values[-2]
            if latest > previous:
                logger.info(f"Trend for {test_name}: Increasing from {previous} to {latest}")
            elif latest < previous:
                logger.info(f"Trend for {test_name}: Decreasing from {previous} to {latest}")

    async def _handle_follow_up_questions(self, text: str, context: Dict[str, Any], nlu_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles follow-up questions from the user after the initial results explanation.
        """
        text_lower = text.lower()
        response_text = "I can try to clarify, but for detailed medical interpretation, please ask your doctor."
        
        if "what does" in text_lower and "mean" in text_lower:
            # Attempt to find a test name in the query and explain it further
            for test_name in self._memory["current_lab_report"].keys():
                if test_name.lower() in text_lower:
                    value = self._memory["current_lab_report"][test_name]["value"]
                    unit = self._memory["current_lab_report"][test_name]["unit"]
                    lower_bound, upper_bound, ref_unit = self._get_reference_range(test_name, self._memory["patient_info"]["age"], self._memory["patient_info"]["gender"])
                    
                    if lower_bound is not None:
                         response_text = f"Your {test_name} level of {value} {unit} means that "
                         if value < lower_bound:
                             response_text += f"it is lower than the normal range ({lower_bound}-{upper_bound} {ref_unit}). This could suggest [potential low implications]."
                         elif value > upper_bound:
                             response_text += f"it is higher than the normal range ({lower_bound}-{upper_bound} {ref_unit}). This could suggest [potential high implications]."
                         else:
                             response_text += f"it is within the normal range ({lower_bound}-{upper_bound} {ref_unit})."
                         response_text += " Your doctor can provide more specific details based on your overall health."
                         break
            else:
                response_text = "Which specific test or term would you like me to explain?"
        
        return {
            "response_text": response_text,
            "context_update": {"lab_stage": "explaining_results"},
            "action": "answer_question"
        }

    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["patient_info"] = {"age": None, "gender": None}
        self._memory["previous_results"] = {}
        self._memory["current_lab_report"] = {}
        self._memory["conversation_stage"] = "waiting_for_report"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock NLU Engine and Medical Knowledge Graph for testing
    class MockNLUEngine:
        def process_text(self, text, lang):
            return {} 

    class MockMedicalKG:
        def get_reference_range(self, test_name, age, gender):
            if test_name == "Hemoglobin":
                if gender == "male" and age and age >= 18: return (13.5, 17.5, "g/dL")
                if gender == "female" and age and age >= 18: return (12.0, 15.5, "g/dL")
                return (11.0, 14.0, "g/dL") 
            elif test_name == "Glucose": return (70.0, 99.0, "mg/dL") 
            return (None, None, "unknown")


    nlu_mock = MockNLUEngine()
    medical_kg_mock = MockMedicalKG()
    
    lab_agent = LabResultsAgent(nlu_engine=nlu_mock, medical_kg=medical_kg_mock)

    async def run_lab_results_flow():
        context = {"call_id": "lab_call_111", "user_id": "user_lab", "language": "en", "patient_age": 45, "patient_gender": "female"}

        print("\n--- Flow 1: Initial Query for Lab Results ---")
        response1 = await lab_agent.process_input("I have my blood test results.", context)
        print(f"Agent: {response1['response_text']}")

        print("\n--- Flow 2: Providing Lab Results (Unstructured Text) ---")
        lab_report_text = """
        Patient: Jane Doe
        Test Date: 2025-12-11

        Hemoglobin: 10.5 g/dL (Low)
        Glucose: 150 mg/dL (High)
        WBC: 8.0 x 10^3/uL (Normal)
        Creatinine: 0.9 mg/dL (Normal)
        """
        response2 = await lab_agent.process_input(lab_report_text, context)
        print(f"Agent: {response2['response_text']}")
        assert "Hemoglobin level is 10.5 g/dL. This is lower than normal" in response2["response_text"]
        assert "Glucose level is 150.0 mg/dL. This is higher than normal" in response2["response_text"]
        assert "discuss with your doctor about potential causes of anemia" in response2["response_text"]

        print("\n--- Flow 3: Follow-up Question on Glucose ---")
        response3 = await lab_agent.process_input("What does high glucose mean?", context)
        print(f"Agent: {response3['response_text']}")
        assert "higher than the normal range" in response3["response_text"]

        print("\n--- Flow 4: Critical Glucose Reading ---")
        lab_agent.reset_memory()
        response_crit1 = await lab_agent.process_input("I have my lab report.", context)
        response_crit2_text = """
        Patient: John Smith
        Test Date: 2025-12-11
        Glucose: 450 mg/dL (Critical High)
        """
        response_crit2 = await lab_agent.process_input(response_crit2_text, context)
        print(f"Agent: {response_crit2['response_text']}")
        assert "CRITICAL ALERT: Glucose is dangerously high" in response_crit2["response_text"]
        assert response_crit2["context_update"]["red_flags_detected"] == True

        lab_agent.reset_memory()
        print(f"\nMemory after reset: {lab_agent.current_memory}")

    import asyncio
    asyncio.run(run_lab_results_flow())