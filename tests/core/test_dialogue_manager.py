import sys
import os
import unittest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.dialogue_manager import DialogueManager

class TestDialogueManager(unittest.TestCase):

    def setUp(self):
        """
        Initialize the DialogueManager for each test.
        The state machine definition is not used by the current implementation,
        but we pass it for completeness.
        """
        dummy_state_machine_def = {
            'states': ['GREETING', 'TRIAGE', 'CONFIRMATION'],
            'transitions': []
        }
        self.dialogue_manager = DialogueManager(dummy_state_machine_def)

    def test_greeting_state(self):
        """Test the initial GREETING state action."""
        session = {"context": {"dialogue_state": "GREETING"}}
        user_input = "Hello"
        
        action = self.dialogue_manager.get_next_action(session, user_input)
        
        self.assertEqual(action["action"], "ask")
        self.assertEqual(action["question"], "Hello! How can I help you today?")

    def test_triage_state_no_slots_filled(self):
        """Test TRIAGE state when no information has been provided yet."""
        session = {"context": {"dialogue_state": "TRIAGE", "slot_filling": {}}}
        user_input = "I have a headache" # This input is not used by the current logic
        
        action = self.dialogue_manager.get_next_action(session, user_input)
        
        self.assertEqual(action["action"], "ask_slot")
        self.assertEqual(action["slot"], "symptom")

    def test_triage_state_some_slots_filled(self):
        """Test TRIAGE state when some slots are already filled."""
        session = {
            "context": {
                "dialogue_state": "TRIAGE",
                "slot_filling": {"symptom": "headache", "severity": "mild"}
            }
        }
        user_input = "It's been two days"
        
        action = self.dialogue_manager.get_next_action(session, user_input)
        
        self.assertEqual(action["action"], "ask_slot")
        self.assertEqual(action["slot"], "duration")

    def test_triage_state_all_slots_filled(self):
        """Test TRIAGE state when all slots are filled, moving to confirmation."""
        session = {
            "context": {
                "dialogue_state": "TRIAGE",
                "slot_filling": {
                    "symptom": "fever",
                    "duration": "3 days",
                    "severity": "high"
                }
            }
        }
        user_input = "That's everything"
        
        action = self.dialogue_manager.get_next_action(session, user_input)
        
        self.assertEqual(action["action"], "confirm")
        expected_text = "Just to be sure: you have a fever of high severity for 3 days. Is that correct?"
        self.assertEqual(action["text"], expected_text)

    def test_confirmation_state_user_confirms(self):
        """Test CONFIRMATION state when the user agrees."""
        session = {
            "context": {
                "dialogue_state": "CONFIRMATION",
                "slot_filling": {"symptom": "cough", "duration": "a week", "severity": "moderate"}
            }
        }
        user_input = "Yes, that is correct."
        
        action = self.dialogue_manager.get_next_action(session, user_input)
        
        self.assertEqual(action["action"], "generate_response")
        self.assertEqual(action["context"], session["context"]["slot_filling"])

    def test_confirmation_state_user_denies(self):
        """Test CONFIRMATION state when the user denies, triggering conversation repair."""
        session = {
            "context": {
                "dialogue_state": "CONFIRMATION",
                "slot_filling": {"symptom": "cough", "duration": "a week", "severity": "moderate"}
            }
        }
        user_input = "No, that's wrong."
        
        action = self.dialogue_manager.get_next_action(session, user_input)
        
        self.assertEqual(action["action"], "ask")
        self.assertEqual(action["question"], "I'm sorry I got that wrong. Let's try again. What seems to be the problem?")
        # Check that the slots have been cleared for the retry
        self.assertEqual(session["context"]["slot_filling"], {})

    def test_unknown_state_fallback(self):
        """Test the fallback action for an unknown dialogue state."""
        session = {"context": {"dialogue_state": "UNKNOWN_STATE"}}
        user_input = "Some random input"
        
        action = self.dialogue_manager.get_next_action(session, user_input)
        
        self.assertEqual(action["action"], "fallback")
        self.assertEqual(action["text"], "I'm not sure how to help with that. Can you rephrase?")


if __name__ == '__main__':
    unittest.main()
