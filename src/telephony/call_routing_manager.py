# src/telephony/call_routing_manager.py

from typing import Dict, Any, List
import asyncio
import datetime
import json
from enum import Enum, auto

# Assuming these imports will be available from other modules
# from src.voice.telephony.ivr_menu_builder import IVRMenuBuilder, IVRAction
# from src.core.intent_classifier import IntentClassifier # Or src.language.intent_parser
# from src.voice.telephony.emergency_call_routing import EmergencyCallRouter
# from src.telephony.call_event_manager import CallEventManager
# from src.voice.telephony.call_session_manager import CallSessionManager
# from src.core.telemetry_emitter import TelemetryEmitter


class IVRAction(Enum):
    ROUTE_TO_EMERGENCY = auto()
    ROUTE_TO_HUMAN_AGENT = auto()
    ROUTE_TO_AI_ASSISTANT = auto()
    REPEAT_MENU = auto()
    HANGUP = auto()
    PLAY_MESSAGE = auto()

class IVRMenu:
    def __init__(self, menu_id):
        self.menu_id = menu_id



class CallRoutingManager:
    """
    Routes incoming calls to appropriate AI agents or human operators based on
    user input (DTMF, speech intent), time of day, and agent availability.
    """
    def __init__(self, ivr_menu_builder_instance, intent_classifier_instance, emergency_call_router_instance, call_event_manager_instance, call_session_manager_instance, telemetry_emitter_instance):
        """
        Initializes the CallRoutingManager.
        
        :param ivr_menu_builder_instance: An initialized IVRMenuBuilder instance.
        :param intent_classifier_instance: An initialized IntentClassifier instance.
        :param emergency_call_router_instance: An initialized EmergencyCallRouter instance.
        :param call_event_manager_instance: An initialized CallEventManager instance.
        :param call_session_manager_instance: An initialized CallSessionManager instance.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.ivr_menu_builder = ivr_menu_builder_instance
        self.intent_classifier = intent_classifier_instance
        self.emergency_call_router = emergency_call_router_instance
        self.event_manager = call_event_manager_instance
        self.session_manager = call_session_manager_instance
        self.telemetry = telemetry_emitter_instance
        
        self.agent_availability = {"human_operator": True, "ai_assistant": True} # Mock availability
        self.operating_hours_start = datetime.time(9, 0) # 9 AM
        self.operating_hours_end = datetime.time(17, 0) # 5 PM

        # Mapping of intents to agents
        self.intent_to_agent_map = {
            "medical_emergency": "EmergencyAgent",
            "symptom_report": "MedicalTriageAgent",
            "appointment_booking": "AppointmentBookingAgent",
            "general_question": "AIAssistant"
        }
        
        print("✅ CallRoutingManager initialized.")

    async def route_call(self, session_id: str, current_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines the appropriate routing for an incoming call based on current input.
        
        :param session_id: The ID of the current call session.
        :param current_input: A dictionary containing the user's input (e.g., {"type": "DTMF", "digit": "1"}
                              or {"type": "Speech", "text": "I have a headache"}).
        :return: A dictionary specifying the next action (e.g., {"action": "route_to_agent", "agent_id": "..."}).
        """
        routing_decision = {
            "action": "stay_with_ai_assistant",
            "target": "AIAssistant",
            "reason": "Default AI assistant handling."
        }
        
        session = self.session_manager.get_session_by_uuid(session_id)
        if not session:
            print(f"Session {session_id} not found for routing.")
            self.telemetry.emit_event("call_routing_error", {"session_id": session_id, "error": "session_not_found"})
            return {"action": "disconnect", "reason": "Session not found."}

        # 1. Check for DTMF input (high priority for IVR navigation)
        if current_input.get("type") == "DTMF":
            dtmf_digit = current_input.get("digit")
            current_ivr_menu = session.get("current_ivr_menu", self.ivr_menu_builder.get_root_menu())
            
            ivr_action, ivr_param = self.ivr_menu_builder.navigate(current_ivr_menu.menu_id, dtmf_digit)
            
            if ivr_action == IVRAction.ROUTE_TO_EMERGENCY:
                # Emergency calls have highest priority, bypass regular routing
                return await self._handle_emergency_routing(session_id, current_input)
            elif ivr_action == IVRAction.ROUTE_TO_HUMAN_AGENT:
                routing_decision.update({"action": "transfer_to_human", "target": "human_operator", "reason": "User requested human agent via IVR."})
                session.update({"current_agent": "human_operator"})
            elif ivr_action == IVRAction.ROUTE_TO_AI_ASSISTANT:
                 routing_decision.update({"action": "route_to_agent", "target": "AIAssistant", "reason": "User requested AI assistant via IVR."})
                 session.update({"current_agent": "AIAssistant"})
            elif isinstance(ivr_action, self.ivr_menu_builder.IVRMenu): # Next menu
                session.update({"current_ivr_menu": ivr_action}) # Store next menu state
                routing_decision.update({"action": "play_ivr_menu", "target": ivr_action.menu_id, "reason": "Navigating IVR menu."})
            elif ivr_action == IVRAction.REPEAT_MENU:
                routing_decision.update({"action": "play_ivr_menu", "target": current_ivr_menu.menu_id, "reason": "Invalid DTMF or timeout, repeating menu."})
            elif ivr_action == IVRAction.HANGUP:
                 routing_decision.update({"action": "disconnect", "reason": "IVR indicated hangup."})
            
            self.telemetry.emit_event("call_routing_dtmf", {"session_id": session_id, "digit": dtmf_digit, "decision": routing_decision["action"]})


        # 2. Process speech input (if not handled by DTMF)
        elif current_input.get("type") == "Speech":
            speech_text = current_input.get("text")
            
            mock_intent_result = self.intent_classifier.classify(speech_text)
            
            if mock_intent_result.get("primary_intent") == "medical_emergency":
                return await self._handle_emergency_routing(session_id, current_input)
            
            target_agent = self.intent_to_agent_map.get(mock_intent_result.get("primary_intent"), "AIAssistant")
            routing_decision.update({
                "action": "route_to_agent",
                "target": target_agent,
                "reason": f"Speech intent classified as '{mock_intent_result.get('primary_intent')}'."
            })
            session.update({"current_agent": target_agent})
            self.telemetry.emit_event("call_routing_speech", {"session_id": session_id, "intent": mock_intent_result.get("primary_intent"), "decision": routing_decision["action"]})

        # 3. Final availability check and fallback logic
        # This block now runs for all decisions that weren't an early return (like emergency)
        if routing_decision["action"] in ["route_to_agent", "transfer_to_human", "stay_with_ai_assistant"]:
             if not self.agent_availability.get(routing_decision["target"], False):
                if self.agent_availability.get("human_operator"):
                    if not self._is_during_operating_hours():
                        routing_decision.update({"action": "transfer_to_human_voicemail", "target": "human_operator", "reason": f"Target agent '{routing_decision['target']}' unavailable, outside operating hours."})
                    else:
                        routing_decision.update({"action": "transfer_to_human", "target": "human_operator", "reason": f"Target agent '{routing_decision['target']}' unavailable."})
                else:
                    routing_decision.update({"action": "disconnect", "reason": "All agents unavailable."})

        return routing_decision

    async def _handle_emergency_routing(self, session_id: str, current_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles routing for detected emergency calls.
        """
        print(f"🚨 EMERGENCY DETECTED for session {session_id}!")
        # The emergency call router would have access to session and global config (e.g., regional emergency numbers)
        # In real system, this would trigger emergency protocol.
        mock_region_config = {"emergency_numbers": {"emergency": "911", "ambulance": "911"}} # Example
        emergency_action_result = await self.emergency_call_router.handle_emergency_call(
            self.session_manager.get_session_by_uuid(session_id), mock_region_config # Pass relevant session obj
        )
        
        if emergency_action_result.get("status") == "transferred_to_psap":
            return {"action": "transfer_to_emergency_services", "target": emergency_action_result.get("target"), "reason": "Emergency protocol initiated."}
        else:
            return {"action": "disconnect", "reason": "Emergency handling failed or unable to transfer."}

    def _is_during_operating_hours(self) -> bool:
        """Checks if current time is within defined operating hours."""
        now = datetime.datetime.now().time()
        return self.operating_hours_start <= now <= self.operating_hours_end

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockIVRMenuBuilder:
        def __init__(self):
            class RootMenu:
                def __init__(self): self.menu_id = "root_menu"
                def navigate(self, menu_id, dtmf_input):
                    if dtmf_input == "1": return IVRAction.ROUTE_TO_EMERGENCY, None
                    if dtmf_input == "2": return IVRAction.ROUTE_TO_HUMAN_AGENT, None
                    if dtmf_input == "3": return IVRAction.ROUTE_TO_AI_ASSISTANT, None
                    return IVRAction.REPEAT_MENU, None
            self._root_menu = RootMenu()
            self.IVRAction = IVRAction # Expose for easy testing
        def get_root_menu(self): return self._root_menu
        def navigate(self, menu_id, dtmf_input):
            return self._root_menu.navigate(menu_id, dtmf_input)

    class MockIntentClassifier:
        def classify(self, text: str) -> Dict:
            if "emergency" in text.lower() or "can't breathe" in text.lower():
                return {"primary_intent": "medical_emergency", "confidence": 0.99}
            if "book" in text.lower():
                return {"primary_intent": "appointment_booking", "confidence": 0.8}
            if "headache" in text.lower():
                return {"primary_intent": "symptom_report", "confidence": 0.75}
            return {"primary_intent": "general_question", "confidence": 0.6}

    class MockEmergencyCallRouter:
        async def handle_emergency_call(self, session, region_config) -> Dict:
            print(f"Mock ECR: Handling emergency call for session {session.session_id}")
            return {"status": "transferred_to_psap", "target": "911"}

    class MockCallEventManager:
        async def publish(self, event_type: str, event_data: Dict[str, Any]):
            print(f"Mock EventManager: Published '{event_type}' - {event_data}")

    class MockCallSession:
        def __init__(self, session_id):
            self.session_id = session_id
            self._data = {}
        def get(self, key, default=None): return self._data.get(key, default)
        def update(self, new_data: Dict): self._data.update(new_data)
        @property
        def state(self): return self._data.get("state", "IDLE")
        def connected(self): self.update({"state": "CONNECTED"}) # Simulate
        def end(self, reason): self.update({"state": "ENDED", "reason": reason}) # Simulate

    class MockCallSessionManager:
        def __init__(self):
            self.sessions = {"s_route_1": MockCallSession("s_route_1"), "s_route_2": MockCallSession("s_route_2"), "s_route_3": MockCallSession("s_route_3"), "s_route_4": MockCallSession("s_route_4")}
        def get_session_by_uuid(self, session_id): return self.sessions.get(session_id)

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_ivr = MockIVRMenuBuilder()
    mock_ic = MockIntentClassifier()
    mock_ecr = MockEmergencyCallRouter()
    mock_cem = MockCallEventManager()
    mock_csm = MockCallSessionManager()
    mock_te = MockTelemetryEmitter()
    
    router = CallRoutingManager(mock_ivr, mock_ic, mock_ecr, mock_cem, mock_csm, mock_te)

    # --- Test 1: DTMF input for emergency ---
    print("\n--- Test 1: DTMF '1' for Emergency ---")
    current_input_1 = {"type": "DTMF", "digit": "1"}
    route_1 = asyncio.run(router.route_call("s_route_1", current_input_1))
    print(f"Routing Decision 1: {json.dumps(route_1, indent=2)}")

    # --- Test 2: Speech input for appointment booking ---
    print("\n--- Test 2: Speech 'book an appointment' ---")
    current_input_2 = {"type": "Speech", "text": "I need to book an appointment."}
    route_2 = asyncio.run(router.route_call("s_route_2", current_input_2))
    print(f"Routing Decision 2: {json.dumps(route_2, indent=2)}")

    # --- Test 3: Speech input for emergency ---
    print("\n--- Test 3: Speech 'I can't breathe' ---")
    current_input_3 = {"type": "Speech", "text": "I can't breathe, this is an emergency!"}
    route_3 = asyncio.run(router.route_call("s_route_3", current_input_3))
    print(f"Routing Decision 3: {json.dumps(route_3, indent=2)}")

    # --- Test 4: General question (AI assistant) ---
    print("\n--- Test 4: General question (AI assistant) ---")
    current_input_4 = {"type": "Speech", "text": "What is the weather like?"}
    route_4 = asyncio.run(router.route_call("s_route_4", current_input_4))
    print(f"Routing Decision 4: {json.dumps(route_4, indent=2)}")

    # --- Test 5: AI assistant unavailable (mock for now, assume outside operating hours) ---
    print("\n--- Test 5: AI assistant unavailable ---")
    router.agent_availability["ai_assistant"] = False # Simulate AI being down or out of hours
    router.operating_hours_start = datetime.time(1, 0) # Set to ensure it's not during operating hours
    router.operating_hours_end = datetime.time(2, 0)
    current_input_5 = {"type": "Speech", "text": "Hello"}
    route_5 = asyncio.run(router.route_call("s_route_4", current_input_5)) # Use same session
    print(f"Routing Decision 5 (AI unavailable): {json.dumps(route_5, indent=2)}")
