
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pytest
from unittest.mock import Mock, patch
from transitions import MachineError
from src.core.state_machine import VoiceCallStateMachine, MedicalWorkflowMachine

class TestVoiceCallStateMachine:
    """Tests for the VoiceCallStateMachine."""

    @pytest.fixture
    def call_machine(self):
        """Fixture to provide a new VoiceCallStateMachine for each test."""
        # We can mock the print function to avoid console output during tests
        with patch('builtins.print') as mock_print:
            machine = VoiceCallStateMachine(session_id="test-session-123")
            # We can also mock the logger if it were used
            # machine.logger = Mock()
            yield machine

    def test_initial_state(self, call_machine):
        """Tests that the initial state is IDLE."""
        assert call_machine.state == 'IDLE'

    def test_happy_path_flow(self, call_machine):
        """Tests a typical, successful sequence of state transitions."""
        assert call_machine.state == 'IDLE'
        
        call_machine.user_starts_talking()
        assert call_machine.state == 'LISTENING'
        
        call_machine.silence_detected()
        assert call_machine.state == 'PROCESSING'
        
        # The on_enter_SPEAKING callback expects an argument
        call_machine.response_ready(response_audio="dummy_audio")
        assert call_machine.state == 'SPEAKING'
        
        call_machine.speech_finished()
        assert call_machine.state == 'WAITING_INPUT'
        
        # Test transition back to listening from waiting
        call_machine.user_starts_talking()
        assert call_machine.state == 'LISTENING'

    def test_user_hangs_up_transition(self, call_machine):
        """Tests that user_hangs_up transitions to IDLE from any state."""
        # From LISTENING
        call_machine.user_starts_talking()
        assert call_machine.state == 'LISTENING'
        call_machine.user_hangs_up()
        assert call_machine.state == 'IDLE'
        
        # From WAITING_INPUT
        call_machine.state = 'WAITING_INPUT' # Manually set state for test
        call_machine.user_hangs_up()
        assert call_machine.state == 'IDLE'

    def test_invalid_transition_raises_error(self, call_machine):
        """Tests that an invalid transition raises a MachineError."""
        assert call_machine.state == 'IDLE'
        with pytest.raises(MachineError):
            call_machine.silence_detected()  # Cannot detect silence when idle

    @patch('src.core.state_machine.VoiceCallStateMachine.log_state_change')
    def test_log_state_change_callback(self, mock_log, call_machine):
        """Tests that the log_state_change callback is triggered."""
        call_machine.user_starts_talking()
        mock_log.assert_called_once()
        assert call_machine.state == 'LISTENING'

    @patch('src.core.state_machine.VoiceCallStateMachine.on_enter_PROCESSING')
    def test_on_enter_processing_callback(self, mock_on_enter, call_machine):
        """Tests that a specific on_enter callback is triggered."""
        call_machine.user_starts_talking()
        call_machine.silence_detected()
        mock_on_enter.assert_called_once()
        assert call_machine.state == 'PROCESSING'

class TestMedicalWorkflowMachine:
    """Tests for the MedicalWorkflowMachine."""

    @pytest.fixture
    def medical_machine(self):
        """Fixture to provide a new MedicalWorkflowMachine for each test."""
        return MedicalWorkflowMachine()

    def test_initial_state(self, medical_machine):
        """Tests that the initial state is GREETING."""
        assert medical_machine.state == 'GREETING'

    def test_standard_booking_flow(self, medical_machine):
        """Tests the non-emergency workflow to booking."""
        medical_machine.start_triage()
        assert medical_machine.state == 'TRIAGE_ACTIVE'
        
        # is_emergency should be false by default
        medical_machine.start_booking(intent='appointment_booking')
        assert medical_machine.state == 'APPOINTMENT_BOOKING'

    def test_emergency_detection_flow(self, medical_machine):
        """Tests that an emergency intent correctly transitions to the emergency protocol."""
        medical_machine.start_triage()
        assert medical_machine.state == 'TRIAGE_ACTIVE'
        
        # The 'detect_emergency' trigger uses the 'is_emergency' condition
        medical_machine.detect_emergency(intent='medical_emergency')
        assert medical_machine.state == 'EMERGENCY_PROTOCOL'

    def test_booking_is_blocked_during_emergency(self, medical_machine):
        """Tests the 'unless' guard on the start_booking transition."""
        medical_machine.start_triage()
        assert medical_machine.state == 'TRIAGE_ACTIVE'
        
        # This should fail because the 'unless' condition is met
        with pytest.raises(MachineError):
            medical_machine.start_booking(intent='medical_emergency')
            
        # The state should not have changed
        assert medical_machine.state == 'TRIAGE_ACTIVE'

    def test_finish_call_transition(self, medical_machine):
        """Tests that the finish_call trigger works from various states."""
        # From TRIAGE_ACTIVE
        medical_machine.start_triage()
        medical_machine.finish_call()
        assert medical_machine.state == 'CLOSING'
        
        # Reset and test from APPOINTMENT_BOOKING
        medical_machine.state = 'GREETING'
        medical_machine.start_triage()
        medical_machine.start_booking(intent='booking')
        medical_machine.finish_call()
        assert medical_machine.state == 'CLOSING'
