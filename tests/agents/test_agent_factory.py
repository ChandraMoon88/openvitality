import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.agents.base_agent import BaseAgent
from src.agents.agent_factory import AgentFactory, register_agent, _AGENT_REGISTRY, _AGENT_POOL

# Define mock agent classes for testing
class MockTriageAgent(BaseAgent):
    # Fix: __init__ now accepts 'name' so it can receive it from the Factory
    def __init__(self, name="triage", **kwargs):
        super().__init__(name, "Handles initial patient triage.", {"role": "triage specialist"})
        self._memory["patient_symptoms"] = kwargs.get("patient_symptoms", [])
    
    async def process_input(self, text: str, context: dict) -> dict:
        self._memory["patient_symptoms"].append(text)
        return {"response_text": f"Triage agent received: {text}.", "context_update": {}, "action": "ask_more"}
    
    def reset_memory(self):
        super().reset_memory()
        self._memory["patient_symptoms"] = []

class MockAppointmentAgent(BaseAgent):
    # Fix: __init__ now accepts 'name' so it can receive it from the Factory
    def __init__(self, name="appointment", **kwargs):
        super().__init__(name, "Manages appointment booking.", {"role": "receptionist"})
        self._memory["booking_slots"] = kwargs.get("booking_slots", [])

    async def process_input(self, text: str, context: dict) -> dict:
        return {"response_text": f"Appointment agent processing: {text}.", "context_update": {}, "action": "propose_slots"}

    def reset_memory(self):
        super().reset_memory()
        self._memory["booking_slots"] = []

class TestAgentFactory(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Clear the registry and pool before each test
        _AGENT_REGISTRY.clear()
        _AGENT_POOL.clear()

    def test_register_agent_success(self):
        """Test successful registration of a BaseAgent subclass."""
        register_agent("triage_mock", MockTriageAgent)
        self.assertIn("triage_mock", _AGENT_REGISTRY)
        self.assertEqual(_AGENT_REGISTRY["triage_mock"], MockTriageAgent)

    def test_register_agent_invalid_type(self):
        """Test that registering a non-BaseAgent subclass raises a TypeError."""
        class BadAgent:
            pass
        with self.assertRaises(TypeError):
            register_agent("bad_agent", BadAgent)
        self.assertNotIn("bad_agent", _AGENT_REGISTRY)

    def test_list_registered_agents(self):
        """Test that list_registered_agents returns the correct list."""
        register_agent("triage_mock", MockTriageAgent)
        register_agent("appointment_mock", MockAppointmentAgent)
        self.assertEqual(AgentFactory.list_registered_agents(), ["triage_mock", "appointment_mock"])

    def test_create_agent_new_instance(self):
        """Test creating a new agent instance when not in pool or pooling disabled."""
        register_agent("triage_mock", MockTriageAgent)
        
        # Test new instance creation
        agent = AgentFactory.create_agent("triage_mock", use_pooling=False)
        self.assertIsInstance(agent, MockTriageAgent)
        self.assertNotIn("triage_mock", _AGENT_POOL) # Should not be pooled if use_pooling is False
        self.assertEqual(agent.name, "triage_mock") # Verify the factory passed the name correctly

        # Test new instance creation when not in pool but pooling enabled
        agent2 = AgentFactory.create_agent("triage_mock", use_pooling=True)
        self.assertIsInstance(agent2, MockTriageAgent)
        self.assertIn("triage_mock", _AGENT_POOL)
        self.assertEqual(_AGENT_POOL["triage_mock"], agent2)
        self.assertEqual(agent2.name, "triage_mock")
        
    def test_create_agent_reuse_from_pool(self):
        """Test reusing an agent from the pool."""
        register_agent("triage_mock", MockTriageAgent)
        
        # Create first agent, it should be added to pool
        agent1 = AgentFactory.create_agent("triage_mock", use_pooling=True, patient_symptoms=["headache"])
        self.assertIn("triage_mock", _AGENT_POOL)
        self.assertEqual(agent1.current_memory["patient_symptoms"], ["headache"])

        # Create second agent, should reuse agent1
        agent2 = AgentFactory.create_agent("triage_mock", use_pooling=True, context={"session_id": "new_session"})
        self.assertIs(agent1, agent2) # Should be the exact same instance
        self.assertEqual(agent2.current_memory["patient_symptoms"], []) # Memory should be reset
        self.assertEqual(agent2.current_memory["session_id"], "new_session") # Context should be updated

    def test_create_agent_with_context(self):
        """Test passing initial context to a newly created agent."""
        register_agent("appointment_mock", MockAppointmentAgent)
        context_data = {"user_id": "test_user", "preference": "morning"}
        agent = AgentFactory.create_agent("appointment_mock", context=context_data, use_pooling=False)
        self.assertEqual(agent.current_memory["user_id"], "test_user")
        self.assertEqual(agent.current_memory["preference"], "morning")

    def test_create_agent_unregistered_name(self):
        """Test that calling create_agent with an unregistered name raises a ValueError."""
        with self.assertRaises(ValueError):
            AgentFactory.create_agent("non_existent_agent")

    def test_release_agent(self):
        """Test that release_agent resets the memory of a pooled agent."""
        register_agent("triage_mock", MockTriageAgent)
        
        # Now that the factory passes the name, agent.name will be 'triage_mock'
        agent = AgentFactory.create_agent("triage_mock", use_pooling=True, patient_symptoms=["fever"])
        
        self.assertEqual(agent.current_memory["patient_symptoms"], ["fever"])
        
        # release_agent checks if agent.name ('triage_mock') is in pool keys
        # The key in pool is also 'triage_mock' from create_agent args.
        AgentFactory.release_agent(agent)
        
        self.assertEqual(agent.current_memory["patient_symptoms"], []) # Memory should be reset

        # Test releasing an agent not in the pool (should not raise error)
        non_pooled_agent = MockAppointmentAgent(name="non_pooled")
        AgentFactory.release_agent(non_pooled_agent) # Should run without error

    def test_cleanup_all_agents(self):
        """Test that cleanup_all_agents clears the agent pool and resets memory."""
        register_agent("triage_mock", MockTriageAgent)
        register_agent("appointment_mock", MockAppointmentAgent)

        agent_triage = AgentFactory.create_agent("triage_mock", use_pooling=True, patient_symptoms=["cold"])
        agent_appointment = AgentFactory.create_agent("appointment_mock", use_pooling=True, booking_slots=["slot_a"])

        self.assertIn("triage_mock", _AGENT_POOL)
        self.assertIn("appointment_mock", _AGENT_POOL)
        self.assertEqual(agent_triage.current_memory["patient_symptoms"], ["cold"])
        self.assertEqual(agent_appointment.current_memory["booking_slots"], ["slot_a"])

        AgentFactory.cleanup_all_agents()

        self.assertEqual(_AGENT_POOL, {}) # Pool should be empty
        self.assertEqual(agent_triage.current_memory["patient_symptoms"], []) # Memory should be reset
        self.assertEqual(agent_appointment.current_memory["booking_slots"], []) # Memory should be reset

if __name__ == '__main__':
    unittest.main()