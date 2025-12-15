import logging
import datetime
from typing import Dict, Any, List, Optional
import asyncio
import re

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class BillingInquiryAgent(BaseAgent):
    """
    A specialized AI agent for handling patient billing inquiries.
    It retrieves and explains charges, shows payment history and outstanding balances,
    and can facilitate payments or payment plan arrangements.
    """
    def __init__(self, nlu_engine: Any = None, billing_db_service: Any = None, payment_gateway: Any = None):
        super().__init__(
            name="BillingInquiryAgent",
            description="Handles patient billing inquiries and payment facilitation.",
            persona={
                "role": "clear and helpful billing assistant",
                "directives": [
                    "Access patient billing ledger securely.",
                    "Explain charges clearly, using plain English for medical codes.",
                    "Provide current outstanding balance and payment history.",
                    "Offer secure payment options (e.g., payment links).",
                    "Discuss and facilitate payment plans for larger amounts.",
                    "Maintain a professional and empathetic tone, especially regarding sensitive financial matters."
                ],
                "style": "professional, precise, empathetic"
            }
        )
        self.nlu_engine = nlu_engine
        self.billing_db_service = billing_db_service
        self.payment_gateway = payment_gateway
        
        self._memory["patient_billing_info"] = {
            "patient_id": None,
            "authentication_status": False,
            "outstanding_balance": 0.0,
            "transactions": [] # List of {"date", "description", "amount", "type": "charge"/"payment"}
        }
        self._memory["conversation_stage"] = "authentication" # authentication, main_menu, itemizing_charges, payment_options
        self._memory["current_question_index"] = 0

        self.authentication_questions = [
            "To access your billing information, could you please provide your full name or patient ID for verification?"
        ]
        logger.info("BillingInquiryAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input for billing inquiries.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = self.nlu_engine.process_text(text, context.get("language", "en"))
        
        text_lower = text.lower()

        if self._memory["conversation_stage"] == "authentication":
            return await self._authenticate_caller(text, context)
        
        elif not self._memory["patient_billing_info"]["authentication_status"]:
            return {"response_text": "I need to verify your identity to access your billing information. Please provide your verification details.", "context_update": {}, "action": "request_authentication"}

        elif self._memory["conversation_stage"] == "main_menu":
            if "outstanding balance" in text_lower or "how much do i owe" in text_lower:
                return await self._inquire_outstanding_balance(context)
            # FIX: Added "itemize" to support "itemize my charges"
            elif "itemized" in text_lower or "itemize" in text_lower or "breakdown" in text_lower:
                return await self._itemize_charges(context)
            elif "payment history" in text_lower or "past payments" in text_lower:
                return await self._show_payment_history(context)
            elif "make a payment" in text_lower or "pay my bill" in text_lower:
                return await self._offer_payment_options(context)
            elif "payment plan" in text_lower or "installments" in text_lower:
                return await self._offer_payment_plan(context)
        
        elif self._memory["conversation_stage"] == "payment_options":
            # Assuming user is responding to payment options
            if "link" in text_lower or "online" in text_lower:
                return await self._generate_payment_link(context)
            elif "plan" in text_lower:
                return await self._offer_payment_plan(context)
            
        return {"response_text": "I'm not sure how to assist with that billing query. Would you like to know your balance, itemized charges, or make a payment?", "context_update": {}, "action": "clarify_billing"}

    async def _authenticate_caller(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conceptual caller authentication.
        For now, a simple keyword-based mock.
        """
        if self._memory["patient_billing_info"]["authentication_status"]:
            # FIX: Explicitly set conversation stage to main_menu if already authenticated
            self._memory["conversation_stage"] = "main_menu"
            return {"response_text": "Your identity has already been verified. How can I help you with your billing?", "context_update": {"billing_stage": "main_menu"}, "action": "prompt_main_menu"}

        # Mock authentication logic
        if "my name is john smith" in text.lower() or "my patient id is 12345" in text.lower(): # Simple mock
            self._memory["patient_billing_info"]["patient_id"] = "patient_billing_001"
            self._memory["patient_billing_info"]["authentication_status"] = True
            logger.info(f"Caller authenticated for patient_id: {self._memory['patient_billing_info']['patient_id']}")
            
            # Fetch billing info immediately after authentication (conceptual)
            await self._fetch_billing_info(self._memory["patient_billing_info"]["patient_id"])
            
            self._memory["conversation_stage"] = "main_menu"
            return {"response_text": "Thank you, your identity has been verified. How can I help you with your billing today?", "context_update": {"billing_stage": "main_menu"}, "action": "prompt_main_menu"}
        else:
            return {"response_text": "Could you please provide your full name or patient ID to securely verify your identity and access your billing information?", "context_update": {"billing_stage": "authentication_failed"}, "action": "request_authentication_retry"}

    async def _fetch_billing_info(self, patient_id: str):
        """
        Conceptual method to fetch billing information from a database.
        """
        # mock_transactions = await self.billing_db_service.get_ledger(patient_id)
        mock_transactions = [
            {"date": datetime.datetime.now() - datetime.timedelta(days=30), "code": "CPT 99213", "description": "Office visit", "amount": 100.00, "type": "charge"},
            {"date": datetime.datetime.now() - datetime.timedelta(days=20), "code": "LAB 123", "description": "Blood test", "amount": 50.00, "type": "charge"},
            {"date": datetime.datetime.now() - datetime.timedelta(days=10), "code": "PAYMENT", "description": "Partial payment", "amount": -75.00, "type": "payment"},
        ]
        self._memory["patient_billing_info"]["transactions"] = mock_transactions
        self._memory["patient_billing_info"]["outstanding_balance"] = sum(t["amount"] for t in mock_transactions)
        logger.info(f"Fetched billing info for {patient_id}. Balance: {self._memory['patient_billing_info']['outstanding_balance']:.2f}")

    async def _inquire_outstanding_balance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provides the current outstanding balance.
        """
        balance = self._memory["patient_billing_info"]["outstanding_balance"]
        response_text = f"Your current outstanding balance is ${balance:.2f}. Would you like to make a payment, or see an itemized list of charges?"
        self._memory["conversation_stage"] = "main_menu" # Stay in main menu but prompt payment
        return {"response_text": response_text, "context_update": {"billing_stage": "balance_provided"}, "action": "provide_balance"}

    async def _itemize_charges(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provides an itemized list of charges in plain English.
        """
        transactions = self._memory["patient_billing_info"]["transactions"]
        if not transactions:
            return {"response_text": "I don't have any recent charges to show you.", "context_update": {}, "action": "no_charges"}

        charge_details = ["Here is a breakdown of your recent charges:"]
        for t in transactions:
            if t["type"] == "charge":
                # Conceptual CPT code explanation
                plain_english_desc = t["description"]
                if t["code"] == "CPT 99213": plain_english_desc = "Standard Office Visit"
                
                charge_details.append(f"- On {t['date'].strftime('%b %d, %Y')}: {plain_english_desc} (${t['amount']:.2f})")
        
        response_text = " ".join(charge_details)
        response_text += f"\nYour total outstanding balance is ${self._memory['patient_billing_info']['outstanding_balance']:.2f}. Would you like to make a payment?"

        self._memory["conversation_stage"] = "main_menu"
        return {"response_text": response_text, "context_update": {"billing_stage": "charges_itemized"}, "action": "itemize_charges"}

    async def _show_payment_history(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Displays a history of past payments.
        """
        transactions = self._memory["patient_billing_info"]["transactions"]
        payments = [t for t in transactions if t["type"] == "payment"]

        if not payments:
            return {"response_text": "I don't have a record of past payments for you.", "context_update": {}, "action": "no_payments"}
        
        payment_details = ["Here is your payment history:"]
        for p in payments:
            payment_details.append(f"- On {p['date'].strftime('%b %d, %Y')}: Payment of ${abs(p['amount']):.2f}")
        
        response_text = " ".join(payment_details)
        response_text += f"\nYour current outstanding balance is ${self._memory['patient_billing_info']['outstanding_balance']:.2f}."

        self._memory["conversation_stage"] = "main_menu"
        return {"response_text": response_text, "context_update": {"billing_stage": "history_shown"}, "action": "show_payment_history"}

    async def _offer_payment_options(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Offers ways to make a payment.
        """
        balance = self._memory["patient_billing_info"]["outstanding_balance"]
        if balance <= 0:
            return {"response_text": "You currently have no outstanding balance. Thank you!", "context_update": {"billing_stage": "no_balance"}, "action": "no_balance_to_pay"}

        response_text = f"Your outstanding balance is ${balance:.2f}. You can pay online using a secure link, or we can discuss setting up a payment plan. Which would you prefer?"
        self._memory["conversation_stage"] = "payment_options"
        return {"response_text": response_text, "context_update": {"billing_stage": "offering_payment_options"}, "action": "offer_payment_options"}

    async def _generate_payment_link(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a secure online payment link.
        """
        balance = self._memory["patient_billing_info"]["outstanding_balance"]
        if balance <= 0:
            return {"response_text": "You currently have no outstanding balance. Thank you!", "context_update": {"billing_stage": "no_balance"}, "action": "no_balance_to_pay"}

        # Conceptual call to payment gateway
        # payment_link = await self.payment_gateway.generate_link(self._memory["patient_billing_info"]["patient_id"], balance)
        payment_link = f"https://mock-payment-gateway.com/pay/{self._memory['patient_billing_info']['patient_id']}/{balance:.2f}"
        
        response_text = f"Here is a secure link to pay your outstanding balance of ${balance:.2f} online: {payment_link}. We can also send this link to your registered mobile number via SMS. Would you like that?"
        self._memory["conversation_stage"] = "main_menu" # After providing link, return to main menu
        return {"response_text": response_text, "context_update": {"billing_stage": "payment_link_generated"}, "action": "payment_link_generated"}

    async def _offer_payment_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Offers and facilitates setting up a payment plan.
        """
        balance = self._memory["patient_billing_info"]["outstanding_balance"]
        if balance <= 0:
            return {"response_text": "You currently have no outstanding balance. Thank you!", "context_update": {"billing_stage": "no_balance"}, "action": "no_balance_to_pay"}
        
        response_text = (
            f"Your outstanding balance is ${balance:.2f}. We can arrange a payment plan to split this into manageable installments. "
            "Typically, payment plans are offered for amounts over $200 and can be spread over 3 to 12 months. "
            "Would you like to explore options for a payment plan?"
        )
        self._memory["conversation_stage"] = "main_menu" # Return to main after offering
        return {"response_text": response_text, "context_update": {"billing_stage": "payment_plan_offered"}, "action": "offer_payment_plan"}

    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["patient_billing_info"] = {
            "patient_id": None, "authentication_status": False,
            "outstanding_balance": 0.0, "transactions": []
        }
        self._memory["conversation_stage"] = "authentication"
        self._memory["current_question_index"] = 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock dependencies
    class MockNLUEngine:
        def process_text(self, text, lang):
            return {} 

    nlu_mock = MockNLUEngine()
    
    billing_agent = BillingInquiryAgent(nlu_engine=nlu_mock)

    async def run_billing_flow():
        context = {"call_id": "billing_call_111", "user_id": "patient_bill", "language": "en"}

        print("\n--- Flow 1: Authentication ---")
        response1 = await billing_agent.process_input("I have a question about my bill.", context)
        print(f"Agent: {response1['response_text']}") 
        
        response2 = await billing_agent.process_input("My name is John Smith.", context)
        print(f"Agent: {response2['response_text']}") 
        assert billing_agent.current_memory["patient_billing_info"]["authentication_status"] == True

        print("\n--- Flow 2: Inquire Outstanding Balance ---")
        response3 = await billing_agent.process_input("How much do I owe?", context)
        print(f"Agent: {response3['response_text']}")
        assert "outstanding balance is $75.00" in response3["response_text"]
        
        print("\n--- Flow 3: Itemized Charges ---")
        response4 = await billing_agent.process_input("Can I see an itemized list of charges?", context)
        print(f"Agent: {response4['response_text']}")
        assert "Office visit ($100.00)" in response4["response_text"]
        
        print("\n--- Flow 4: Payment History ---")
        response5 = await billing_agent.process_input("What is my payment history?", context)
        print(f"Agent: {response5['response_text']}")
        assert "Payment of $75.00" in response5["response_text"]

        print("\n--- Flow 5: Make a Payment (Generate Link) ---")
        response6 = await billing_agent.process_input("I want to make a payment.", context)
        print(f"Agent: {response6['response_text']}") 
        
        response7 = await billing_agent.process_input("Send me an online payment link.", context)
        print(f"Agent: {response7['response_text']}")
        assert "Here is a secure link to pay your outstanding balance" in response7["response_text"]

        print("\n--- Flow 6: Offer Payment Plan ---")
        response8 = await billing_agent.process_input("Can I set up a payment plan?", context)
        print(f"Agent: {response8['response_text']}")
        assert "We can arrange a payment plan" in response8["response_text"]

        billing_agent.reset_memory()
        print(f"\nMemory after reset: {billing_agent.current_memory}")

    import asyncio
    asyncio.run(run_billing_flow())