import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import json
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.emergency.ambulance_dispatch_system import AmbulanceDispatchSystem
from src.voice.telephony.call_session_manager import CallSessionManager # Import the actual class

# Mock Session object
class MockSession:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.metadata = {}
        self.caller_id = "+15551234567"

class TestAmbulanceDispatchSystem(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh system with mocked dependencies for each test."""
        self.mock_call_session_manager = AsyncMock(spec=CallSessionManager)
        self.mock_emergency_call_router = AsyncMock() # Mock the router
        
        self.dispatch_system = AmbulanceDispatchSystem(
            call_session_manager=self.mock_call_session_manager,
            emergency_call_router=self.mock_emergency_call_router
        )

        # Common test data
        self.call_id = "test_call_123"
        self.patient_info = {"name": "John Doe", "age": 45, "allergies": "None"}
        self.emergency_details = {"condition": "chest pain", "symptoms": ["pain", "sweating"]}
        self.caller_location = {"lat": 1.0, "lon": 1.0, "address": "123 Test St"}

        # Configure mock session manager
        self.mock_session = MockSession(self.call_id)
        self.mock_call_session_manager.get_session.return_value = self.mock_session

    def test_initialization(self):
        """Test correct initialization of properties."""
        self.assertIsInstance(self.dispatch_system.call_session_manager, AsyncMock)
        self.assertIsInstance(self.dispatch_system.emergency_call_router, AsyncMock)
        self.assertIn("US", self.dispatch_system.regional_emergency_numbers)
        self.assertEqual(self.dispatch_system.regional_emergency_numbers["US"], "911")

    async def test_dispatch_ambulance_success_us(self):
        """Test successful dispatch for US country code."""
        result = await self.dispatch_system.dispatch_ambulance(
            self.call_id, self.patient_info, self.emergency_details, "US", self.caller_location
        )

        self.assertEqual(result["status"], "dispatch_initiated")
        self.assertEqual(result["number_dialed"], "911")
        self.mock_emergency_call_router._dial_emergency_services.assert_called_once()
        self.assertEqual(self.mock_session.metadata["emergency_number_dialed"], "911")
        self.assertTrue(self.mock_session.metadata["emergency_dispatched"])

    async def test_dispatch_ambulance_success_in(self):
        """Test successful dispatch for IN country code."""
        result = await self.dispatch_system.dispatch_ambulance(
            self.call_id, self.patient_info, self.emergency_details, "IN", self.caller_location
        )

        self.assertEqual(result["status"], "dispatch_initiated")
        self.assertEqual(result["number_dialed"], "108")
        self.mock_emergency_call_router._dial_emergency_services.assert_called_once()
        self.assertEqual(self.mock_session.metadata["emergency_number_dialed"], "108")

    async def test_dispatch_ambulance_success_default(self):
        """Test successful dispatch for an unknown country code (should use default)."""
        result = await self.dispatch_system.dispatch_ambulance(
            self.call_id, self.patient_info, self.emergency_details, "XX", self.caller_location
        )

        self.assertEqual(result["status"], "dispatch_initiated")
        self.assertEqual(result["number_dialed"], "112")
        self.mock_emergency_call_router._dial_emergency_services.assert_called_once()
        self.assertEqual(self.mock_session.metadata["emergency_number_dialed"], "112")

    async def test_dispatch_ambulance_no_router_mock_call(self):
        """Test mock call initiation when emergency_call_router is not provided."""
        dispatch_system_no_router = AmbulanceDispatchSystem(
            call_session_manager=self.mock_call_session_manager,
            emergency_call_router=None # No router provided
        )
        result = await dispatch_system_no_router.dispatch_ambulance(
            self.call_id, self.patient_info, self.emergency_details, "US", self.caller_location
        )
        self.assertEqual(result["status"], "mock_call_initiated")
        self.assertIn("Connecting you to emergency services at 911", result["message"])
        self.assertNotIn("emergency_dispatched", self.mock_session.metadata) # Metadata not updated by mock call action

    async def test_dispatch_ambulance_no_router_silent_dial(self):
        """Test mock silent dial when emergency_call_router is not provided."""
        dispatch_system_no_router = AmbulanceDispatchSystem(
            call_session_manager=self.mock_call_session_manager,
            emergency_call_router=None # No router provided
        )
        result = await dispatch_system_no_router.dispatch_ambulance(
            self.call_id, self.patient_info, self.emergency_details, "US", self.caller_location, silent_dial=True
        )
        self.assertEqual(result["status"], "mock_call_initiated")
        self.assertIn("Initiating silent emergency dispatch", result["message"])
        self.assertNotIn("emergency_dispatched", self.mock_session.metadata)

    async def test_dispatch_ambulance_session_not_found(self):
        """Test error handling when call session is not found."""
        self.mock_call_session_manager.get_session.return_value = None # Simulate session not found
        result = await self.dispatch_system.dispatch_ambulance(
            "non_existent_call", self.patient_info, self.emergency_details, "US", self.caller_location
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("Call session not found", result["reason"])
        self.mock_emergency_call_router._dial_emergency_services.assert_not_called()

    def test_compile_dispatcher_data(self):
        """Test that _compile_dispatcher_data correctly structures data."""
        data = self.dispatch_system._compile_dispatcher_data(
            self.call_id, self.patient_info, self.emergency_details, "US", self.caller_location
        )
        self.assertIn("timestamp", data)
        self.assertEqual(data["call_id"], self.call_id)
        self.assertEqual(data["patient"]["name"], self.patient_info["name"])
        self.assertEqual(data["emergency"]["condition"], self.emergency_details["condition"])
        self.assertEqual(data["location"], self.caller_location)
        self.assertEqual(data["country_code"], "US")
        self.assertIn("instructions_for_operator", data)

        # Test default values for missing info
        patient_info_partial = {"name": "Jane"}
        emergency_details_partial = {"symptoms": ["headache"]}
        data_partial = self.dispatch_system._compile_dispatcher_data(
            "partial_call", patient_info_partial, emergency_details_partial, "US", {}
        )
        self.assertEqual(data_partial["patient"]["age"], "Unknown")
        self.assertEqual(data_partial["emergency"]["condition"], "Unspecified")
        self.assertEqual(data_partial["location"], {})

    async def test_stay_on_line_success(self):
        """Test stay_on_line sets metadata for an existing session."""
        await self.dispatch_system.stay_on_line(self.call_id)
        self.assertTrue(self.mock_session.metadata["stay_on_line_active"])

    async def test_stay_on_line_session_not_found(self):
        """Test stay_on_line handles non-existent sessions gracefully."""
        self.mock_call_session_manager.get_session.return_value = None
        # Should not raise an error, just log a warning
        await self.dispatch_system.stay_on_line("non_existent_call")
        # Assert no exceptions were raised
        self.mock_call_session_manager.get_session.assert_called_once_with("non_existent_call")


if __name__ == '__main__':
    unittest.main()