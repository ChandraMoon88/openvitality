# src/core/dialogue_manager.py
"""
Controls the flow and structure of the conversation.

This manager uses a state machine to guide the user through a logical sequence
of steps, from greeting to closing. It handles tasks like filling required
information (slots), clarifying ambiguities, and repairing the conversation
when the user or AI gets confused.
"""
from typing import Dict, Any, List

# from .state_machine import DialogueStateMachine
# from . import logger

class DialogueManager:
    def __init__(self, state_machine_definition: Dict):
        """
        Initializes the DialogueManager with a state machine.
        """
        # self.sm = DialogueStateMachine(definition=state_machine_definition)
        # logger.info("DialogueManager initialized.")
        print("DialogueManager initialized.")

    def get_next_action(self, session: Dict, user_input: str) -> Dict:
        """
        Determines the next action for the AI based on the current state and user input.
        
        Returns:
            A dictionary specifying the action (e.g., 'ask_question', 'confirm_info').
        """
        current_state = session['context'].get('dialogue_state', 'GREETING')
        # self.sm.set_state(current_state)

        # Example logic for a simple triage workflow
        if current_state == 'GREETING':
            # self.sm.transition('start_triage')
            return {"action": "ask", "question": "Hello! How can I help you today?"}

        elif current_state == 'TRIAGE':
            # This is where slot filling happens
            required_slots = ["symptom", "duration", "severity"]
            filled_slots = session['context'].get('slot_filling', {})
            
            missing_slots = [slot for slot in required_slots if slot not in filled_slots]

            if not missing_slots:
                # All slots are filled, time to confirm
                # self.sm.transition('confirm_details')
                confirmation_text = f"Just to be sure: you have a {filled_slots['symptom']} of {filled_slots['severity']} severity for {filled_slots['duration']}. Is that correct?"
                return {"action": "confirm", "text": confirmation_text}
            else:
                # Ask for the next missing piece of information
                next_slot_to_ask = missing_slots[0]
                return {"action": "ask_slot", "slot": next_slot_to_ask}

        elif current_state == 'CONFIRMATION':
            if "yes" in user_input.lower():
                # self.sm.transition('provide_recommendation')
                return {"action": "generate_response", "context": session['context']['slot_filling']}
            else:
                # Conversation repair
                # self.sm.transition('restart_triage')
                session['context']['slot_filling'] = {} # Clear slots
                return {"action": "ask", "question": "I'm sorry I got that wrong. Let's try again. What seems to be the problem?"}
        
        else:
            return {"action": "fallback", "text": "I'm not sure how to help with that. Can you rephrase?"}

    def handle_interruption(self):
        """
        Handles cases where the user speaks while the AI is speaking.
        """
        # Logic to stop the AI's current speech and listen to the user.
        # logger.info("User interruption detected. Clearing AI speech queue.")
        print("Handling user interruption.")
        pass

# Example State Machine Definition
DIALOGUE_FLOW = {
    'states': ['GREETING', 'TRIAGE', 'CONFIRMATION', 'TREATMENT', 'CLOSING'],
    'transitions': [
        {'trigger': 'start_triage', 'source': 'GREETING', 'dest': 'TRIAGE'},
        {'trigger': 'confirm_details', 'source': 'TRIAGE', 'dest': 'CONFIRMATION'},
        {'trigger': 'provide_recommendation', 'source': 'CONFIRMATION', 'dest': 'TREATMENT'},
        {'trigger': 'restart_triage', 'source': 'CONFIRMATION', 'dest': 'TRIAGE'},
        {'trigger': 'end_conversation', 'source': '*', 'dest': 'CLOSING'}
    ]
}
