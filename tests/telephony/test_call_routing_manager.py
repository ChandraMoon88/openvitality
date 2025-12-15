import sys
sys.path.append('.')

import unittest
import asyncio
import datetime
from typing import Dict, Any, Tuple

# Import the actual classes from the source file to ensure type consistency
from src.telephony.call_routing_manager import CallRoutingManager, IVRAction, IVRMenu

# --- Mock Dependencies ---

class MockIVRMenuBuilder:
    def __init__(self):
        self.root_menu = IVRMenu("root")
        # Expose for isinstance checks and direct use in tests
        self.IVRMenu = IVRMenu
        
    def get_root_menu(self):
        return self.root_menu
        
    def navigate(self, menu_id: str, dtmf_input: str) -> Tuple[Any, Any]:
        if dtmf_input == "1":
            return IVRAction.ROUTE_TO_EMERGENCY, None
        if dtmf_input == "2":
            return IVRAction.ROUTE_TO_HUMAN_AGENT, None
        if dtmf_input == "9": # For testing a different menu
            return IVRMenu("submenu"), None
        return IVRAction.REPEAT_MENU, None

class MockIntentClassifier:
    def classify(self, text: str) -> Dict:
        if "emergency" in text.lower():
            return {"primary_intent": "medical_emergency"}
        if "book" in text.lower():
            return {"primary_intent": "appointment_booking"}
        return {"primary_intent": "general_question"}

class MockEmergencyCallRouter:
    async def handle_emergency_call(self, session, region_config) -> Dict:
        return {"status": "transferred_to_psap", "target": "911"}

class MockCallEventManager:
    async def publish(self, event_type: str, event_data: Dict[str, Any]):
        pass

class MockCallSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self._data = {}
    def get(self, key, default=None): return self._data.get(key, default)
    def update(self, new_data: Dict): self._data.update(new_data)

class MockCallSessionManager:
    def __init__(self):
        self.sessions = {f"s{i}": MockCallSession(f"s{i}") for i in range(10)}
    def get_session_by_uuid(self, session_id): return self.sessions.get(session_id)

class MockTelemetryEmitter:
    def __init__(self):
        self.events = []
    def emit_event(self, event_name: str, data: Dict):
        self.events.append({"name": event_name, "data": data})


class TestCallRoutingManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_ivr = MockIVRMenuBuilder()
        # The source file now has IVRAction, but the mock navigator needs to use it.
        # This setup ensures the mock builder can access the real Enum.
        setattr(self.mock_ivr, 'IVRAction', IVRAction)
        
        self.mock_ic = MockIntentClassifier()
        self.mock_ecr = MockEmergencyCallRouter()
        self.mock_cem = MockCallEventManager()
        self.mock_csm = MockCallSessionManager()
        self.mock_te = MockTelemetryEmitter()
        
        self.router = CallRoutingManager(self.mock_ivr, self.mock_ic, self.mock_ecr, self.mock_cem, self.mock_csm, self.mock_te)

    async def test_route_call_dtmf_emergency(self):
        decision = await self.router.route_call("s1", {"type": "DTMF", "digit": "1"})
        self.assertEqual(decision["action"], "transfer_to_emergency_services")
        self.assertEqual(decision["target"], "911")

    async def test_route_call_dtmf_human_agent(self):
        self.router.agent_availability["human_operator"] = True
        decision = await self.router.route_call("s2", {"type": "DTMF", "digit": "2"})
        self.assertEqual(decision["action"], "transfer_to_human")
        self.assertEqual(decision["target"], "human_operator")

    async def test_route_call_speech_intent_booking(self):
        # Ensure the target agent is marked as available for this test
        self.router.agent_availability["AppointmentBookingAgent"] = True
        decision = await self.router.route_call("s3", {"type": "Speech", "text": "I want to book an appointment"})
        self.assertEqual(decision["action"], "route_to_agent")
        self.assertEqual(decision["target"], "AppointmentBookingAgent")
        
        session = self.mock_csm.get_session_by_uuid("s3")
        self.assertEqual(session.get("current_agent"), "AppointmentBookingAgent")

    async def test_route_call_speech_intent_emergency(self):
        decision = await self.router.route_call("s4", {"type": "Speech", "text": "This is an emergency"})
        self.assertEqual(decision["action"], "transfer_to_emergency_services")

    async def test_route_call_fallback_ai_unavailable(self):
        # Make AI unavailable, but human available
        self.router.agent_availability["AIAssistant"] = False
        self.router.agent_availability["human_operator"] = True
        
        decision = await self.router.route_call("s5", {"type": "Speech", "text": "general question"})
        self.assertEqual(decision["action"], "transfer_to_human")

    async def test_route_call_fallback_all_unavailable(self):
        # Make all potentially relevant agents unavailable
        self.router.agent_availability["AIAssistant"] = False
        self.router.agent_availability["human_operator"] = False
        self.router.agent_availability["AppointmentBookingAgent"] = False # Include other agents
        
        decision = await self.router.route_call("s6", {"type": "Speech", "text": "general question"})
        self.assertEqual(decision["action"], "disconnect")

    async def test_route_call_outside_operating_hours_voicemail(self):
        # Set time to be outside 9-5
        self.router.operating_hours_start = datetime.time(1, 0)
        self.router.operating_hours_end = datetime.time(2, 0)
        
        # Make AI unavailable, human available
        self.router.agent_availability["AIAssistant"] = False
        self.router.agent_availability["human_operator"] = True
        
        decision = await self.router.route_call("s7", {"type": "Speech", "text": "general question"})
        self.assertEqual(decision["action"], "transfer_to_human_voicemail")


if __name__ == "__main__":
    unittest.main()