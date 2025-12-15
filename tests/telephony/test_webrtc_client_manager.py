import sys
sys.path.append('.')

import unittest
import asyncio
import uuid
from typing import Dict, Any, Callable

from src.telephony.webrtc_client_manager import WebRTCClientManager

# --- Mock Dependencies ---
class MockSipAudioBridge:
    def __init__(self, *args): self.stopped = False
    def stop_bridge(self): self.stopped = True
    def on_tts_audio_received(self, audio_data): pass

class MockCallSession:
    def __init__(self, session_id, **kwargs):
        self.session_id = session_id
        self.ended = False
        self.end_reason = None
    def end(self, reason):
        self.ended = True
        self.end_reason = reason

class MockCallSessionManager:
    def __init__(self):
        self.sessions = {}
    def create_session(self, call_id, *args):
        session_id = f"session_{call_id}"
        new_session = MockCallSession(session_id)
        self.sessions[session_id] = new_session
        return new_session
    def get_session_by_uuid(self, session_id):
        return self.sessions.get(session_id)

class MockCallEventManager:
    async def publish(self, *args, **kwargs):
        pass

class MockTelemetryEmitter:
    def __init__(self):
        self.events = []
    def emit_event(self, event_name, data):
        self.events.append({'name': event_name, 'data': data})

class TestWebRTCClientManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_cem = MockCallEventManager()
        self.mock_csm = MockCallSessionManager()
        self.mock_te = MockTelemetryEmitter()
        
        # The source file has mock classes defined at the module level.
        # We need to inject them into the WebRTCClientManager's namespace for it to find them.
        # This is a workaround for the way the source file is structured.
        import src.telephony.webrtc_client_manager as webrtc_module
        webrtc_module.MockSipAudioBridge = MockSipAudioBridge
        webrtc_module.MockSTTEngine = type('MockSTTEngine', (), {})
        webrtc_module.MockTTSEngine = type('MockTTSEngine', (), {})
        webrtc_module.MockVADEngine = type('MockVADEngine', (), {})

        self.manager = WebRTCClientManager({}, self.mock_cem, self.mock_csm, self.mock_te)

    async def test_start_and_stop_server(self):
        # Prevent the mock loop from actually running
        self.manager._mock_webrtc_signaling_loop = unittest.mock.AsyncMock()
        
        await self.manager.start_webrtc_server()
        self.assertIsNotNone(self.manager.webrtc_server_task)
        
        await self.manager.stop_webrtc_server()
        self.assertIsNone(self.manager.webrtc_server_task)
        self.assertTrue(self.manager._mock_webrtc_signaling_loop.is_awaited)

    async def test_handle_new_connection(self):
        conn_id = str(uuid.uuid4())
        await self.manager.handle_new_connection(conn_id, peer_connection_mock={"id": conn_id})
        
        self.assertIn(conn_id, self.manager.active_connections)
        session_id = self.manager.active_connections[conn_id]["session_id"]
        self.assertIn(session_id, self.mock_csm.sessions)
        self.assertEqual(len(self.mock_te.events), 1)
        self.assertEqual(self.mock_te.events[0]['name'], 'webrtc_connection_established')

    async def test_handle_signaling_message_offer(self):
        conn_id = str(uuid.uuid4())
        await self.manager.handle_new_connection(conn_id, peer_connection_mock={})
        
        callback_future = asyncio.Future()
        async def mock_signaling_callback(cid, msg):
            callback_future.set_result(msg)
            
        self.manager.signaling_callback = mock_signaling_callback
        
        await self.manager.handle_signaling_message(conn_id, {"type": "offer", "sdp": "mock-offer"})
        
        response = await asyncio.wait_for(callback_future, timeout=1)
        self.assertEqual(response['type'], 'answer')
        self.assertIn('sdp', response)

    async def test_handle_connection_ended(self):
        conn_id = str(uuid.uuid4())
        await self.manager.handle_new_connection(conn_id, peer_connection_mock={})
        
        session_id = self.manager.active_connections[conn_id]["session_id"]
        session = self.mock_csm.get_session_by_uuid(session_id)
        
        await self.manager.handle_connection_ended(conn_id, "test_end")
        
        self.assertNotIn(conn_id, self.manager.active_connections)
        self.assertTrue(session.ended)
        self.assertEqual(session.end_reason, "webrtc_ended_test_end")

    async def test_send_media_to_unknown_connection(self):
        # This test ensures that sending media to a non-existent connection doesn't raise an error.
        try:
            await self.manager.send_media("unknown-conn-id", b"some_audio")
        except Exception as e:
            self.fail(f"Sending media to unknown connection raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()