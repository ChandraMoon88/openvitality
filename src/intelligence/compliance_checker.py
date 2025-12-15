# src/intelligence/compliance_checker.py

from typing import Dict, Any, List
import json
import asyncio
import time

# Assuming these imports will be available from other modules
# from src.intelligence.pii_scrubber import PIIScrubber
# from src.intelligence.audit_logger import AuditLogger
# from src.intelligence.medical_fact_checker import MedicalFactChecker
# from src.intelligence.ethical_guidelines_enforcer import EthicalGuidelinesEnforcer
# from src.core.telemetry_emitter import TelemetryEmitter


class ComplianceChecker:
    """
    Ensures AI operations adhere to legal and regulatory compliance standards
    such as HIPAA, GDPR, and DPDP, based on the operating region.
    """
    def __init__(self, pii_scrubber_instance, audit_logger_instance, medical_fact_checker_instance, ethical_enforcer_instance, telemetry_emitter_instance):
        """
        Initializes the ComplianceChecker with instances of its dependencies.
        """
        self.pii_scrubber = pii_scrubber_instance
        self.audit_logger = audit_logger_instance
        self.medical_fact_checker = medical_fact_checker_instance
        self.ethical_enforcer = ethical_enforcer_instance
        self.telemetry = telemetry_emitter_instance
        print("✅ ComplianceChecker initialized.")

    async def check_compliance(self, data: Dict[str, Any], region_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs compliance checks on a set of interaction data against region-specific rules.
        
        :param data: A dictionary containing all relevant interaction data (user input, AI response, etc.).
        :param region_config: The configuration for the specific region (e.g., USA, India).
        :return: A dictionary containing compliance status and any detected violations.
        """
        compliance_report = {
            "is_compliant": True,
            "violations": [],
            "recommendations": []
        }
        
        session_id = data.get("session_id", "unknown_session")
        user_id = data.get("user_id", "unknown_user")
        
        privacy_law = region_config.get("privacy_law", "UNKNOWN")
        
        print(f"Checking compliance for session {session_id} under {privacy_law}...")

        # 1. Check PII handling (via PIIScrubber and AuditLogger)
        if not data.get("pii_scrubbed_input") or not data.get("pii_scrubbed_output"):
             # This check assumes PII scrubbing would have been done earlier.
             # If raw data is still present, it's a violation.
            
            # Re-check for PII in original input/output if available
            original_input = data.get("user_input", "")
            original_output = data.get("ai_response", {}).get("response_text", "")

            if self.pii_scrubber.detect_pii(original_input) or self.pii_scrubber.detect_pii(original_output):
                compliance_report["is_compliant"] = False
                compliance_report["violations"].append({"type": "PII_UNSCRUBBED", "details": "PII detected in unscrubbed logs/data."})
                compliance_report["recommendations"].append("Ensure all raw inputs/outputs are scrubbed before logging/storage.")
                self.telemetry.emit_event("compliance_violation", {"session_id": session_id, "type": "PII_UNSCRUBBED", "privacy_law": privacy_law})

        # 2. Medical Accuracy (via MedicalFactChecker report)
        medical_fact_check_report = data.get("medical_fact_check_report", {})
        if medical_fact_check_report.get("verdict") == "unsafe":
            compliance_report["is_compliant"] = False
            compliance_report["violations"].append({"type": "MEDICAL_MISINFORMATION", "details": f"AI response contained unsafe medical claim: {medical_fact_check_report.get('claim')}"})
            compliance_report["recommendations"].append("Review LLM safety settings and prompt engineering to prevent unsafe medical claims.")
            self.telemetry.emit_event("compliance_violation", {"session_id": session_id, "type": "MEDICAL_MISINFORMATION"})

        # 3. Ethical Guidelines Adherence (via EthicalGuidelinesEnforcer flags)
        ethical_flags = data.get("ai_response", {}).get("ethical_flags", [])
        if "bias_detected" in json.dumps(ethical_flags): # Check if any bias flags exist
            compliance_report["is_compliant"] = False
            compliance_report["violations"].append({"type": "ETHICAL_BIAS", "details": "AI response detected with potential bias."})
            compliance_report["recommendations"].append("Investigate LLM response for fairness and bias. Adjust prompts or models.")
            self.telemetry.emit_event("compliance_violation", {"session_id": session_id, "type": "ETHICAL_BIAS"})
        
        # 4. Data Retention Policy (concept - relies on memory_manager and audit_logger)
        # This check is more about system configuration than per-interaction.
        # Example: if privacy_law is GDPR, then data for "x" category must be deleted after "y" days.
        if privacy_law == "GDPR" and not region_config.get("data_retention_policy_configured"):
            compliance_report["recommendations"].append("Define and implement clear data retention and deletion policies for GDPR compliance.")

        # 5. Consent Management (concept)
        # Check if user consent was properly obtained and recorded for data processing.
        # This would usually involve checking a consent database.
        if privacy_law in ["GDPR", "DPDP_2023"] and not data.get("user_consent_recorded"):
             compliance_report["recommendations"].append("Implement robust user consent mechanisms and ensure consent is recorded for data processing.")

        self.telemetry.emit_event("compliance_check_complete", {"session_id": session_id, "is_compliant": compliance_report["is_compliant"], "violations_count": len(compliance_report["violations"])})
        
        return compliance_report

    def generate_compliance_report(self, start_date: float, end_date: float) -> Dict[str, Any]:
        """
        Generates a summary compliance report for a given period.
        This would typically involve aggregating data from the audit log.
        """
        print(f"Generating compliance report from {time.ctime(start_date)} to {time.ctime(end_date)}.")
        
        # In a real system, query the audit_logger for events within the time frame.
        mock_report_data = {
            "period_start": start_date,
            "period_end": end_date,
            "total_interactions": 1000,
            "total_violations": 5,
            "violation_breakdown": {
                "PII_UNSCRUBBED": 2,
                "MEDICAL_MISINFORMATION": 1,
                "ETHICAL_BIAS": 2
            },
            "recommendations_summary": [
                "Review PII scrubbing configurations.",
                "Reinforce LLM safety prompts.",
                "Conduct regular bias audits."
            ]
        }
        self.telemetry.emit_event("compliance_report_generated", {"period_start": start_date, "period_end": end_date})
        return mock_report_data

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockPIIScrubber:
        def detect_pii(self, text: str) -> Dict[str, List[str]]:
            if "bad_email@example.com" in text:
                return {"email": ["bad_email@example.com"]}
            return {}
    class MockAuditLogger:
        pass
    class MockMedicalFactChecker:
        pass
    class MockEthicalGuidelinesEnforcer:
        pass
    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_pii = MockPIIScrubber()
    mock_audit = MockAuditLogger()
    mock_med_check = MockMedicalFactChecker()
    mock_ethical = MockEthicalGuidelinesEnforcer()
    mock_te = MockTelemetryEmitter()
    
    checker = ComplianceChecker(mock_pii, mock_audit, mock_med_check, mock_ethical, mock_te)
    
    # --- Mock Region Configs ---
    hipaa_config = {"privacy_law": "HIPAA", "data_retention_policy_configured": True}
    gdpr_config = {"privacy_law": "GDPR", "data_retention_policy_configured": False}
    dpdp_config = {"privacy_law": "DPDP_2023", "data_retention_policy_configured": True}

    # --- Test 1: Compliant interaction (HIPAA) ---
    print("\n--- Test 1: Compliant interaction (HIPAA) ---")
    compliant_data = {
        "session_id": "s_comp_1", "user_id": "u_comp_1",
        "user_input": "What is my prescription?",
        "ai_response": {"response_text": "I cannot provide personal health information.", "ethical_flags": ["transparency_disclaimer_added"]},
        "medical_fact_check_report": {"verdict": "safe"},
        "pii_scrubbed_input": True, "pii_scrubbed_output": True
    }
    report_compliant = asyncio.run(checker.check_compliance(compliant_data, hipaa_config))
    print(f"Report: {json.dumps(report_compliant, indent=2)}")

    # --- Test 2: PII Violation (GDPR) ---
    print("\n--- Test 2: PII Violation (GDPR) ---")
    pii_data = {
        "session_id": "s_pii_1", "user_id": "u_pii_1",
        "user_input": "My email is bad_email@example.com.", # PII present
        "ai_response": {"response_text": "I understand.", "ethical_flags": []},
        "medical_fact_check_report": {"verdict": "safe"},
        "pii_scrubbed_input": False, "pii_scrubbed_output": True, # Simulate scrubbing failed
    }
    report_pii = asyncio.run(checker.check_compliance(pii_data, gdpr_config))
    print(f"Report: {json.dumps(report_pii, indent=2)}")

    # --- Test 3: Medical Misinformation Violation (DPDP) ---
    print("\n--- Test 3: Medical Misinformation Violation (DPDP) ---")
    misinfo_data = {
        "session_id": "s_misinfo_1", "user_id": "u_misinfo_1",
        "user_input": "Tell me a cure for cancer.",
        "ai_response": {"response_text": "Drink this special tea for a cure.", "ethical_flags": ["transparency_disclaimer_added"]},
        "medical_fact_check_report": {"verdict": "unsafe", "claim": "Drink special tea for cancer cure"}, # Unsafe claim
        "pii_scrubbed_input": True, "pii_scrubbed_output": True
    }
    report_misinfo = asyncio.run(checker.check_compliance(misinfo_data, dpdp_config))
    print(f"Report: {json.dumps(report_misinfo, indent=2)}")

    # --- Test 4: Generate Compliance Report ---
    print("\n--- Test 4: Generate Compliance Report ---")
    current_time = time.time()
    one_week_ago = current_time - (7 * 24 * 3600)
    summary_report = checker.generate_compliance_report(one_week_ago, current_time)
    print(f"Summary Report: {json.dumps(summary_report, indent=2)}")
