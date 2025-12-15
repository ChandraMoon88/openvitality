# src/telephony/call_event_manager.py

from typing import Dict, Any, Callable, List
import asyncio
import json

# Assuming these imports will be available from other modules
# from src.voice.telephony.call_session_manager import CallSessionManager # To update call state
# from src.core.telemetry_emitter import TelemetryEmitter


class CallEventManager:
    """
    Centralized management system for telephony-related events (e.g., call started,
    connected, disconnected, DTMF received, media events).
    Uses a simple publish-subscribe (pub-sub) pattern for event distribution.
    """
    def __init__(self, call_session_manager_instance, telemetry_emitter_instance):
        """
        Initializes the CallEventManager.
        
        :param call_session_manager_instance: An initialized CallSessionManager instance.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.call_session_manager = call_session_manager_instance
        self.telemetry = telemetry_emitter_instance
        
        # Dictionary to store event handlers: {event_type: [handler_callable, ...]}:
        self._handlers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        
        print("✅ CallEventManager initialized.")

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]):
        """
        Subscribes a handler function to a specific event type.
        
        :param event_type: The type of event to subscribe to (e.g., "call_connected", "dtmf_received").
        :param handler: The callable function that will be executed when the event is published.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        print(f"Subscribed handler {handler.__name__} to event: {event_type}")

    async def publish(self, event_type: str, event_data: Dict[str, Any]):
        """
        Publishes an event, executing all subscribed handlers for that event type.
        Also updates the CallSessionManager for relevant call state changes.
        
        :param event_type: The type of event being published.
        :param event_data: A dictionary containing data relevant to the event.
        """
        print(f"Publishing event: {event_type} with data: {event_data}")
        self.telemetry.emit_event(f"call_event_{event_type}", event_data)
        
        # Update CallSessionManager for core call state changes
        session_id = event_data.get("session_id")
        if session_id:
            session = self.call_session_manager.get_session_by_uuid(session_id)
            if session:
                if event_type == "call_connected":
                    session.connected()
                elif event_type == "call_disconnected":
                    session.end(event_data.get("reason", "normal_clear"))
                elif event_type == "call_on_hold":
                    session.hold()
                elif event_type == "call_resumed":
                    session.resume()
                # Additional state updates can be added here
        
        # Execute all subscribed handlers asynchronously
        if event_type in self._handlers:
            tasks = [handler(event_data) for handler in self._handlers[event_type]]
            await asyncio.gather(*tasks) # Run handlers concurrently
        
        print(f"Event {event_type} published.")

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockCallSession:
        def __init__(self, session_id):
            self.session_id = session_id
            self.state = "INITIAL"
        def connected(self):
            self.state = "CONNECTED"
            print(f"Mock CallSession {self.session_id}: State changed to CONNECTED")
        def end(self, reason):
            self.state = "DISCONNECTED"
            print(f"Mock CallSession {self.session_id}: State changed to DISCONNECTED ({reason})")
        def hold(self):
            self.state = "ON_HOLD"
            print(f"Mock CallSession {self.session_id}: State changed to ON_HOLD")
        def resume(self):
            self.state = "CONNECTED"
            print(f"Mock CallSession {self.session_id}: State changed to RESUMED")

    class MockCallSessionManager:
        def __init__(self):
            self.sessions = {"s1": MockCallSession("s1"), "s2": MockCallSession("s2")}
        def get_session_by_uuid(self, session_id):
            return self.sessions.get(session_id)
        def create_session(self, call_id, from_num, to_num):
            # Simplified, usually would generate unique session_id
            new_session = MockCallSession(f"new_{call_id}")
            self.sessions[new_session.session_id] = new_session
            return new_session

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_csm = MockCallSessionManager()
    mock_te = MockTelemetryEmitter()
    
    event_manager = CallEventManager(mock_csm, mock_te)

    # --- Define some event handlers ---
    async def handle_call_connected(event_data: Dict):
        print(f"  [Handler] Call {event_data['session_id']} is now fully connected!")

    async def handle_dtmf_received(event_data: Dict):
        print(f"  [Handler] DTMF '{event_data['digit']}' received for session {event_data['session_id']}.")
        
    async def handle_any_event(event_data: Dict):
        print(f"  [Generic Handler] Event {event_data.get('event_type') or 'unknown'} occurred.")

    # --- Subscribe handlers ---
    event_manager.subscribe("call_connected", handle_call_connected)
    event_manager.subscribe("dtmf_received", handle_dtmf_received)
    event_manager.subscribe("call_connected", handle_any_event) # A single event can have multiple handlers

    # --- Test 1: Publish a 'call_connected' event ---
    print("\n--- Test 1: Publish 'call_connected' ---")
    session_id_1 = "s1"
    asyncio.run(event_manager.publish("call_connected", {"session_id": session_id_1, "call_id": "sip_call_123"}))
    print(f"Session {session_id_1} state: {mock_csm.get_session_by_uuid(session_id_1).state}")

    # --- Test 2: Publish a 'dtmf_received' event ---
    print("\n--- Test 2: Publish 'dtmf_received' ---")
    session_id_2 = "s2"
    asyncio.run(event_manager.publish("dtmf_received", {"session_id": session_id_2, "digit": "1"}))
    print(f"Session {session_id_2} state: {mock_csm.get_session_by_uuid(session_id_2).state}")

    # --- Test 3: Publish a 'call_disconnected' event ---
    print("\n--- Test 3: Publish 'call_disconnected' ---")
    asyncio.run(event_manager.publish("call_disconnected", {"session_id": session_id_1, "reason": "user_hangup"}))
    print(f"Session {session_id_1} state: {mock_csm.get_session_by_uuid(session_id_1).state}")

    # --- Test 4: Publish an unhandled event type ---
    print("\n--- Test 4: Publish unhandled event type ---")
    asyncio.run(event_manager.publish("media_dropped", {"session_id": session_id_2, "packet_loss": "10%"}))
