import sys
sys.path.append('.')

import unittest
import asyncio
import os
import shutil
from typing import Dict, Any

from src.telephony.call_recording_manager import CallRecordingManager

# --- Mock Dependencies ---
class MockUserConsentManager:
    def get_consent_status(self, user_id: str, consent_type: str) -> bool:
        if user_id == "user_with_consent" and consent_type == "audio_recording":
            return True
        return False

class MockDataRetentionManager:
    async def apply_retention_policy_for_session(self, session_id: str, user_id: str = None):
        pass # No action needed for mock

class MockAuditLogger:
    def __init__(self):
        self.logs = []
    def log_interaction(self, data: Dict):
        self.logs.append(data)

class MockTelemetryEmitter:
    def __init__(self):
        self.events = []
    def emit_event(self, event_name: str, data: Dict):
        self.events.append({"name": event_name, "data": data})

class TestCallRecordingManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.test_dir = "temp_test_recordings"
        os.makedirs(self.test_dir, exist_ok=True)
        
        self.mock_ucm = MockUserConsentManager()
        self.mock_drm = MockDataRetentionManager()
        self.mock_al = MockAuditLogger()
        self.mock_te = MockTelemetryEmitter()
        mock_config = {"recording_base_dir": self.test_dir}
        
        self.recorder = CallRecordingManager(self.mock_ucm, self.mock_drm, self.mock_al, self.mock_te, mock_config)

    def tearDown(self):
        # Clean up all active recordings before deleting the directory
        for session_id in list(self.recorder.active_recordings.keys()):
            recording_info = self.recorder.active_recordings.pop(session_id, None)
            if recording_info and recording_info.get("file_handle"):
                recording_info["file_handle"].close()
        
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    async def test_start_recording_with_consent(self):
        session_id = "s1"
        user_id = "user_with_consent"
        path = await self.recorder.start_recording(session_id, user_id)
        
        self.assertIsNotNone(path)
        self.assertIn(session_id, self.recorder.active_recordings)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(len(self.mock_al.logs), 1)
        self.assertEqual(self.mock_al.logs[0]['event_type'], 'recording_started')

    async def test_start_recording_without_consent(self):
        session_id = "s2"
        user_id = "user_no_consent"
        path = await self.recorder.start_recording(session_id, user_id)
        
        self.assertIsNone(path)
        self.assertNotIn(session_id, self.recorder.active_recordings)
        self.assertEqual(len(self.mock_te.events), 1)
        self.assertEqual(self.mock_te.events[0]['name'], 'call_recording_failed')

    async def test_start_recording_forced(self):
        session_id = "s3"
        user_id = "user_no_consent"
        path = await self.recorder.start_recording(session_id, user_id, force=True)
        
        self.assertIsNotNone(path)
        self.assertIn(session_id, self.recorder.active_recordings)
        self.assertTrue(self.recorder.active_recordings[session_id]['force_recorded'])

    async def test_write_audio_and_stop_recording(self):
        session_id = "s4"
        user_id = "user_with_consent"
        path = await self.recorder.start_recording(session_id, user_id)
        
        audio_data = b"test audio data"
        await self.recorder.write_audio_frame(session_id, audio_data)
        
        await self.recorder.stop_recording(session_id)
        
        self.assertNotIn(session_id, self.recorder.active_recordings)
        
        with open(path, "rb") as f:
            content = f.read()
            self.assertEqual(content, audio_data)

    async def test_get_recording_for_audit(self):
        session_id = "s5"
        user_id = "user_with_consent"
        path = await self.recorder.start_recording(session_id, user_id)
        audio_data = b"audit this"
        await self.recorder.write_audio_frame(session_id, audio_data)
        # We need to stop it to be able to re-open it on windows.
        await self.recorder.stop_recording(session_id)
        
        # Add it back to active recordings for the test's logic, but file is closed.
        # This is a bit of a hack. In a real scenario, we'd probably query a DB.
        self.recorder.active_recordings[session_id] = {'recording_path': path}

        # Authorized access
        retrieved_data = await self.recorder.get_recording_for_audit(session_id, "admin_auditor")
        self.assertEqual(retrieved_data, audio_data)
        
        # Unauthorized access
        unauthorized_data = await self.recorder.get_recording_for_audit(session_id, "bad_actor")
        self.assertIsNone(unauthorized_data)
        
        # Check telemetry for denied access
        self.assertTrue(any(e['name'] == 'recording_access_denied' for e in self.mock_te.events))


if __name__ == "__main__":
    unittest.main()