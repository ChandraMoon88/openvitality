import logging
import json
from typing import Optional, Dict, Any

# Assuming CallSessionManager and CallState are defined elsewhere
from src.voice.telephony.call_session_manager import CallSessionManager, CallState

logger = logging.getLogger(__name__)

class EmergencyCallRouter:
    """
    Handles routing and escalation logic for emergency calls.
    """
    def __init__(self, call_session_manager: CallSessionManager):
        self.call_session_manager = call_session_manager
        # Emergency numbers by country code (example)
        self.emergency_numbers = {
            "US": "911",
            "IN": "108",
            "GB": "999",
            "DEFAULT": "112" # Universal emergency number
        }
        logger.info("EmergencyCallRouter initialized.")

    def detect_emergency_keywords(self, text: str) -> bool:
        """
        Placeholder for emergency keyword detection.
        In a real system, this would be more sophisticated (e.g., using NLP models).
        """
        text_lower = text.lower()
        emergency_triggers = [
            "help", "emergency", "911", "108", "999", "ambulance", "fire", "police",
            "can't breathe", "chest pain", "bleeding", "unconscious", "stroke", "heart attack",
            "choking", "suicide", "kill myself", "shot", "stabbed"
        ]
        if any(trigger in text_lower for trigger in emergency_triggers):
            logger.warning(f"Emergency keyword detected in text: '{text}'")
            return True
        return False

    def escalate_emergency_call(self, call_id: str, country_code: str = "US", caller_location: Dict[str, Any] = None):
        """
        Escalates an emergency call.
        - Bypasses menus
        - Enables silent monitoring/recording
        - Dials emergency services
        - Prepares data packet for dispatcher
        """
        session = self.call_session_manager.get_session(call_id)
        if not session:
            logger.error(f"Cannot escalate emergency call: Session {call_id} not found.")
            return

        logger.critical(f"EMERGENCY PROTOCOL ACTIVATED for Call ID: {call_id}")
        
        # 1. Bypass all menus and logic (handled externally by checking this module)
        # 2. Enable silent monitoring/recording
        session.enable_recording(True) # Ensure recording is on
        session.update_state(CallState.CONNECTED) # Ensure call is connected

        # 3. Determine emergency number
        dial_number = self.emergency_numbers.get(country_code.upper(), self.emergency_numbers["DEFAULT"])
        logger.info(f"Attempting to dial emergency number: {dial_number} for country {country_code}")

        # 4. Prepare data packet for dispatcher
        dispatcher_data = self._prepare_dispatcher_data(session, caller_location, country_code)
        logger.info(f"Prepared dispatcher data for Call ID {call_id}: {json.dumps(dispatcher_data, indent=2)}")

        # 5. Connect to emergency services (conceptual for this file)
        self._dial_emergency_services(session, dial_number, dispatcher_data)

        # 6. Set flag to never hang up (handled by external SIP/WebRTC logic checking session state)
        session.metadata["emergency_active"] = True
        session.metadata["emergency_dialed_number"] = dial_number
        session.metadata["dispatcher_data_sent"] = dispatcher_data
        
        logger.info(f"Emergency escalation complete for Call ID: {call_id}. Waiting for human intervention.")

    def _prepare_dispatcher_data(self, session, caller_location: Dict[str, Any] = None, country_code: str = "US") -> Dict[str, Any]:
        """
        Gathers relevant information for emergency dispatch.
        """
        data = {
            "call_id": session.call_id,
            "caller_id": session.caller_id,
            "start_time": session.start_time,
            "country_code": country_code,
            "detected_language": session.metadata.get("detected_language", "unknown"),
            "current_state": session.metadata.get("current_ai_state", "unknown"),
            "transcripts_excerpt": "Last few seconds of transcript will go here...", # Placeholder
            "potential_symptoms": session.metadata.get("potential_symptoms", []),
            "ai_detected_emergency_reason": "Based on keyword detection and AI assessment...", # Placeholder
            "legal_compliance_info": "Following local emergency regulations."
        }
        if caller_location:
            data["location"] = caller_location
        
        # In a real system, you'd pull more data from the session, user profile, etc.
        return data

    def _dial_emergency_services(self, session, dial_number: str, dispatcher_data: Dict[str, Any]):
        """
        Conceptual method to actually dial emergency services.
        This would integrate with SIP_Trunk_Handler or Twilio_Connector.
        """
        logger.info(f"ACTION: Initiate outbound call to {dial_number} for Call ID {session.call_id}")
        logger.info("ACTION: Keep connection open, feed dispatcher_data if possible (e.g., via DTMF or pre-call)")
        # Example:
        # if session.session_type == "SIP":
        #     self.sip_trunk_handler.make_call(dial_number, pre_recorded_message_with_data)
        # elif session.session_type == "Twilio":
        #     self.twilio_connector.make_outgoing_call(dial_number, twiml_for_emergency_transfer)
        # else:
        #     logger.warning(f"Unsupported session type '{session.session_type}' for dialing emergency services.")


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock CallSessionManager
    mock_call_manager = CallSessionManager()

    router = EmergencyCallRouter(mock_call_manager)

    # Scenario 1: Emergency detected in user input
    user_input_emergency = "I have severe chest pain and can't breathe! Call 911!"
    if router.detect_emergency_keywords(user_input_emergency):
        call_id_1 = str(uuid.uuid4())
        session1 = mock_call_manager.create_session(caller_id="+15551234567", existing_call_id=call_id_1)
        
        caller_location = {"latitude": 34.0522, "longitude": -118.2437, "accuracy": 10, "source": "GPS"}
        router.escalate_emergency_call(call_id_1, country_code="US", caller_location=caller_location)
        
        print(f"\nSession 1 state after escalation: {session1.state.name}")
        print(f"Session 1 emergency active: {session1.metadata.get('emergency_active')}")
        print(f"Session 1 dispatcher data: {json.dumps(session1.metadata.get('dispatcher_data_sent'), indent=2)}")

    print("-" * 30)

    # Scenario 2: No emergency
    user_input_normal = "I have a mild headache."
    if not router.detect_emergency_keywords(user_input_normal):
        print(f"'{user_input_normal}' - No emergency detected. Continue normal AI flow.")
    
    print("-" * 30)

    # Scenario 3: Emergency for a different country
    user_input_india_emergency = "Mujhe bukhar hai aur chest mein dard ho raha hai. Madad chahiye!" # I have fever and chest pain. I need help!
    if router.detect_emergency_keywords(user_input_india_emergency):
        call_id_2 = str(uuid.uuid4())
        session2 = mock_call_manager.create_session(caller_id="+919876543210", existing_call_id=call_id_2)
        router.escalate_emergency_call(call_id_2, country_code="IN")
        print(f"\nSession 2 state after escalation: {session2.state.name}")
        print(f"Session 2 emergency dialed number: {session2.metadata.get('emergency_dialed_number')}")
    
    # Simulate cleanup
    mock_call_manager.end_session(call_id_1)
    mock_call_manager.end_session(call_id_2)
    mock_call_manager.cleanup_inactive_sessions(timeout_seconds=0)
