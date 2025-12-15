# src/intelligence/user_consent_manager.py

from typing import Dict, Any, List
import datetime
import json

# Assuming these imports will be available from other modules
# from src.core.session_manager import SessionManager
# from src.intelligence.audit_logger import AuditLogger
# from src.core.telemetry_emitter import TelemetryEmitter


class UserConsentManager:
    """
    Manages and records user consent for various data collection and processing activities.
    Crucial for compliance with privacy regulations like GDPR, HIPAA, and DPDP.
    """
    def __init__(self, session_manager_instance, audit_logger_instance, telemetry_emitter_instance):
        """
        Initializes the UserConsentManager.
        
        :param session_manager_instance: An initialized SessionManager instance.
        :param audit_logger_instance: An initialized AuditLogger instance.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.session_manager = session_manager_instance
        self.audit_logger = audit_logger_instance
        self.telemetry = telemetry_emitter_instance
        
        # In a real system, this would interact with a database or a persistent store
        # to retrieve and save consent records. For this mock, we use an in-memory dict.
        self._user_consents: Dict[str, Dict[str, Any]] = {} # {user_id: {consent_type: {status: bool, timestamp: datetime}}}
        
        print("✅ UserConsentManager initialized.")

    async def record_consent(self, user_id: str, consent_type: str, status: bool, session_id: str = None):
        """
        Records a user's consent choice for a specific type of data processing.
        
        :param user_id: The ID of the user.
        :param consent_type: The type of consent (e.g., "audio_recording", "data_sharing", "marketing_emails").
        :param status: True if consent is granted, False if denied/withdrawn.
        :param session_id: Optional, the session ID during which consent was recorded.
        """
        if user_id not in self._user_consents:
            self._user_consents[user_id] = {}
        
        self._user_consents[user_id][consent_type] = {
            "status": status,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        print(f"Recorded consent for user {user_id}: {consent_type}={status}")
        self.telemetry.emit_event(
            "consent_recorded",
            {
                "user_id": user_id,
                "session_id": session_id,
                "consent_type": consent_type,
                "status": status
            }
        )
        
        # Log this event for audit trail
        self.audit_logger.log_interaction({
            "event_type": "consent_change",
            "user_id": user_id,
            "session_id": session_id,
            "consent_type": consent_type,
            "new_status": status
        })

    def get_consent_status(self, user_id: str, consent_type: str) -> bool:
        """
        Retrieves the current consent status for a specific user and consent type.
        
        :param user_id: The ID of the user.
        :param consent_type: The type of consent to check.
        :return: True if consent is granted, False otherwise (including if not recorded).
        """
        return self._user_consents.get(user_id, {}).get(consent_type, {}).get("status", False)

    async def present_consent_options_to_user(self, session_id: str, user_id: str, user_interface_callback: callable):
        """
        Simulates presenting consent options to the user at the start of an interaction
        and recording their choices.
        
        :param session_id: The current session ID.
        :param user_id: The ID of the user.
        :param user_interface_callback: A function/method that would present the options
                                        to the actual user and return their choices.
        """
        print(f"Presenting consent options for user {user_id} in session {session_id}...")
        
        # In a real system, this would interact with the frontend/voice UI
        # to get user input for consent.
        
        # Example consent questions
        options = {
            "audio_recording": "Do you consent to audio recording for quality and improvement purposes?",
            "data_sharing": "Do you consent to anonymized data sharing for research?",
            "marketing_emails": "Would you like to receive marketing emails?",
        }
        
        # Mock user response for demonstration
        # In actual deployment, user_interface_callback would prompt the user and get actual input.
        user_choices = await user_interface_callback(options)
        
        for consent_type, status in user_choices.items():
            await self.record_consent(user_id, consent_type, status, session_id)
        
        print(f"Consent options presented and choices recorded for user {user_id}.")

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockSessionManager:
        pass # Not directly used in this example's methods

    class MockAuditLogger:
        def log_interaction(self, data: Dict):
            print(f"Mock Audit Log: {json.dumps(data)}")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_sm = MockSessionManager()
    mock_al = MockAuditLogger()
    mock_te = MockTelemetryEmitter()
    
    manager = UserConsentManager(mock_sm, mock_al, mock_te)

    user1_id = "u_consent_1"
    session1_id = "s_consent_1"

    # --- Test 1: Record initial consents ---
    print("\n--- Test 1: Record initial consents ---")
    async def mock_user_interface_callback(options_dict: Dict) -> Dict[str, bool]:
        print("\n(Simulating user interaction for consent. All true for demo.)")
        # In real life, this would present the options and get user input
        return {key: True for key in options_dict.keys()}

    asyncio.run(manager.present_consent_options_to_user(session1_id, user1_id, mock_user_interface_callback))

    # --- Test 2: Get consent status ---
    print("\n--- Test 2: Get consent status ---")
    print(f"Audio recording consent for {user1_id}: {manager.get_consent_status(user1_id, 'audio_recording')}") # Expected: True
    print(f"Marketing emails consent for {user1_id}: {manager.get_consent_status(user1_id, 'marketing_emails')}") # Expected: True
    print(f"Non-existent consent for {user1_id}: {manager.get_consent_status(user1_id, 'non_existent_type')}") # Expected: False

    # --- Test 3: Change/Withdraw consent ---
    print("\n--- Test 3: Change/Withdraw consent ---")
    asyncio.run(manager.record_consent(user1_id, "marketing_emails", False, session1_id))
    print(f"Marketing emails consent for {user1_id} after withdrawal: {manager.get_consent_status(user1_id, 'marketing_emails')}") # Expected: False

