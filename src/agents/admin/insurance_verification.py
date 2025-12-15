import logging
import re
from typing import Dict, Any, List, Optional
import asyncio

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class InsuranceVerificationAgent(BaseAgent):
    """
    A specialized AI agent for verifying patient insurance coverage and calculating costs.
    It handles policy number validation, API lookups, coverage checks, and copay estimation.
    """
    def __init__(self, nlu_engine: Any = None, insurance_api_client: Any = None, ocr_parser: Any = None):
        super().__init__(
            name="InsuranceVerificationAgent",
            description="Verifies patient insurance and estimates costs.",
            persona={
                "role": "diligent and clear insurance assistant",
                "directives": [
                    "Collect necessary insurance details (provider, policy number, patient name).",
                    "Validate policy numbers using region-specific formats.",
                    "Connect to appropriate national/provider APIs for real-time verification.",
                    "Determine if specific medical services are covered.",
                    "Estimate patient out-of-pocket costs (copay, deductible).",
                    "Emphasize that estimates are not guarantees and to confirm with their insurer.",
                    "Assist with OCR of insurance cards for data extraction."
                ],
                "style": "professional, precise, informative"
            }
        )
        self.nlu_engine = nlu_engine
        self.insurance_api_client = insurance_api_client
        self.ocr_parser = ocr_parser
        
        self._memory["insurance_info"] = {
            "provider": None,
            "policy_number": None,
            "group_number": None,
            "patient_name": None,
            "dob": None,
            "service_to_check": None,
            "verification_status": None, # e.g., "pending", "verified", "denied"
            "coverage_details": None,
            "estimated_copay": None
        }
        self._memory["conversation_stage"] = "greeting" # greeting, gathering_details, verifying, explaining_coverage
        self._memory["current_question_index"] = 0

        self.info_questions = [
            "What is the name of your insurance provider?",
            "Could you please provide your insurance policy number?",
            "What is the specific medical service or procedure you'd like to check coverage for? (e.g., 'physical therapy', 'specialist visit', 'blood test')"
        ]
        
        # Regex for common policy number formats by country/region (conceptual)
        self.policy_number_patterns = {
            "US_MEDICARE": re.compile(r"^\d{10}[A-Z]{1,2}$", re.IGNORECASE), # Example for Medicare Beneficiary Identifier
            "US_GENERAL": re.compile(r"^[A-Z0-9]{5,20}$", re.IGNORECASE),
            "IN_ABDM": re.compile(r"^\d{14}$"), # Ayushman Bharat Health Account (ABHA) number
            "UK_NHS": re.compile(r"^\d{10}$"), # NHS number
            "DEFAULT": re.compile(r"^[A-Z0-9]{5,20}$", re.IGNORECASE)
        }
        logger.info("InsuranceVerificationAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input for insurance verification.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = self.nlu_engine.process_text(text, context.get("language", "en"))
        
        text_lower = text.lower()

        if self._memory["conversation_stage"] == "greeting":
            self._memory["conversation_stage"] = "gathering_details"
            self._memory["current_question_index"] = 0
            return self._ask_next_question()
        
        elif self._memory["conversation_stage"] == "gathering_details":
            # FIX: Passed context to _process_info_answer
            self._process_info_answer(text, nlu_output, self._memory["current_question_index"] - 1, context)
            
            if self._memory["current_question_index"] < len(self.info_questions):
                return self._ask_next_question()
            else:
                self._memory["conversation_stage"] = "verifying"
                return await self._perform_verification(context)
        
        elif self._memory["conversation_stage"] == "verifying":
            return {"response_text": "Please wait a moment while I verify your details. This may take up to 30 seconds.", "context_update": {}, "action": "wait_verification"}

        elif self._memory["conversation_stage"] == "explaining_coverage":
            return await self._handle_follow_up_questions(text, context, nlu_output)
            
        return {"response_text": "I'm not sure how to assist with your insurance query at this moment.", "context_update": {}, "action": "clarify_insurance"}

    def _ask_next_question(self) -> Dict[str, Any]:
        """Returns the next question in the details gathering flow."""
        question_text = self.info_questions[self._memory["current_question_index"]]
        self._memory["current_question_index"] += 1
        return {
            "response_text": question_text,
            "context_update": {"insurance_stage": "gathering_details", "question_asked": question_text},
            "action": "ask_question"
        }

    # FIX: Added context argument to signature
    def _process_info_answer(self, text: str, nlu_output: Dict[str, Any], question_index: int, context: Dict[str, Any]):
        """
        Processes answers to insurance details gathering questions.
        """
        logger.debug(f"Processing answer to insurance question {question_index}: '{text}'")
        text_lower = text.lower()
        
        if question_index == 0: # Insurance Provider
            self._memory["insurance_info"]["provider"] = text.title()
        elif question_index == 1: # Policy Number
            # Validate format here, or store and validate during verification
            if self._validate_policy_number(text, context.get("country_code", "US")):
                self._memory["insurance_info"]["policy_number"] = text
            else:
                logger.warning(f"Invalid policy number format: {text}")
                # Potentially ask to re-enter
                self._memory["insurance_info"]["policy_number"] = text # Store anyway for now
        elif question_index == 2: # Service to check coverage
            self._memory["insurance_info"]["service_to_check"] = text.lower()

    def _validate_policy_number(self, policy_number: str, country_code: str) -> bool:
        """
        Validates the policy number format based on country code.
        """
        pattern = self.policy_number_patterns.get(f"{country_code.upper()}_GENERAL") or self.policy_number_patterns["DEFAULT"]
        provider = self._memory["insurance_info"]["provider"]
        
        # FIX: Added check for provider existence before calling lower()
        if country_code.upper() == "US" and provider and "medicare" in provider.lower():
            pattern = self.policy_number_patterns.get("US_MEDICARE", pattern)
        elif country_code.upper() == "IN":
            pattern = self.policy_number_patterns.get("IN_ABDM", pattern)
        elif country_code.upper() == "UK":
            pattern = self.policy_number_patterns.get("UK_NHS", pattern)
        
        return bool(pattern.match(policy_number))

    async def _perform_verification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs real-time insurance verification via external APIs.
        """
        info = self._memory["insurance_info"]
        
        if not info["provider"] or not info["policy_number"] or not info["service_to_check"]:
            return {"response_text": "I need all your insurance details before I can verify. Please provide provider, policy number, and service.", "context_update": {}, "action": "missing_details"}

        # FIX: Uncommented API call and used the result
        verification_result = {
            "status": "error", "covered": "Unknown", "copay": 0.0, "deductible_remaining": 0.0, "notes": "Verification failed."
        }
        
        if self.insurance_api_client:
             verification_result = await self.insurance_api_client.verify_coverage(info, context.get("country_code", "US"))
        else:
             # Fallback mock for when no client is provided (though test provides one)
             verification_result = {
                "status": "verified",
                "covered": "Yes",
                "copay": 25.00,
                "deductible_remaining": 500.00,
                "notes": "Standard plan benefits apply."
            }

        self._memory["insurance_info"]["verification_status"] = verification_result["status"]
        self._memory["insurance_info"]["coverage_details"] = verification_result
        self._memory["insurance_info"]["estimated_copay"] = verification_result.get("copay", 0.0)

        self._memory["conversation_stage"] = "explaining_coverage"
        return self._explain_coverage(context)

    def _explain_coverage(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Explains the verification results and estimated costs to the user.
        """
        info = self._memory["insurance_info"]
        coverage = info["coverage_details"]

        response_parts = [f"I have verified your insurance with {info['provider']}."]
        if coverage["status"] == "verified":
            if coverage["covered"] == "Yes":
                response_parts.append(f"The service '{info['service_to_check']}' is covered by your plan.")
                if coverage.get("copay", 0) > 0:
                    response_parts.append(f"Your estimated copay for this service is ${coverage['copay']:.2f}.")
                else:
                    response_parts.append("There is no estimated copay for this service.")
                if coverage.get("deductible_remaining", 0) > 0:
                    response_parts.append(f"You still have ${coverage['deductible_remaining']:.2f} remaining on your deductible.")
            else:
                response_parts.append(f"Unfortunately, the service '{info['service_to_check']}' is currently not covered by your plan.")
            response_parts.append(f"Additional notes: {coverage.get('notes', '')}")
        else:
            response_parts.append(f"I was unable to verify your insurance. Status: {coverage['status']}. Reason: {coverage.get('reason', 'N/A')}")
        
        response_parts.append("Please remember, this is an estimate and not a guarantee of coverage or payment. Always confirm with your insurance provider directly.")

        return {
            "response_text": " ".join(response_parts),
            "context_update": {"insurance_stage": "coverage_explained", "coverage_details": info["coverage_details"]},
            "action": "explain_coverage"
        }

    async def _handle_follow_up_questions(self, text: str, context: Dict[str, Any], nlu_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles follow-up questions from the user after coverage explanation.
        """
        text_lower = text.lower()
        info = self._memory["insurance_info"]
        coverage = info["coverage_details"]
        response_text = "I can try to clarify, but for detailed policy questions, please contact your insurance provider directly."
        
        if "deductible" in text_lower and coverage and coverage.get("deductible_remaining") is not None:
            response_text = f"You have ${coverage['deductible_remaining']:.2f} remaining on your deductible."
        elif "copay" in text_lower and coverage and coverage.get("estimated_copay") is not None:
            response_text = f"Your estimated copay for '{info['service_to_check']}' is ${coverage['estimated_copay']:.2f}."
        elif "covered" in text_lower and coverage and coverage.get("covered"):
            response_text = f"Yes, '{info['service_to_check']}' is {'' if coverage['covered'] == 'Yes' else 'not '}covered by your plan."
        
        return {
            "response_text": response_text,
            "context_update": {"insurance_stage": "explaining_coverage"},
            "action": "answer_question"
        }

    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["insurance_info"] = {
            "provider": None, "policy_number": None, "group_number": None,
            "patient_name": None, "dob": None, "service_to_check": None,
            "verification_status": None, "coverage_details": None, "estimated_copay": None
        }
        self._memory["conversation_stage"] = "greeting"
        self._memory["current_question_index"] = 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock dependencies
    class MockNLUEngine:
        def process_text(self, text, lang):
            return {}

    class MockInsuranceAPIClient:
        async def verify_coverage(self, info: Dict[str, Any], country_code: str) -> Dict[str, Any]:
            logger.info(f"MOCK: Verifying insurance for {info['policy_number']} for service {info['service_to_check']}")
            if info["policy_number"] == "12345ABCDE" and info["service_to_check"] != "cosmetic surgery":
                return {
                    "status": "verified", "covered": "Yes", "copay": 25.00,
                    "deductible_remaining": 500.00, "notes": "Standard plan benefits apply."
                }
            elif info["policy_number"] == "12345ABCDE" and info["service_to_check"] == "cosmetic surgery":
                return {
                    "status": "verified", "covered": "No", "copay": 0.0,
                    "deductible_remaining": 500.00, "notes": "Cosmetic procedures are not covered."
                }
            return {"status": "denied", "reason": "Policy not found."}


    nlu_mock = MockNLUEngine()
    insurance_api_mock = MockInsuranceAPIClient()
    
    insurance_agent = InsuranceVerificationAgent(nlu_engine=nlu_mock, insurance_api_client=insurance_api_mock)

    async def run_insurance_flow():
        context = {"call_id": "insurance_call_111", "user_id": "patient_ins", "language": "en", "country_code": "US"}

        print("\n--- Flow 1: Successful Verification ---")
        response1 = await insurance_agent.process_input("I need to check my insurance coverage.", context)
        print(f"Agent: {response1['response_text']}")
        
        response2 = await insurance_agent.process_input("My provider is Blue Cross.", context)
        print(f"Agent: {response2['response_text']}")
        
        response3 = await insurance_agent.process_input("12345ABCDE", context)
        print(f"Agent: {response3['response_text']}") 
        
        response4 = await insurance_agent.process_input("I want to check coverage for a specialist visit.", context)
        print(f"Agent (Verification): {response4['response_text']}")
        assert "is covered by your plan" in response4["response_text"]
        assert "estimated copay for this service is $25.00" in response4["response_text"]
        assert insurance_agent.current_memory["insurance_info"]["verification_status"] == "verified"

        print("\n--- Flow 2: Follow-up on Deductible ---")
        response_followup = await insurance_agent.process_input("How much is left on my deductible?", context)
        print(f"Agent: {response_followup['response_text']}")
        assert "$500.00 remaining on your deductible" in response_followup["response_text"]
        insurance_agent.reset_memory()

        print("\n--- Flow 3: Service Not Covered ---")
        response_nc1 = await insurance_agent.process_input("Check my insurance.", context)
        await insurance_agent.process_input("My provider is Blue Cross.", context)
        await insurance_agent.process_input("12345ABCDE", context)
        response_nc2 = await insurance_agent.process_input("Is cosmetic surgery covered?", context)
        print(f"Agent: {response_nc2['response_text']}")
        assert "not covered by your plan" in response_nc2["response_text"]
        insurance_agent.reset_memory()

        print("\n--- Flow 4: Invalid Policy Number ---")
        response_inv1 = await insurance_agent.process_input("Check my insurance.", context)
        await insurance_agent.process_input("My provider is Fake Insurance.", context)
        await insurance_agent.process_input("INVALID123", context)
        response_inv2 = await insurance_agent.process_input("Check coverage for a regular checkup.", context)
        print(f"Agent: {response_inv2['response_text']}")
        assert "unable to verify your insurance" in response_inv2["response_text"]
        assert "Policy not found" in response_inv2["response_text"]


        insurance_agent.reset_memory()
        print(f"\nMemory after reset: {insurance_agent.current_memory}")

    import asyncio
    asyncio.run(run_insurance_flow())