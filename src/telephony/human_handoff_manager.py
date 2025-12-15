# src/telephony/human_handoff_manager.py

from typing import Dict, Any, List
import asyncio
import datetime
import uuid
import json

# Assuming these imports will be available from other modules
# from src.telephony.call_routing_manager import CallRoutingManager
# from src.telephony.call_event_manager import CallEventManager
# from src.voice.telephony.call_session_manager import CallSessionManager
# from src.core.priority_queue import PriorityQueue # For managing agent queues
# from src.core.telemetry_emitter import TelemetryEmitter


class HumanHandoffManager:
    """
    Manages the seamless transfer of a call from an AI assistant to a human agent,
    ensuring context is preserved and agents are utilized efficiently.
    """
    def __init__(self, call_routing_manager_instance, call_event_manager_instance, call_session_manager_instance, agent_queue_instance, telemetry_emitter_instance):
        """
        Initializes the HumanHandoffManager.
        
        :param call_routing_manager_instance: An initialized CallRoutingManager instance.
        :param call_event_manager_instance: An initialized CallEventManager instance.
        :param call_session_manager_instance: An initialized CallSessionManager instance.
        :param agent_queue_instance: An initialized PriorityQueue instance for managing human agent queues.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.call_routing_manager = call_routing_manager_instance
        self.event_manager = call_event_manager_instance
        self.session_manager = call_session_manager_instance
        self.agent_queue = agent_queue_instance
        self.telemetry = telemetry_emitter_instance
        
        # In-memory store for agent availability: {agent_id: bool}
        self.agent_availability: Dict[str, bool] = {"agent_1": True, "agent_2": True, "agent_3": False}
        self.agent_skills: Dict[str, List[str]] = {
            "agent_1": ["general", "billing"],
            "agent_2": ["general", "medical_triage"],
            "agent_3": ["technical"]
        }
        
        print("✅ HumanHandoffManager initialized.")

    async def initiate_handoff(self, session_id: str, reason: str, context_for_human: Dict[str, Any] = None, priority: int = 1) -> Dict[str, Any]:
        """
        Initiates the process of transferring a call to a human agent.
        
        :param session_id: The ID of the call session to transfer.
        :param reason: The reason for the handoff (e.g., "AI_cannot_understand", "user_requested_human").
        :param context_for_human: A dictionary containing relevant conversation context to pass to the human agent.
        :param priority: The priority of this handoff in the queue (higher = more urgent).
        :return: A dictionary with the handoff status.
        """
        handoff_status = {
            "success": False,
            "message": "Handoff failed.",
            "queue_position": None,
            "handoff_id": None
        }
        
        session = self.session_manager.get_session_by_uuid(session_id)
        if not session:
            handoff_status["message"] = f"Session {session_id} not found."
            self.telemetry.emit_event("handoff_failed", {"session_id": session_id, "reason": "session_not_found"})
            return handoff_status
        
        # 1. Prepare handoff task
        handoff_id = str(uuid.uuid4())
        handoff_task = {
            "handoff_id": handoff_id,
            "session_id": session_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "reason": reason,
            "context_for_human": context_for_human or {},
            "status": "queued",
            "priority": priority
        }
        
        # 2. Add to agent queue
        await self.agent_queue.add_task(handoff_task, priority)
        queue_position = await self.agent_queue.get_task_position(handoff_id) # Mock method

        handoff_status["success"] = True
        handoff_status["message"] = "Call successfully queued for human agent."
        handoff_status["handoff_id"] = handoff_id
        handoff_status["queue_position"] = queue_position
        
        # Update session state
        session.update({"status": "awaiting_human_handoff", "handoff_id": handoff_id})

        self.audit_logger.log_interaction({
            "event_type": "human_handoff_initiated",
            "session_id": session_id,
            "handoff_id": handoff_id,
            "reason": reason,
            "priority": priority
        })
        self.telemetry.emit_event("human_handoff_initiated", {"session_id": session_id, "handoff_id": handoff_id, "reason": reason})
        print(f"✅ Handoff initiated for session {session_id}. Handoff ID: {handoff_id}. Queue position: {queue_position}")
        
        # Publish event for UI/agent system to pick up
        await self.event_manager.publish("human_handoff_queued", {"session_id": session_id, "handoff_id": handoff_id, "queue_position": queue_position})
        
        return handoff_status

    async def update_agent_availability(self, agent_id: str, is_available: bool, skills: List[str] = None):
        """
        Updates the availability status of a human agent.
        
        :param agent_id: The ID of the human agent.
        :param is_available: True if the agent is available, False otherwise.
        :param skills: Optional, list of skills the agent possesses.
        """
        self.agent_availability[agent_id] = is_available
        if skills is not None:
            self.agent_skills[agent_id] = skills

        status_text = "available" if is_available else "unavailable"
        print(f"Agent {agent_id} is now {status_text}.")
        self.telemetry.emit_event("agent_availability_updated", {"agent_id": agent_id, "is_available": is_available, "skills": skills})
        await self.event_manager.publish("agent_availability_changed", {"agent_id": agent_id, "is_available": is_available})

    async def assign_next_handoff_to_agent(self, agent_id: str) -> Dict[str, Any] | None:
        """
        Assigns the next highest priority handoff task to an available human agent.
        
        :param agent_id: The ID of the agent requesting a new task.
        :return: The handoff task details, or None if no tasks are available.
        """
        if not self.agent_availability.get(agent_id, False):
            print(f"Agent {agent_id} is not available for assignment.")
            return None
        
        next_task = await self.agent_queue.get_next_task()
        
        if next_task:
            handoff_id = next_task["handoff_id"]
            session_id = next_task["session_id"]
            
            # Update session and handoff task status
            session = self.session_manager.get_session_by_uuid(session_id)
            if session:
                session.update({"status": "transferred_to_human", "assigned_agent": agent_id})
            next_task["status"] = "assigned"
            next_task["assigned_to"] = agent_id
            next_task["timestamp_assigned"] = datetime.datetime.now().isoformat()

            self.audit_logger.log_interaction({
                "event_type": "human_handoff_assigned",
                "session_id": session_id,
                "handoff_id": handoff_id,
                "assigned_agent": agent_id
            })
            self.telemetry.emit_event("human_handoff_assigned", {"session_id": session_id, "handoff_id": handoff_id, "assigned_agent": agent_id})
            await self.event_manager.publish("human_handoff_assigned", {"session_id": session_id, "handoff_id": handoff_id, "agent_id": agent_id})
            
            print(f"Assigned handoff {handoff_id} (session {session_id}) to agent {agent_id}.")
            return next_task
        else:
            print(f"No pending handoff tasks for agent {agent_id}.")
            return None

    async def _handle_agent_disconnect(self, event_data: Dict[str, Any]):
        """Handler for agent disconnect events (updates availability)."""
        agent_id = event_data["agent_id"]
        await self.update_agent_availability(agent_id, False)

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockCallRoutingManager:
        pass # Not directly called in this example

    class MockCallEventManager:
        def __init__(self):
            self.published_events = []
        async def publish(self, event_type: str, event_data: Dict[str, Any]):
            self.published_events.append({"type": event_type, "data": event_data})
            print(f"Mock EventManager: Published '{event_type}' - {event_data}")
        def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], Any]):
            pass # Not used directly in this mock

    class MockCallSession:
        def __init__(self, session_id):
            self.session_id = session_id
            self._data = {"status": "active_with_ai"}
        def get(self, key, default=None): return self._data.get(key, default)
        def update(self, new_data: Dict):
            self._data.update(new_data)

    class MockCallSessionManager:
        def __init__(self):
            self.sessions = {"s_handoff_1": MockCallSession("s_handoff_1"), "s_handoff_2": MockCallSession("s_handoff_2")}
        def get_session_by_uuid(self, session_id):
            return self.sessions.get(session_id)

    class MockPriorityQueue:
        def __init__(self):
            self._queue = []
            self.task_store = {} # Store tasks by ID to simulate position lookup
        async def add_task(self, task: Dict, priority: int):
            task["priority"] = priority
            self._queue.append(task)
            self._queue.sort(key=lambda x: x["priority"], reverse=True) # Higher priority first
            self.task_store[task["handoff_id"]] = task
            return True
        async def get_next_task(self) -> Dict | None:
            if self._queue:
                return self._queue.pop(0)
            return None
        async def get_task_position(self, handoff_id: str) -> int | None:
            for i, task in enumerate(self._queue):
                if task["handoff_id"] == handoff_id:
                    return i + 1
            return None

    class MockAuditLogger:
        def log_interaction(self, data: Dict):
            print(f"Mock Audit Log: {json.dumps(data)}")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_crm = MockCallRoutingManager()
    mock_cem = MockCallEventManager()
    mock_csm = MockCallSessionManager()
    mock_pq = MockPriorityQueue()
    mock_al = MockAuditLogger()
    mock_te = MockTelemetryEmitter()
    
    handoff_manager = HumanHandoffManager(mock_crm, mock_cem, mock_csm, mock_pq, mock_al, mock_te)

    # --- Test 1: Initiate a high-priority handoff ---
    print("\n--- Test 1: Initiate a high-priority handoff ---")
    session_id_1 = "s_handoff_1"
    handoff_context_1 = {"last_ai_response": "I didn't understand that.", "patient_symptoms": ["fever", "cough"]}
    handoff_status_1 = asyncio.run(handoff_manager.initiate_handoff(session_id_1, "AI_stuck_loop", handoff_context_1, priority=5))
    print(f"Handoff Status 1: {json.dumps(handoff_status_1, indent=2)}")

    # --- Test 2: Initiate a medium-priority handoff ---
    print("\n--- Test 2: Initiate a medium-priority handoff ---")
    session_id_2 = "s_handoff_2"
    handoff_context_2 = {"user_requested": "speak to a human"}
    handoff_status_2 = asyncio.run(handoff_manager.initiate_handoff(session_id_2, "user_requested_human", handoff_context_2, priority=3))
    print(f"Handoff Status 2: {json.dumps(handoff_status_2, indent=2)}")

    # --- Test 3: Agent 1 requests next task ---
    print("\n--- Test 3: Agent 1 requests next task ---")
    assigned_task_1 = asyncio.run(handoff_manager.assign_next_handoff_to_agent("agent_1"))
    print(f"Assigned Task to Agent 1: {json.dumps(assigned_task_1, indent=2)}")

    # --- Test 4: Agent 3 (unavailable) requests next task ---
    print("\n--- Test 4: Agent 3 (unavailable) requests next task ---")
    assigned_task_3 = asyncio.run(handoff_manager.assign_next_handoff_to_agent("agent_3"))
    print(f"Assigned Task to Agent 3: {assigned_task_3}") # Expected: None

    # --- Test 5: Agent 3 becomes available and gets task ---
    print("\n--- Test 5: Agent 3 becomes available and gets task ---")
    asyncio.run(handoff_manager.update_agent_availability("agent_3", True, skills=["technical", "medical_triage"]))
    assigned_task_3_new = asyncio.run(handoff_manager.assign_next_handoff_to_agent("agent_3"))
    print(f"Assigned Task to Agent 3 (now available): {json.dumps(assigned_task_3_new, indent=2)}")
