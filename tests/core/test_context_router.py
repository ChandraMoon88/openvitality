import sys
import os
import unittest
from unittest.mock import Mock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.context_router import ContextRouter

class TestContextRouter(unittest.TestCase):

    def setUp(self):
        """Set up mock agents and the router for each test."""
        self.mock_emergency_agent = Mock()
        self.mock_emergency_agent.is_available.return_value = True
        self.mock_symptom_agent = Mock()
        self.mock_symptom_agent.is_available.return_value = True
        self.mock_appointment_agent = Mock()
        self.mock_appointment_agent.is_available.return_value = True
        self.mock_general_agent = Mock()
        self.mock_general_agent.is_available.return_value = True

        self.agent_registry = {
            "medical_emergency": self.mock_emergency_agent,
            "symptom_report": self.mock_symptom_agent,
            "appointment_booking": self.mock_appointment_agent,
            "general_question": self.mock_general_agent,
        }

        self.router = ContextRouter(self.agent_registry)

    def test_emergency_routing_override(self):
        """Test that 'medical_emergency' intent always routes to the emergency agent."""
        session = {
            "session_id": "123",
            "context": {"current_agent": "symptom_report", "last_intent": "symptom_report"}
        }
        intent = "medical_emergency"
        confidence = 1.0

        selected_agent = self.router.get_agent(session, intent, confidence)
        self.assertEqual(selected_agent, self.mock_emergency_agent)

    def test_sticky_routing(self):
        """Test that the router stays with the current agent if the intent is unchanged."""
        session = {
            "session_id": "456",
            "context": {"current_agent": "symptom_report", "last_intent": "symptom_report"}
        }
        intent = "symptom_report" # Same intent
        confidence = 0.9

        selected_agent = self.router.get_agent(session, intent, confidence)
        self.assertEqual(selected_agent, self.mock_symptom_agent)

    def test_sticky_routing_breaks_on_intent_change(self):
        """Test that sticky routing is broken when the intent changes."""
        session = {
            "session_id": "789",
            "context": {"current_agent": "symptom_report", "last_intent": "symptom_report"}
        }
        intent = "appointment_booking" # Different intent
        confidence = 0.95

        selected_agent = self.router.get_agent(session, intent, confidence)
        self.assertEqual(selected_agent, self.mock_appointment_agent)
        self.assertNotEqual(selected_agent, self.mock_symptom_agent)

    def test_intent_based_routing(self):
        """Test standard routing to a new agent based on high-confidence intent."""
        session = {
            "session_id": "abc",
            "context": {} # No current agent
        }
        intent = "appointment_booking"
        confidence = 0.85

        selected_agent = self.router.get_agent(session, intent, confidence)
        self.assertEqual(selected_agent, self.mock_appointment_agent)

    def test_fallback_routing_on_low_confidence(self):
        """Test that the router uses the fallback agent for low-confidence intents."""
        session = {
            "session_id": "def",
            "context": {}
        }
        intent = "symptom_report"
        confidence = 0.5 # Below the 0.7 threshold

        selected_agent = self.router.get_agent(session, intent, confidence)
        self.assertEqual(selected_agent, self.mock_general_agent)

    def test_fallback_routing_on_unknown_intent(self):
        """Test that the router uses the fallback agent for unregistered intents."""
        session = {
            "session_id": "ghi",
            "context": {}
        }
        intent = "unknown_intent"
        confidence = 0.9

        selected_agent = self.router.get_agent(session, intent, confidence)
        self.assertEqual(selected_agent, self.mock_general_agent)

    def test_agent_unavailability(self):
        """Test that the router falls back if the intended agent is unavailable."""
        self.mock_appointment_agent.is_available.return_value = False
        session = {
            "session_id": "jkl",
            "context": {}
        }
        intent = "appointment_booking"
        confidence = 0.95

        selected_agent = self.router.get_agent(session, intent, confidence)
        self.assertEqual(selected_agent, self.mock_general_agent)


if __name__ == '__main__':
    unittest.main()
