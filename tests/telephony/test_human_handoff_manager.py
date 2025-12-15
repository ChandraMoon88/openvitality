import sys
sys.path.append('.')

import unittest
import asyncio
from typing import Dict, Any, List, Callable
import datetime
import uuid
import json

from src.telephony.human_handoff_manager import HumanHandoffManager

# --- Mock Dependencies ---
class MockCallRoutingManager:
    pass

class MockCallEventManager:
    def __init__(self):
        self.published_events = []
    async def publish(self, event_type: str, event_data: Dict[str, Any]):
        self.published_events.append({"type": event_type, "data": event_data})
    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], Any]):
        pass

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
        self.task_store = {}
    async def add_task(self, task: Dict, priority: int):
        task["priority"] = priority
        self._queue.append(task)
        self._queue.sort(key=lambda x: x["priority"], reverse=True)
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
    def __init__(self):
        self.logs = []
    def log_interaction(self, data: Dict):
        self.logs.append(data)

class MockTelemetryEmitter:
    def __init__(self):
        self.events = []
    def emit_event(self, event_name: str, data: Dict):
        self.events.append({"name": event_name, "data": data})

class TestHumanHandoffManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_crm = MockCallRoutingManager()
        self.mock_cem = MockCallEventManager()
        self.mock_csm = MockCallSessionManager()
        self.mock_pq = MockPriorityQueue()
        self.mock_al = MockAuditLogger()
        self.mock_te = MockTelemetryEmitter()
        
        # This is a bit of a hack for the test. The class in the source has `audit_logger` as an attribute but not in `__init__`.
        # So we're adding it here. A better solution would be to refactor the main class.
        self.handoff_manager = HumanHandoffManager(self.mock_crm, self.mock_cem, self.mock_csm, self.mock_pq, self.mock_te)
        self.handoff_manager.audit_logger = self.mock_al


    async def test_initiate_handoff(self):
        session_id = "s_handoff_1"
        handoff_context = {"last_ai_response": "I didn't understand that.", "patient_symptoms": ["fever", "cough"]}
        
        handoff_status = await self.handoff_manager.initiate_handoff(session_id, "AI_stuck_loop", handoff_context, priority=5)

        self.assertTrue(handoff_status["success"])
        self.assertEqual(handoff_status["queue_position"], 1)
        self.assertIsNotNone(handoff_status["handoff_id"])
        
        # Check if the task is in the queue
        self.assertEqual(len(self.mock_pq._queue), 1)
        self.assertEqual(self.mock_pq._queue[0]['session_id'], session_id)
        
        # Check telemetry and audit logs
        self.assertEqual(len(self.mock_te.events), 1)
        self.assertEqual(self.mock_te.events[0]['name'], 'human_handoff_initiated')
        self.assertEqual(len(self.mock_al.logs), 1)
        self.assertEqual(self.mock_al.logs[0]['event_type'], 'human_handoff_initiated')

    async def test_assign_next_handoff_to_agent(self):
        # First, add a task to the queue
        session_id = "s_handoff_1"
        handoff_context = {"last_ai_response": "I didn't understand that."}
        await self.handoff_manager.initiate_handoff(session_id, "AI_stuck_loop", handoff_context, priority=5)

        # Agent 1 is available by default
        agent_id = "agent_1"
        assigned_task = await self.handoff_manager.assign_next_handoff_to_agent(agent_id)

        self.assertIsNotNone(assigned_task)
        self.assertEqual(assigned_task['session_id'], session_id)
        self.assertEqual(assigned_task['assigned_to'], agent_id)

        # Check that the queue is now empty
        self.assertEqual(len(self.mock_pq._queue), 0)

    async def test_assign_handoff_to_unavailable_agent(self):
         # First, add a task to the queue
        session_id = "s_handoff_1"
        await self.handoff_manager.initiate_handoff(session_id, "AI_stuck_loop", {}, priority=5)

        # Agent 3 is unavailable by default
        agent_id = "agent_3"
        assigned_task = await self.handoff_manager.assign_next_handoff_to_agent(agent_id)

        self.assertIsNone(assigned_task)
        # The queue should still have the task
        self.assertEqual(len(self.mock_pq._queue), 1)

    async def test_update_agent_availability_and_assign(self):
        # Add a task
        session_id = "s_handoff_2"
        await self.handoff_manager.initiate_handoff(session_id, "user_request", {}, priority=3)

        # Agent 3 is unavailable, so they can't get a task
        agent_id = "agent_3"
        task = await self.handoff_manager.assign_next_handoff_to_agent(agent_id)
        self.assertIsNone(task)
        
        # Make agent 3 available
        await self.handoff_manager.update_agent_availability(agent_id, True, skills=["technical"])
        
        # Now agent 3 should be able to get the task
        task = await self.handoff_manager.assign_next_handoff_to_agent(agent_id)
        self.assertIsNotNone(task)
        self.assertEqual(task['session_id'], session_id)
        self.assertEqual(task['assigned_to'], agent_id)

if __name__ == "__main__":
    unittest.main()