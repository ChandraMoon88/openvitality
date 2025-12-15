import sys
sys.path.append('.')

import unittest
import asyncio
from typing import Dict, Any

from src.telephony.call_event_manager import CallEventManager

# --- Mock Dependencies ---
class MockCallSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.state = "INITIAL"
        self.end_reason = None
    def connected(self): self.state = "CONNECTED"
    def end(self, reason):
        self.state = "DISCONNECTED"
        self.end_reason = reason
    def hold(self): self.state = "ON_HOLD"
    def resume(self): self.state = "CONNECTED"

class MockCallSessionManager:
    def __init__(self):
        self.sessions = {"s1": MockCallSession("s1"), "s2": MockCallSession("s2")}
    def get_session_by_uuid(self, session_id):
        return self.sessions.get(session_id)

class MockTelemetryEmitter:
    def __init__(self):
        self.events = []
    def emit_event(self, event_name: str, data: Dict):
        self.events.append({"name": event_name, "data": data})

class TestCallEventManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_csm = MockCallSessionManager()
        self.mock_te = MockTelemetryEmitter()
        self.event_manager = CallEventManager(self.mock_csm, self.mock_te)
        self.handler_called_flag = False
        self.handler_data = None

    async def simple_handler(self, event_data: Dict):
        self.handler_called_flag = True
        self.handler_data = event_data

    def test_subscribe(self):
        self.assertNotIn("test_event", self.event_manager._handlers)
        self.event_manager.subscribe("test_event", self.simple_handler)
        self.assertIn("test_event", self.event_manager._handlers)
        self.assertEqual(len(self.event_manager._handlers["test_event"]), 1)

    async def test_publish_to_subscribed_handler(self):
        self.event_manager.subscribe("test_event", self.simple_handler)
        event_data = {"key": "value"}
        
        await self.event_manager.publish("test_event", event_data)
        
        self.assertTrue(self.handler_called_flag)
        self.assertEqual(self.handler_data, event_data)
        
        # Check telemetry
        self.assertEqual(len(self.mock_te.events), 1)
        self.assertEqual(self.mock_te.events[0]['name'], 'call_event_test_event')
        self.assertEqual(self.mock_te.events[0]['data'], event_data)

    async def test_publish_to_multiple_handlers(self):
        handler1_called = asyncio.Future()
        handler2_called = asyncio.Future()

        async def handler1(data):
            handler1_called.set_result(True)

        async def handler2(data):
            handler2_called.set_result(True)

        self.event_manager.subscribe("multi_event", handler1)
        self.event_manager.subscribe("multi_event", handler2)

        await self.event_manager.publish("multi_event", {})

        await asyncio.wait([handler1_called, handler2_called], timeout=1)

        self.assertTrue(handler1_called.done())
        self.assertTrue(handler2_called.done())

    async def test_publish_unhandled_event(self):
        # This test just ensures that publishing an event with no subscribers doesn't raise an error.
        try:
            await self.event_manager.publish("unhandled_event", {})
        except Exception as e:
            self.fail(f"Publishing an unhandled event raised an exception: {e}")
        
        # Should still be tracked by telemetry
        self.assertEqual(len(self.mock_te.events), 1)

    async def test_session_state_change_on_event(self):
        session = self.mock_csm.get_session_by_uuid("s1")
        self.assertEqual(session.state, "INITIAL")

        # Test 'call_connected'
        await self.event_manager.publish("call_connected", {"session_id": "s1"})
        self.assertEqual(session.state, "CONNECTED")

        # Test 'call_on_hold'
        await self.event_manager.publish("call_on_hold", {"session_id": "s1"})
        self.assertEqual(session.state, "ON_HOLD")

        # Test 'call_resumed'
        await self.event_manager.publish("call_resumed", {"session_id": "s1"})
        self.assertEqual(session.state, "CONNECTED")

        # Test 'call_disconnected'
        await self.event_manager.publish("call_disconnected", {"session_id": "s1", "reason": "user_hangup"})
        self.assertEqual(session.state, "DISCONNECTED")
        self.assertEqual(session.end_reason, "user_hangup")

if __name__ == "__main__":
    unittest.main()