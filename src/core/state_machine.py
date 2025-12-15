# src/core/state_machine.py
"""
A formal state machine for managing complex workflows, powered by the
'transitions' library. This ensures that processes follow a strict,
pre-defined logic, preventing invalid states or skipped steps.
"""
from transitions import Machine

# from . import logger

class VoiceCallStateMachine:
    """
    Manages the state of a real-time voice call.
    This ensures a logical flow from connection to disconnection.
    """
    
    states = [
        'IDLE',         # Waiting for a call
        'LISTENING',    # User is speaking
        'PROCESSING',   # VAD detected silence, processing audio
        'SPEAKING',     # AI is generating and streaming audio
        'WAITING_INPUT' # AI has finished speaking, awaiting user response
    ]

    transitions = [
        {'trigger': 'user_starts_talking', 'source': ['IDLE', 'WAITING_INPUT'], 'dest': 'LISTENING'},
        {'trigger': 'silence_detected', 'source': 'LISTENING', 'dest': 'PROCESSING'},
        {'trigger': 'response_ready', 'source': 'PROCESSING', 'dest': 'SPEAKING'},
        {'trigger': 'speech_finished', 'source': 'SPEAKING', 'dest': 'WAITING_INPUT'},
        {'trigger': 'user_hangs_up', 'source': '*', 'dest': 'IDLE'}
    ]

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.machine = Machine(
            model=self,
            states=VoiceCallStateMachine.states,
            transitions=VoiceCallStateMachine.transitions,
            initial='IDLE',
            after_state_change='log_state_change'
        )

    def log_state_change(self):
        """Callback executed after every state transition."""
        # logger.info(f"Session {self.session_id} state changed to: {self.state}")
        print(f"Session {self.session_id} state changed to: {self.state}")

    # --- Example callbacks for specific states ---
    def on_enter_PROCESSING(self):
        """Callback when entering the PROCESSING state."""
        # This is where you would trigger the STT and LLM processing.
        print("Now processing user's speech...")

    def on_enter_SPEAKING(self, response_audio):
        """Callback when entering the SPEAKING state."""
        # This would trigger the TTS and streaming to the user.
        print("Now speaking response...")


class MedicalWorkflowMachine:
    """
    Manages the state of a high-level medical consultation workflow.
    Prevents logical errors like booking an appointment before triage.
    """
    
    states = ['GREETING', 'TRIAGE_ACTIVE', 'EMERGENCY_PROTOCOL', 'APPOINTMENT_BOOKING', 'CLOSING']

    def __init__(self):
        self.machine = Machine(model=self, states=MedicalWorkflowMachine.states, initial='GREETING')

        self.machine.add_transition('start_triage', 'GREETING', 'TRIAGE_ACTIVE')
        self.machine.add_transition('detect_emergency', '*', 'EMERGENCY_PROTOCOL', conditions=['is_emergency'])
        self.machine.add_transition('start_booking', 'TRIAGE_ACTIVE', 'APPOINTMENT_BOOKING', unless=['is_emergency'])
        self.machine.add_transition('finish_call', '*', 'CLOSING')

    def is_emergency(self, intent: str) -> bool:
        """Guard condition to check if the intent is an emergency."""
        return intent == 'medical_emergency'

# Example Usage:
# call_state = VoiceCallStateMachine(session_id="abc-123")
# print(call_state.state)  # Output: IDLE
# call_state.user_starts_talking()
# print(call_state.state)  # Output: LISTENING
# call_state.silence_detected()
# print(call_state.state)  # Output: PROCESSING
