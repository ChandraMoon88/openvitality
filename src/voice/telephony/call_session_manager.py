import uuid
import time
import logging
import threading
from enum import Enum, auto

logger = logging.getLogger(__name__)

class CallState(Enum):
    RINGING = auto()
    CONNECTED = auto()
    ON_HOLD = auto()
    ENDED = auto()
    TRANSFERRED = auto()
    FAILED = auto()

class CallSession:
    def __init__(self, call_id: str, caller_id: str, callee_id: str = None, session_type: str = "SIP"):
        self.call_id = call_id
        self.caller_id = caller_id
        self.callee_id = callee_id
        self.session_type = session_type # e.g., "SIP", "WebRTC", "Twilio"
        self.start_time = time.time()
        self.end_time = None
        self.state = CallState.RINGING
        self.recording_enabled = False
        self.transfer_destination = None
        self.quality_metrics = {
            "latency": [],
            "packet_loss": [],
            "mos_score": []
        }
        self.metadata = {} # For any extra session-specific data
        logger.info(f"CallSession {self.call_id} created for {self.caller_id} (Type: {self.session_type})")

    def update_state(self, new_state: CallState):
        if not isinstance(new_state, CallState):
            raise ValueError("new_state must be a valid CallState enum member.")
        logger.info(f"CallSession {self.call_id} state changed from {self.state.name} to {new_state.name}")
        self.state = new_state
        if new_state == CallState.ENDED or new_state == CallState.FAILED:
            self.end_time = time.time()

    def enable_recording(self, enable: bool):
        self.recording_enabled = enable
        logger.info(f"CallSession {self.call_id} recording set to: {enable}")

    def transfer_call(self, destination: str, transfer_type: str = "blind"):
        self.transfer_destination = destination
        self.update_state(CallState.TRANSFERRED)
        logger.info(f"CallSession {self.call_id} transferred ({transfer_type}) to: {destination}")

    def add_quality_metric(self, metric_type: str, value):
        if metric_type in self.quality_metrics:
            self.quality_metrics[metric_type].append((time.time(), value))
        else:
            logger.warning(f"Unknown quality metric type: {metric_type}")

    @property
    def duration(self):
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def to_dict(self):
        return {
            "call_id": self.call_id,
            "caller_id": self.caller_id,
            "callee_id": self.callee_id,
            "session_type": self.session_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "state": self.state.name,
            "recording_enabled": self.recording_enabled,
            "transfer_destination": self.transfer_destination,
            "duration": self.duration,
            "quality_metrics": {k: [v[1] for v in val] for k, val in self.quality_metrics.items()}, # Only values
            "metadata": self.metadata
        }

class CallSessionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.active_sessions = {}
                logger.info("CallSessionManager initialized.")
        return cls._instance

    def create_session(self, caller_id: str, callee_id: str = None, session_type: str = "SIP", existing_call_id: str = None) -> CallSession:
        call_id = existing_call_id if existing_call_id else str(uuid.uuid4())
        if call_id in self.active_sessions:
            logger.warning(f"CallSession with ID {call_id} already exists. Returning existing session.")
            return self.active_sessions[call_id]

        session = CallSession(call_id, caller_id, callee_id, session_type)
        self.active_sessions[call_id] = session
        return session

    def get_session(self, call_id: str) -> CallSession | None:
        return self.active_sessions.get(call_id)

    def end_session(self, call_id: str):
        session = self.active_sessions.pop(call_id, None)
        if session:
            session.update_state(CallState.ENDED)
            logger.info(f"CallSession {call_id} ended and removed. Duration: {session.duration:.2f} seconds.")
            return session
        logger.warning(f"Attempted to end non-existent session: {call_id}")
        return None
    
    def get_active_sessions_count(self) -> int:
        return len(self.active_sessions)

    def get_all_active_sessions(self) -> dict[str, CallSession]:
        return self.active_sessions

    def cleanup_inactive_sessions(self, timeout_seconds: int = 3600):
        """Removes sessions that have been ended for a specified timeout."""
        current_time = time.time()
        to_remove = []
        for call_id, session in self.active_sessions.items():
            if session.state == CallState.ENDED and session.end_time and (current_time - session.end_time > timeout_seconds):
                to_remove.append(call_id)
        
        for call_id in to_remove:
            del self.active_sessions[call_id]
            logger.info(f"Cleaned up inactive CallSession {call_id}.")

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    manager = CallSessionManager()

    # Create a new session
    session1 = manager.create_session(caller_id="+1234567890", session_type="SIP")
    print(f"Session 1 ID: {session1.call_id}, State: {session1.state.name}")

    # Update state and enable recording
    session1.update_state(CallState.CONNECTED)
    session1.enable_recording(True)
    session1.add_quality_metric("mos_score", 4.5)
    session1.add_quality_metric("latency", 120)
    print(f"Session 1 State: {session1.state.name}, Recording: {session1.recording_enabled}")

    # Create another session
    session2 = manager.create_session(caller_id="+9876543210", session_type="WebRTC")
    print(f"Session 2 ID: {session2.call_id}, State: {session2.state.name}")

    # Get a session
    retrieved_session = manager.get_session(session1.call_id)
    if retrieved_session:
        print(f"Retrieved Session ID: {retrieved_session.call_id}, Caller: {retrieved_session.caller_id}")
        retrieved_session.add_quality_metric("mos_score", 4.2)

    # Transfer a call
    session1.transfer_call("human_agent_queue")
    print(f"Session 1 State after transfer: {session1.state.name}")
    
    # Simulate some time passing
    time.sleep(2)

    # End sessions
    ended_session1 = manager.end_session(session1.call_id)
    if ended_session1:
        print(f"Ended Session 1. Duration: {ended_session1.duration:.2f}s")
        print(f"Session 1 Details: {ended_session1.to_dict()}")

    manager.end_session(session2.call_id)
    print(f"Active sessions count: {manager.get_active_sessions_count()}")

    # Test creating with existing ID
    session3 = manager.create_session(caller_id="+1112223333", existing_call_id="my_predefined_id")
    session4 = manager.create_session(caller_id="+4445556666", existing_call_id="my_predefined_id") # Should return session3
    print(f"Session 3 ID: {session3.call_id}")
    print(f"Session 4 ID: {session4.call_id}")
    assert session3.call_id == session4.call_id

    # Cleanup (even though sessions are already ended, this demonstrates the method)
    time.sleep(1) # Allow end_time to be different
    manager.cleanup_inactive_sessions(timeout_seconds=0.5)
    print(f"Active sessions count after cleanup: {manager.get_active_sessions_count()}")
