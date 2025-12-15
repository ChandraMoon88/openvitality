# src/telephony/call_recording_manager.py

from typing import Dict, Any
import os
import datetime
import asyncio
import json

# Assuming these imports will be available from other modules
# from src.intelligence.user_consent_manager import UserConsentManager
# from src.intelligence.data_retention_manager import DataRetentionManager
# from src.intelligence.audit_logger import AuditLogger
# from src.core.telemetry_emitter import TelemetryEmitter


class CallRecordingManager:
    """
    Manages the recording of call audio, including starting, stopping,
    secure storage, and integration with consent and data retention policies.
    """
    def __init__(self, user_consent_manager_instance, data_retention_manager_instance, audit_logger_instance, telemetry_emitter_instance, config: Dict[str, Any]):
        """
        Initializes the CallRecordingManager.
        
        :param user_consent_manager_instance: An initialized UserConsentManager instance.
        :param data_retention_manager_instance: An initialized DataRetentionManager instance.
        :param audit_logger_instance: An initialized AuditLogger instance.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        :param config: Application configuration, including recording storage paths.
        """
        self.user_consent_manager = user_consent_manager_instance
        self.data_retention_manager = data_retention_manager_instance
        self.audit_logger = audit_logger_instance
        self.telemetry = telemetry_emitter_instance
        self.config = config
        
        self.recording_base_dir = config.get("recording_base_dir", "data/call_recordings")
        os.makedirs(self.recording_base_dir, exist_ok=True)
        
        # Stores active recordings: {session_id: {"recording_path": str, "start_time": datetime, "file_handle": Any, ...}}
        self.active_recordings: Dict[str, Dict[str, Any]] = {}
        
        print("✅ CallRecordingManager initialized.")

    async def start_recording(self, session_id: str, user_id: str, format: str = "wav", encrypt: bool = True, force: bool = False) -> str | None:
        """
        Starts recording audio for a given session.
        
        :param session_id: The ID of the call session.
        :param user_id: The ID of the user associated with the session.
        :param format: The audio format for recording (e.g., "wav", "mp3").
        :param encrypt: If True, the recording will be encrypted.
        :param force: If True, bypasses consent check (e.g., for emergency calls or legal requirement).
        :return: The path to the recording file if started, None otherwise.
        """
        if session_id in self.active_recordings:
            print(f"Recording already active for session {session_id}.")
            return self.active_recordings[session_id]["recording_path"]

        # Check user consent unless forced
        if not force and not self.user_consent_manager.get_consent_status(user_id, "audio_recording"):
            print(f"Recording denied for session {session_id}: User consent not granted.")
            self.telemetry.emit_event("call_recording_failed", {"session_id": session_id, "user_id": user_id, "reason": "no_consent"})
            return None
        
        # Generate a unique filename and path
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{timestamp}.{format}"
        recording_path = os.path.join(self.recording_base_dir, filename)
        
        # Simulate opening a file handle and starting to write audio
        # In a real system, audio frames would be fed directly to this manager.
        file_handle = open(recording_path, "wb") # Open in binary write mode
        
        self.active_recordings[session_id] = {
            "recording_path": recording_path,
            "start_time": datetime.datetime.now(),
            "format": format,
            "encrypted": encrypt,
            "file_handle": file_handle,
            "force_recorded": force
        }
        
        self.audit_logger.log_interaction({
            "event_type": "recording_started",
            "session_id": session_id,
            "user_id": user_id,
            "recording_path": recording_path,
            "encrypted": encrypt,
            "forced": force
        })
        self.telemetry.emit_event("call_recording_started", {"session_id": session_id, "user_id": user_id, "recording_path": recording_path})
        print(f"✅ Started recording for session {session_id} to {recording_path}.")
        return recording_path

    async def stop_recording(self, session_id: str):
        """
        Stops recording audio for a given session and finalizes the recording file.
        
        :param session_id: The ID of the call session.
        """
        recording_info = self.active_recordings.pop(session_id, None)
        if recording_info:
            # Simulate closing the file handle and finalizing encryption
            file_handle = recording_info["file_handle"]
            file_handle.close()
            
            if recording_info["encrypted"]:
                print(f"Simulating encryption of {recording_info['recording_path']}")
                # A real system would encrypt the file here.
                pass

            duration = (datetime.datetime.now() - recording_info["start_time"]).total_seconds()
            
            self.audit_logger.log_interaction({
                "event_type": "recording_stopped",
                "session_id": session_id,
                "recording_path": recording_info["recording_path"],
                "duration_seconds": duration
            })
            self.telemetry.emit_event("call_recording_stopped", {"session_id": session_id, "recording_path": recording_info["recording_path"], "duration": duration})
            print(f"🛑 Stopped recording for session {session_id}. Duration: {duration:.2f}s.")
            
            # Trigger data retention policy for this recording
            await self.data_retention_manager.apply_retention_policy_for_session(session_id, user_id="mock_user_id_for_session") # Pass actual user_id
        else:
            print(f"No active recording found for session {session_id}.")

    async def write_audio_frame(self, session_id: str, audio_frame_bytes: bytes):
        """
        Writes an audio frame to the active recording for a session.
        This would be called repeatedly by the audio pipeline.
        
        :param session_id: The ID of the call session.
        :param audio_frame_bytes: Raw audio data frame as bytes.
        """
        recording_info = self.active_recordings.get(session_id)
        if recording_info:
            file_handle = recording_info["file_handle"]
            try:
                # In a real WAV file, you'd write header first, then data.
                # Here, we just append raw bytes for simplicity of mock.
                file_handle.write(audio_frame_bytes)
            except Exception as e:
                print(f"Error writing audio frame to {session_id}: {e}")
                self.telemetry.emit_event("call_recording_write_error", {"session_id": session_id, "error": str(e)})

    def get_recording_path(self, session_id: str) -> str | None:
        """
        Retrieves the path to the recording file for a given session.
        """
        info = self.active_recordings.get(session_id)
        if info:
            return info["recording_path"]
        return None

    async def get_recording_for_audit(self, session_id: str, auditor_id: str) -> bytes | None:
        """
        Retrieves a recording for auditing purposes, subject to access controls.
        
        :param session_id: The ID of the call session.
        :param auditor_id: The ID of the auditor requesting access.
        :return: The decrypted recording bytes, or None if access denied.
        """
        # This is highly simplified access control.
        # A real system would have roles, permissions, and a secure key management system.
        if auditor_id not in ["admin_auditor", "legal_auditor"]:
            print(f"Access denied for auditor {auditor_id} to recording for session {session_id}.")
            self.telemetry.emit_event("recording_access_denied", {"session_id": session_id, "auditor_id": auditor_id})
            return None
        
        recording_path = self.get_recording_path(session_id)
        if not recording_path or not os.path.exists(recording_path):
            print(f"Recording for session {session_id} not found.")
            return None
        
        # Simulate decryption and retrieval
        with open(recording_path, "rb") as f:
            encrypted_data = f.read()
        
        # Decryption logic would go here.
        decrypted_data = encrypted_data # For mock, no actual decryption
        
        self.audit_logger.log_interaction({
            "event_type": "recording_accessed_for_audit",
            "session_id": session_id,
            "auditor_id": auditor_id
        })
        self.telemetry.emit_event("recording_accessed_for_audit", {"session_id": session_id, "auditor_id": auditor_id})
        print(f"✅ Recording for session {session_id} accessed by {auditor_id}.")
        return decrypted_data


# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockUserConsentManager:
        def get_consent_status(self, user_id: str, consent_type: str) -> bool:
            if user_id == "user_with_consent" and consent_type == "audio_recording":
                return True
            if user_id == "user_emergency" and consent_type == "audio_recording":
                return False # Consent not given, but force=True will override
            return False

    class MockDataRetentionManager:
        async def apply_retention_policy_for_session(self, session_id: str, user_id: str = None):
            print(f"Mock DRM: Applying retention policy for {session_id}.")

    class MockAuditLogger:
        def log_interaction(self, data: Dict):
            print(f"Mock Audit Log: {json.dumps(data)}")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # Ensure data/call_recordings directory exists for mock file writes
    os.makedirs("data/call_recordings", exist_ok=True)

    # --- Initialize ---
    mock_ucm = MockUserConsentManager()
    mock_drm = MockDataRetentionManager()
    mock_al = MockAuditLogger()
    mock_te = MockTelemetryEmitter()
    mock_config = {"recording_base_dir": "data/call_recordings"}
    
    recorder = CallRecordingManager(mock_ucm, mock_drm, mock_al, mock_te, mock_config)

    # --- Test 1: Start recording with consent ---
    print("\n--- Test 1: Start recording with consent ---")
    session_id_1 = "s_rec_1"
    user_id_1 = "user_with_consent"
    rec_path_1 = asyncio.run(recorder.start_recording(session_id_1, user_id_1))
    print(f"Recording Path 1: {rec_path_1}")
    
    # Simulate writing some audio
    asyncio.run(recorder.write_audio_frame(session_id_1, b"some audio data 1"))
    asyncio.run(recorder.write_audio_frame(session_id_1, b"more audio data 1"))

    # --- Test 2: Start recording without consent (should fail) ---
    print("\n--- Test 2: Start recording without consent ---")
    session_id_2 = "s_rec_2"
    user_id_2 = "user_no_consent"
    rec_path_2 = asyncio.run(recorder.start_recording(session_id_2, user_id_2))
    print(f"Recording Path 2: {rec_path_2}") # Expected: None

    # --- Test 3: Start recording forced (e.g., emergency call) ---
    print("\n--- Test 3: Start recording forced (emergency) ---")
    session_id_3 = "s_rec_3_emergency"
    user_id_3 = "user_emergency"
    rec_path_3 = asyncio.run(recorder.start_recording(session_id_3, user_id_3, force=True))
    print(f"Recording Path 3: {rec_path_3}") # Expected: a path

    # --- Simulate writing some audio to forced recording ---
    asyncio.run(recorder.write_audio_frame(session_id_3, b"emergency audio"))

    # --- Test 4: Stop recording session 1 ---
    print("\n--- Test 4: Stop recording session 1 ---")
    asyncio.run(recorder.stop_recording(session_id_1))

    # --- Test 5: Access recording for audit ---
    print("\n--- Test 5: Access recording for audit ---")
    audit_data = asyncio.run(recorder.get_recording_for_audit(session_id_1, "admin_auditor"))
    print(f"Audit Data for session 1 length: {len(audit_data) if audit_data else 'None'}")

    # --- Test 6: Attempt unauthorized access ---
    print("\n--- Test 6: Attempt unauthorized access ---")
    unauth_data = asyncio.run(recorder.get_recording_for_audit(session_id_3, "unauthorized_user"))
    print(f"Unauthorized Access Data: {unauth_data}") # Expected: None

    # Clean up mock recording files
    for key, info in list(recorder.active_recordings.items()): # Need to iterate over a copy as dict changes
        if info["file_handle"]:
            info["file_handle"].close() # Ensure all files are closed
        if os.path.exists(info["recording_path"]):
            os.remove(info["recording_path"])
    
    if rec_path_1 and os.path.exists(rec_path_1): os.remove(rec_path_1)
    if rec_path_3 and os.path.exists(rec_path_3): os.remove(rec_path_3)
    if os.path.exists("data/call_recordings"): os.rmdir("data/call_recordings") # Remove dir if empty
