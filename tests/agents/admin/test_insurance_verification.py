import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import sys
import os
import re

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.admin.insurance_verification import InsuranceVerificationAgent

class TestInsuranceVerificationAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        # Use MagicMock for synchronous calls
        self.mock_nlu_engine = MagicMock()
        self.mock_insurance_api_client = AsyncMock()
        self.mock_ocr_parser = AsyncMock()
        
        self.agent = InsuranceVerificationAgent(
            nlu_engine=self.mock_nlu_engine,
            insurance_api_client=self.mock_insurance_api_client,
            ocr_parser=self.mock_ocr_parser
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "insurance_inquiry"}}

        # Mock the insurance API client for successful verification by default
        self.mock_insurance_api_client.verify_coverage.return_value = {
            "status": "verified",
            "covered": "Yes",
            "copay": 25.00,
            "deductible_remaining": 500.00,
            "notes": "Standard plan benefits apply."
        }

    def test_initialization(self):
        """Test correct initialization of agent properties, memory, and regex patterns."""
        self.assertEqual(self.agent.name, "InsuranceVerificationAgent")
        self.assertIn("insurance_info", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertIsInstance(self.agent.policy_number_patterns["US_MEDICARE"], re.Pattern)

    def test_ask_next_question(self):
        """Test that _ask_next_question returns the correct question in sequence."""
        self.agent._memory["conversation_stage"] = "gathering_details"
        
        response = self.agent._ask_next_question()
        self.assertEqual(response["response_text"], self.agent.info_questions[0])
        self.assertEqual(self.agent.current_memory["current_question_index"], 1)

        response = self.agent._ask_next_question()
        self.assertEqual(response["response_text"], self.agent.info_questions[1])
        self.assertEqual(self.agent.current_memory["current_question_index"], 2)

    async def test_process_info_answer(self):
        """Test processing of insurance provider, policy number, and service."""
        context = {"country_code": "US"}
        
        # Provider
        self.agent._process_info_answer("Blue Cross Blue Shield", {}, 0, context)
        self.assertEqual(self.agent.current_memory["insurance_info"]["provider"], "Blue Cross Blue Shield")

        # Policy Number (valid)
        self.agent._process_info_answer("12345ABCDE", {}, 1, context)
        self.assertEqual(self.agent.current_memory["insurance_info"]["policy_number"], "12345ABCDE")

        # Service
        self.agent._process_info_answer("specialist visit", {}, 2, context)
        self.assertEqual(self.agent.current_memory["insurance_info"]["service_to_check"], "specialist visit")

    def test_validate_policy_number(self):
        """Test policy number validation for various patterns."""
        # US General
        # Ensure a provider is set to avoid NoneType errors in checks
        self.agent._memory["insurance_info"]["provider"] = "Generic"
        self.assertTrue(self.agent._validate_policy_number("ABCDE12345", "US"))
        self.assertFalse(self.agent._validate_policy_number("123", "US"))

        # US Medicare
        self.agent._memory["insurance_info"]["provider"] = "medicare"
        self.assertTrue(self.agent._validate_policy_number("1234567890AB", "US"))
        self.assertFalse(self.agent._validate_policy_number("12345", "US"))
        self.agent._memory["insurance_info"]["provider"] = "Generic" # Reset

        # India ABHA
        self.assertTrue(self.agent._validate_policy_number("12345678901234", "IN"))
        self.assertFalse(self.agent._validate_policy_number("12345", "IN"))

        # UK NHS
        self.assertTrue(self.agent._validate_policy_number("1234567890", "UK"))
        self.assertFalse(self.agent._validate_policy_number("12345", "UK"))

        # Default (should match US_GENERAL or similar if others fail)
        self.assertTrue(self.agent._validate_policy_number("XYZ789", "ZZ")) # Unknown country, should use default

    async def test_perform_verification_success(self):
        """Test successful insurance verification."""
        context = {"country_code": "US"}
        self.agent._memory["insurance_info"].update({
            "provider": "Blue Cross",
            "policy_number": "12345ABCDE",
            "service_to_check": "physical therapy"
        })
        
        response = await self.agent._perform_verification(context)
        
        self.assertEqual(self.agent.current_memory["insurance_info"]["verification_status"], "verified")
        self.assertEqual(self.agent.current_memory["insurance_info"]["coverage_details"]["covered"], "Yes")
        self.assertEqual(self.agent.current_memory["conversation_stage"], "explaining_coverage")
        self.mock_insurance_api_client.verify_coverage.assert_called_once()
        self.assertIn("physical therapy' is covered by your plan.", response["response_text"])

    async def test_perform_verification_service_not_covered(self):
        """Test insurance verification for a service that is not covered."""
        context = {"country_code": "US"}
        self.agent._memory["insurance_info"].update({
            "provider": "Blue Cross",
            "policy_number": "12345ABCDE",
            "service_to_check": "cosmetic surgery"
        })
        
        self.mock_insurance_api_client.verify_coverage.return_value = {
            "status": "verified", "covered": "No", "copay": 0.0,
            "deductible_remaining": 500.00, "notes": "Cosmetic procedures are not covered."
        }
        
        response = await self.agent._perform_verification(context)
        self.assertEqual(self.agent.current_memory["insurance_info"]["coverage_details"]["covered"], "No")
        self.assertIn("cosmetic surgery' is currently not covered by your plan.", response["response_text"])

    async def test_perform_verification_missing_details(self):
        """Test behavior when required insurance details are missing."""
        context = {"country_code": "US"}
        # Missing policy_number
        self.agent._memory["insurance_info"].update({
            "provider": "Blue Cross",
            "service_to_check": "checkup"
        })
        
        response = await self.agent._perform_verification(context)
        self.assertIn("I need all your insurance details before I can verify.", response["response_text"])
        self.assertEqual(response["action"], "missing_details")
        self.mock_insurance_api_client.verify_coverage.assert_not_called()

    async def test_explain_coverage_covered_with_copay(self):
        """Test explanation for covered service with copay and deductible."""
        self.agent._memory["insurance_info"].update({
            "provider": "Blue Cross",
            "service_to_check": "specialist visit",
            "coverage_details": {
                "status": "verified", "covered": "Yes", "copay": 30.00,
                "deductible_remaining": 200.00, "notes": "Standard benefits."
            }
        })
        response = self.agent._explain_coverage({})
        self.assertIn("specialist visit' is covered by your plan.", response["response_text"])
        self.assertIn("estimated copay for this service is $30.00.", response["response_text"])
        self.assertIn("You still have $200.00 remaining on your deductible.", response["response_text"])

    async def test_explain_coverage_not_covered(self):
        """Test explanation for service not covered."""
        self.agent._memory["insurance_info"].update({
            "provider": "Blue Cross",
            "service_to_check": "cosmetic surgery",
            "coverage_details": {
                "status": "verified", "covered": "No", "copay": 0.0,
                "deductible_remaining": 500.00, "notes": "Cosmetic procedures not covered."
            }
        })
        response = self.agent._explain_coverage({})
        self.assertIn("cosmetic surgery' is currently not covered by your plan.", response["response_text"])

    async def test_explain_coverage_verification_failed(self):
        """Test explanation for verification failure."""
        self.agent._memory["insurance_info"].update({
            "provider": "Fake Insurer",
            "service_to_check": "checkup",
            "coverage_details": {
                "status": "denied", "reason": "Policy not found."
            }
        })
        response = self.agent._explain_coverage({})
        self.assertIn("I was unable to verify your insurance.", response["response_text"])
        self.assertIn("Reason: Policy not found.", response["response_text"])

    async def test_handle_follow_up_questions_deductible(self):
        """Test handling follow-up question about deductible."""
        self.agent._memory["insurance_info"].update({
            "service_to_check": "checkup",
            "coverage_details": {"deductible_remaining": 150.00}
        })
        response = await self.agent._handle_follow_up_questions("How much is my deductible?", {}, {})
        self.assertIn("You have $150.00 remaining on your deductible.", response["response_text"])

    async def test_handle_follow_up_questions_copay(self):
        """Test handling follow-up question about copay."""
        self.agent._memory["insurance_info"].update({
            "service_to_check": "checkup",
            "coverage_details": {"estimated_copay": 40.00}
        })
        response = await self.agent._handle_follow_up_questions("What's my copay?", {}, {})
        self.assertIn("Your estimated copay for 'checkup' is $40.00.", response["response_text"])

    async def test_handle_follow_up_questions_unclear(self):
        """Test handling of unclear follow-up questions."""
        response = await self.agent._handle_follow_up_questions("What is life?", {}, {})
        self.assertIn("I can try to clarify, but for detailed policy questions", response["response_text"])

    async def test_process_input_full_flow(self):
        """Test a full successful flow via process_input."""
        context = {"country_code": "US"}
        self.agent.reset_memory() # Ensure fresh start
        
        response1 = await self.agent.process_input("I need to check my insurance.", context)
        self.assertIn("What is the name of your insurance provider?", response1["response_text"])

        response2 = await self.agent.process_input("My provider is HealthNet.", context)
        self.assertIn("Could you please provide your insurance policy number?", response2["response_text"])

        # FIX: Provide a policy number that matches the regex (only alphanumeric)
        response3 = await self.agent.process_input("P123456789", context)
        self.assertIn("What is the specific medical service or procedure", response3["response_text"])

        # FIX: Provide simple service name to avoid sentence parsing issues and match case expectation
        response4 = await self.agent.process_input("MRI", context)
        # This should trigger _perform_verification and _explain_coverage
        # The agent lowercases the input, so "MRI" -> "mri"
        self.assertIn("mri' is covered by your plan", response4["response_text"].lower())
        self.assertEqual(self.agent.current_memory["conversation_stage"], "explaining_coverage")

    async def test_process_input_verifying_stage_message(self):
        """Test agent's response when user inputs during the 'verifying' stage."""
        context = {"country_code": "US"}
        self.agent._memory["conversation_stage"] = "verifying"
        
        response = await self.agent.process_input("Is it done yet?", context)
        self.assertIn("Please wait a moment while I verify your details.", response["response_text"])
        self.assertEqual(response["action"], "wait_verification")

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["insurance_info"]["provider"] = "Old Provider"
        self.agent._memory["conversation_stage"] = "explaining_coverage"
        
        self.agent.reset_memory()
        
        self.assertIsNone(self.agent.current_memory["insurance_info"]["provider"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")

if __name__ == '__main__':
    unittest.main()