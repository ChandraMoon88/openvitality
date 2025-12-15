# src/intelligence/data_retention_manager.py

import datetime
import asyncio
from typing import Dict, Any, List

# Assuming these imports will be available from other modules
# from src.core.memory_manager import MemoryManager
# from src.intelligence.audit_logger import AuditLogger
# from src.core.telemetry_emitter import TelemetryEmitter


class DataRetentionManager:
    """
    Implements and enforces data retention and deletion policies based on
    compliance rules (e.g., GDPR, HIPAA, DPDP).
    """
    def __init__(self, memory_manager_instance, audit_logger_instance, telemetry_emitter_instance, config: Dict[str, Any]):
        """
        Initializes the DataRetentionManager.
        
        :param memory_manager_instance: An initialized MemoryManager instance.
        :param audit_logger_instance: An initialized AuditLogger instance.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        :param config: The application configuration, containing retention policies.
        """
        self.memory_manager = memory_manager_instance
        self.audit_logger = audit_logger_instance
        self.telemetry = telemetry_emitter_instance
        self.config = config
        
        # Load retention policies from config
        self.retention_policies = config.get("data_retention", {
            "audio_data_days": 7,       # Delete raw audio after 7 days
            "short_term_text_days": 30, # Delete detailed conversation text after 30 days
            "summary_text_years": 10,   # Keep anonymized summaries for 10 years
            "audit_logs_years": 10      # Keep audit logs for 10 years
        })
        print("✅ DataRetentionManager initialized with policies:", self.retention_policies)

    async def apply_retention_policy_for_session(self, session_id: str, user_id: str = None):
        """
        Applies the configured data retention policies to a specific session.
        This would typically be called after a session has ended and been processed.
        
        :param session_id: The ID of the session to clean up.
        :param user_id: The ID of the user associated with the session (for user-level data).
        """
        print(f"Applying retention policy for session: {session_id}")

        now = datetime.datetime.now()

        # 1. Audio Data
        audio_retention_days = self.retention_policies.get("audio_data_days", 7)
        if audio_retention_days >= 0: # -1 could mean "never delete"
            await self.memory_manager.delete_session_audio_data(session_id, retention_days=audio_retention_days)
            self.telemetry.emit_event("data_retention_action", {"session_id": session_id, "data_type": "audio", "action": "deleted_if_expired"})

        # 2. Detailed Conversation Text (from session history)
        short_term_text_days = self.retention_policies.get("short_term_text_days", 30)
        if short_term_text_days >= 0:
            await self.memory_manager.delete_session_detailed_text(session_id, retention_days=short_term_text_days)
            self.telemetry.emit_event("data_retention_action", {"session_id": session_id, "data_type": "detailed_text", "action": "deleted_if_expired"})

        # 3. Anonymized Summaries (handled by memory_manager during creation/update)
        # The memory_manager is responsible for creating long-term summaries and
        # ensuring they are anonymized and stored with appropriate metadata for their longer retention.
        # This function primarily triggers deletion of short-term data.

        # 4. Audit Logs (managed by AuditLogger, but we might trigger its cleanup here)
        audit_logs_years = self.retention_policies.get("audit_logs_years", 10)
        if audit_logs_years >= 0:
            # AuditLogger handles its own cleanup, typically on a scheduled basis.
            # We can notify it to potentially check this session's logs.
            await self.audit_logger.trigger_log_cleanup(session_id, retention_years=audit_logs_years)
            self.telemetry.emit_event("data_retention_action", {"session_id": session_id, "data_type": "audit_logs", "action": "checked_for_deletion"})

        print(f"Retention policy applied for session {session_id}.")

    async def scheduled_cleanup_task(self):
        """
        A periodic task that runs to clean up expired data across all sessions.
        This would be run by src/core/task_scheduler.py.
        """
        print("Running scheduled data cleanup task...")
        now = datetime.datetime.now()

        # Get a list of all users or sessions that might have expired data
        # This requires `memory_manager` to provide an iterator or list of all active/recent sessions.
        all_user_ids = await self.memory_manager.get_all_user_ids() # Mock call
        
        for user_id in all_user_ids:
            # Retrieve all sessions for this user (or just expired ones)
            # This is a conceptual loop. Actual implementation depends on DB structure.
            sessions_to_check = await self.memory_manager.get_sessions_for_user(user_id) # Mock call
            for session in sessions_to_check:
                # Assuming session has a 'last_active' timestamp
                if (now - session.last_active).days > self.retention_policies.get("short_term_text_days", 30):
                    await self.apply_retention_policy_for_session(session.session_id, user_id)

        # Trigger AuditLogger's general cleanup
        await self.audit_logger.trigger_general_log_cleanup(retention_years=self.retention_policies.get("audit_logs_years", 10))
        
        print("Scheduled data cleanup task completed.")

    async def enforce_right_to_be_forgotten(self, user_id: str):
        """
        Permanently deletes all data associated with a specific user.
        This is a critical function for GDPR/DPDP compliance.
        
        :param user_id: The ID of the user whose data should be deleted.
        """
        print(f"Enforcing 'Right to be Forgotten' for user: {user_id}")
        
        # 1. Delete all audio data for the user
        await self.memory_manager.delete_all_audio_for_user(user_id)
        self.telemetry.emit_event("r2bf_action", {"user_id": user_id, "data_type": "audio", "action": "deleted"})

        # 2. Delete all detailed conversation text for the user
        await self.memory_manager.delete_all_detailed_text_for_user(user_id)
        self.telemetry.emit_event("r2bf_action", {"user_id": user_id, "data_type": "detailed_text", "action": "deleted"})

        # 3. Anonymize/delete all long-term summaries for the user
        await self.memory_manager.delete_all_summaries_for_user(user_id) # Or anonymize further
        self.telemetry.emit_event("r2bf_action", {"user_id": user_id, "data_type": "summaries", "action": "deleted"})

        # 4. Remove user-specific entries from audit logs (if PII is present in them)
        await self.audit_logger.delete_user_audit_entries(user_id)
        self.telemetry.emit_event("r2bf_action", {"user_id": user_id, "data_type": "audit_logs", "action": "deleted"})

        # 5. Remove any user-specific configuration or metadata
        # (This would be handled by a user management module)
        
        self.telemetry.emit_event("r2bf_complete", {"user_id": user_id})
        print(f"All data for user {user_id} has been processed for deletion.")

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockMemoryManager:
        async def delete_session_audio_data(self, session_id: str, retention_days: int):
            print(f"Mock MM: Deleting audio for session {session_id} older than {retention_days} days.")
        async def delete_session_detailed_text(self, session_id: str, retention_days: int):
            print(f"Mock MM: Deleting detailed text for session {session_id} older than {retention_days} days.")
        async def delete_all_audio_for_user(self, user_id: str):
            print(f"Mock MM: Deleting all audio for user {user_id}.")
        async def delete_all_detailed_text_for_user(self, user_id: str):
            print(f"Mock MM: Deleting all detailed text for user {user_id}.")
        async def delete_all_summaries_for_user(self, user_id: str):
            print(f"Mock MM: Deleting all summaries for user {user_id}.")
        async def get_all_user_ids(self):
            return ["user1", "user2"]
        async def get_sessions_for_user(self, user_id):
            class MockSession:
                def __init__(self, session_id, last_active):
                    self.session_id = session_id
                    self.last_active = last_active
            if user_id == "user1":
                return [MockSession("s1_old", datetime.datetime.now() - datetime.timedelta(days=40))]
            return []

    class MockAuditLogger:
        async def trigger_log_cleanup(self, session_id: str, retention_years: int):
            print(f"Mock AL: Triggering log cleanup for session {session_id} older than {retention_years} years.")
        async def trigger_general_log_cleanup(self, retention_years: int):
            print(f"Mock AL: Triggering general log cleanup older than {retention_years} years.")
        async def delete_user_audit_entries(self, user_id: str):
            print(f"Mock AL: Deleting audit entries for user {user_id}.")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_mm = MockMemoryManager()
    mock_al = MockAuditLogger()
    mock_te = MockTelemetryEmitter()
    mock_config = {
        "data_retention": {
            "audio_data_days": 7,
            "short_term_text_days": 30,
            "summary_text_years": 10,
            "audit_logs_years": 10
        }
    }
    
    manager = DataRetentionManager(mock_mm, mock_al, mock_te, mock_config)

    # --- Test 1: Apply policy for a single session ---
    print("\n--- Test 1: Apply policy for a single session ---")
    asyncio.run(manager.apply_retention_policy_for_session("session_abc_123", "user1"))

    # --- Test 2: Run scheduled cleanup task ---
    print("\n--- Test 2: Run scheduled cleanup task ---")
    asyncio.run(manager.scheduled_cleanup_task())

    # --- Test 3: Enforce Right to be Forgotten ---
    print("\n--- Test 3: Enforce Right to be Forgotten ---")
    asyncio.run(manager.enforce_right_to_be_forgotten("user_to_forget_456"))
