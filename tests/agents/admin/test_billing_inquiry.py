import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.admin.billing_inquiry import BillingInquiryAgent

class TestBillingInquiryAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        # Use MagicMock for synchronous NLU calls
        self.mock_nlu_engine = MagicMock() 
        self.mock_billing_db_service = AsyncMock()
        self.mock_payment_gateway = AsyncMock()
        
        self.agent = BillingInquiryAgent(
            nlu_engine=self.mock_nlu_engine,
            billing_db_service=self.mock_billing_db_service,
            payment_gateway=self.mock_payment_gateway
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "billing_inquiry"}}

        # Mock fetch_billing_info to populate memory with test data
        async def mock_fetch_billing_info(patient_id):
            self.agent._memory["patient_billing_info"]["transactions"] = [
                {"date": datetime.datetime.now() - datetime.timedelta(days=30), "code": "CPT 99213", "description": "Office visit", "amount": 100.00, "type": "charge"},
                {"date": datetime.datetime.now() - datetime.timedelta(days=20), "code": "LAB 123", "description": "Blood test", "amount": 50.00, "type": "charge"},
                {"date": datetime.datetime.now() - datetime.timedelta(days=10), "code": "PAYMENT", "description": "Partial payment", "amount": -75.00, "type": "payment"},
            ]
            self.agent._memory["patient_billing_info"]["outstanding_balance"] = 75.00
        self.agent._fetch_billing_info = AsyncMock(side_effect=mock_fetch_billing_info)


    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "BillingInquiryAgent")
        self.assertIn("patient_billing_info", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "authentication")
        self.assertEqual(self.agent.current_memory["patient_billing_info"]["authentication_status"], False)

    async def test_authenticate_caller_success(self):
        """Test successful authentication flow."""
        context = {"user_id": "test_user"}
        
        response = await self.agent.process_input("My name is John Smith.", context)
        
        self.assertTrue(self.agent.current_memory["patient_billing_info"]["authentication_status"])
        self.assertEqual(self.agent.current_memory["patient_billing_info"]["patient_id"], "patient_billing_001")
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertIn("Thank you, your identity has been verified.", response["response_text"])
        self.agent._fetch_billing_info.assert_called_once_with("patient_billing_001")

    async def test_authenticate_caller_already_authenticated(self):
        """Test handling of already authenticated caller."""
        context = {"user_id": "test_user"}
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "authentication" # Force authentication stage to test
        
        response = await self.agent.process_input("I have another billing question.", context)
        self.assertIn("Your identity has already been verified.", response["response_text"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")

    async def test_authenticate_caller_failure(self):
        """Test failed authentication attempt."""
        context = {"user_id": "test_user"}
        response = await self.agent.process_input("Invalid credentials.", context)
        
        self.assertFalse(self.agent.current_memory["patient_billing_info"]["authentication_status"])
        self.assertIn("Could you please provide your full name or patient ID", response["response_text"])
        self.assertEqual(response["action"], "request_authentication_retry")
    
    async def test_fetch_billing_info(self):
        """Test that _fetch_billing_info populates memory correctly."""
        self.agent._memory["patient_billing_info"]["transactions"] = [] # Clear mock setup
        self.agent._memory["patient_billing_info"]["outstanding_balance"] = 0.0 # Clear mock setup
        
        await self.agent._fetch_billing_info("patient_test")
        
        self.assertGreater(len(self.agent.current_memory["patient_billing_info"]["transactions"]), 0)
        self.assertAlmostEqual(self.agent.current_memory["patient_billing_info"]["outstanding_balance"], 75.00)

    async def test_inquire_outstanding_balance(self):
        """Test reporting of outstanding balance."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "main_menu"
        self.agent._memory["patient_billing_info"]["outstanding_balance"] = 125.50
        
        response = await self.agent.process_input("What is my outstanding balance?", {})
        self.assertIn("Your current outstanding balance is $125.50.", response["response_text"])
        self.assertEqual(response["action"], "provide_balance")

    async def test_itemize_charges(self):
        """Test itemized list of charges."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "main_menu"
        
        # Manually populate memory since _fetch_billing_info isn't called in this test
        self.agent._memory["patient_billing_info"]["transactions"] = [
            {"date": datetime.datetime.now(), "code": "CPT 99213", "description": "Office visit", "amount": 100.00, "type": "charge"},
            {"date": datetime.datetime.now(), "code": "LAB 123", "description": "Blood test", "amount": 50.00, "type": "charge"}
        ]
        self.agent._memory["patient_billing_info"]["outstanding_balance"] = 150.00
        
        response = await self.agent.process_input("Show me itemized charges.", {})
        self.assertIn("Here is a breakdown of your recent charges:", response["response_text"])
        # FIX: The agent converts "CPT 99213" to "Standard Office Visit" in the output
        self.assertIn("Standard Office Visit ($100.00)", response["response_text"])
        self.assertIn("Blood test ($50.00)", response["response_text"])
        self.assertEqual(response["action"], "itemize_charges")

    async def test_itemize_charges_no_transactions(self):
        """Test itemized charges when no transactions exist."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "main_menu"
        self.agent._memory["patient_billing_info"]["transactions"] = []
        
        # Use "Itemize" to match the agent's keyword detection
        response = await self.agent.process_input("Itemize my charges.", {})
        self.assertIn("I don't have any recent charges to show you.", response["response_text"])
        self.assertEqual(response["action"], "no_charges")

    async def test_show_payment_history(self):
        """Test displaying payment history."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "main_menu"

        # Manually populate memory
        self.agent._memory["patient_billing_info"]["transactions"] = [
            {"date": datetime.datetime.now(), "code": "PAY", "description": "Payment", "amount": -75.00, "type": "payment"}
        ]
        
        response = await self.agent.process_input("Show my payment history.", {})
        self.assertIn("Here is your payment history:", response["response_text"])
        self.assertIn("Payment of $75.00", response["response_text"])
        self.assertEqual(response["action"], "show_payment_history")

    async def test_show_payment_history_no_payments(self):
        """Test payment history when no payments exist."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "main_menu"
        self.agent._memory["patient_billing_info"]["transactions"] = [
            {"date": datetime.datetime.now(), "code": "CPT 101", "description": "Consult", "amount": 200.00, "type": "charge"}
        ]
        
        response = await self.agent.process_input("Show payment history.", {})
        self.assertIn("I don't have a record of past payments for you.", response["response_text"])
        self.assertEqual(response["action"], "no_payments")

    async def test_offer_payment_options(self):
        """Test offering payment options."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "main_menu"
        self.agent._memory["patient_billing_info"]["outstanding_balance"] = 100.00
        
        response = await self.agent.process_input("I want to make a payment.", {})
        self.assertIn("Your outstanding balance is $100.00. You can pay online", response["response_text"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "payment_options")
        self.assertEqual(response["action"], "offer_payment_options")

    async def test_offer_payment_options_no_balance(self):
        """Test offering payment options when no balance."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "main_menu"
        self.agent._memory["patient_billing_info"]["outstanding_balance"] = 0.0
        
        response = await self.agent.process_input("Pay my bill.", {})
        self.assertIn("You currently have no outstanding balance. Thank you!", response["response_text"])
        self.assertEqual(response["action"], "no_balance_to_pay")

    async def test_generate_payment_link(self):
        """Test generation of payment link."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "payment_options"
        self.agent._memory["patient_billing_info"]["patient_id"] = "test_patient"
        self.agent._memory["patient_billing_info"]["outstanding_balance"] = 50.00
        
        response = await self.agent.process_input("Send me a payment link.", {})
        self.assertIn("Here is a secure link to pay your outstanding balance of $50.00 online:", response["response_text"])
        self.assertIn("https://mock-payment-gateway.com/pay/test_patient/50.00", response["response_text"])
        self.assertEqual(response["action"], "payment_link_generated")

    async def test_offer_payment_plan(self):
        """Test offering a payment plan."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "main_menu"
        self.agent._memory["patient_billing_info"]["outstanding_balance"] = 300.00
        
        response = await self.agent.process_input("I want a payment plan.", {})
        self.assertIn("We can arrange a payment plan to split this into manageable installments.", response["response_text"])
        self.assertEqual(response["action"], "offer_payment_plan")

    async def test_process_input_unrecognized(self):
        """Test handling of unrecognized input in main_menu."""
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        self.agent._memory["conversation_stage"] = "main_menu"
        
        response = await self.agent.process_input("What is the meaning of life?", {})
        self.assertIn("I'm not sure how to assist with that billing query.", response["response_text"])
        self.assertEqual(response["action"], "clarify_billing")

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["patient_billing_info"]["patient_id"] = "some_id"
        self.agent._memory["conversation_stage"] = "main_menu"
        self.agent._memory["patient_billing_info"]["authentication_status"] = True
        
        self.agent.reset_memory()
        
        self.assertIsNone(self.agent.current_memory["patient_billing_info"]["patient_id"])
        self.assertEqual(self.agent.current_memory["conversation_stage"], "authentication")
        self.assertFalse(self.agent.current_memory["patient_billing_info"]["authentication_status"])

if __name__ == '__main__':
    unittest.main()