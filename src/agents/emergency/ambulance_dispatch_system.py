import logging
import json
import datetime
from typing import Dict, Any, Optional
import asyncio

# Assuming CallSessionManager to keep track of the call
from src.voice.telephony.call_session_manager import CallSessionManager

logger = logging.getLogger(__name__)

class AmbulanceDispatchSystem:
    """
    Manages the critical task of dispatching an ambulance or connecting to
    emergency services based on an identified emergency. It routes calls
    to the correct regional emergency number and compiles essential data
    for the dispatcher.
    """
    def __init__(self, call_session_manager: CallSessionManager, emergency_call_router: Any = None):
        self.call_session_manager = call_session_manager
        self.emergency_call_router = emergency_call_router # For making the actual call
        
        # Regional emergency numbers
        self.regional_emergency_numbers: Dict[str, str] = {
            "US": "911",
            "IN": "108", # India Ambulance
            "GB": "999",
            "AU": "000",
            "DEFAULT": "112" # International standard
        }
        logger.info("AmbulanceDispatchSystem initialized.")

    async def dispatch_ambulance(
        self, 
        call_id: str,
        patient_info: Dict[str, Any],
        emergency_details: Dict[str, Any],
        country_code: str,
        caller_location: Dict[str, Any],
        silent_dial: bool = False
    ) -> Dict[str, Any]:
        """
        Initiates the process to dispatch an ambulance or connect to emergency services.

        Args:
            call_id (str): The ID of the current active call session.
            patient_info (Dict[str, Any]): Dictionary with patient's name, age, known allergies, etc.
            emergency_details (Dict[str, Any]): Details of the emergency (e.g., condition, symptoms).
            country_code (str): ISO 3166-1 alpha-2 country code (e.g., "US", "IN").
            caller_location (Dict[str, Any]): Geographic location of the caller (lat, lon, address).
            silent_dial (bool): If true, do not announce the call to the user immediately.
                                Useful for abusive situations or mental health crises.

        Returns:
            Dict[str, Any]: Status of the dispatch attempt.
        """
        session = self.call_session_manager.get_session(call_id)
        if not session:
            logger.error(f"Cannot dispatch ambulance: Call session {call_id} not found.")
            return {"status": "failed", "reason": "Call session not found."}

        # 1. Determine the correct emergency number
        emergency_number = self.regional_emergency_numbers.get(country_code.upper(), self.regional_emergency_numbers["DEFAULT"])
        
        # 2. Compile the data packet for the dispatcher
        dispatcher_data = self._compile_dispatcher_data(
            call_id, patient_info, emergency_details, country_code, caller_location
        )

        logger.critical(f"Attempting to dispatch emergency services for Call ID: {call_id} to {emergency_number}")
        logger.debug(f"Dispatcher data: {json.dumps(dispatcher_data, indent=2)}")

        # 3. Initiate the call to emergency services (via EmergencyCallRouter or directly)
        if self.emergency_call_router:
            # The emergency_call_router is designed to escalate calls
            # This is a conceptual call to an external service or a function that uses SIP/Twilio
            # The router would handle the actual dialing and staying on line.
            await self.emergency_call_router._dial_emergency_services(session, emergency_number, dispatcher_data)
        else:
            logger.warning("EmergencyCallRouter not provided. Cannot make actual call to emergency services.")
            # Mocking the call action
            if not silent_dial:
                response_message = (
                    f"Connecting you to emergency services at {emergency_number}. "
                    f"Please stay on the line. I have sent your details: {json.dumps(dispatcher_data)}."
                )
            else:
                response_message = "Initiating silent emergency dispatch. Please stay on the line."
            return {"status": "mock_call_initiated", "number_dialed": emergency_number, "message": response_message}

        session.metadata["emergency_dispatched"] = True
        session.metadata["emergency_number_dialed"] = emergency_number
        session.metadata["dispatcher_data_sent"] = dispatcher_data
        session.metadata["silent_dial_active"] = silent_dial

        return {"status": "dispatch_initiated", "number_dialed": emergency_number, "data_sent": dispatcher_data}

    def _compile_dispatcher_data(
        self, 
        call_id: str,
        patient_info: Dict[str, Any],
        emergency_details: Dict[str, Any],
        country_code: str,
        caller_location: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compiles relevant patient and emergency information into a structured data packet
        for the emergency dispatcher.
        """
        # FIX: Added import datetime at the top of the file to support this line
        data_packet = {
            "timestamp": datetime.datetime.now().isoformat(),
            "call_id": call_id,
            "patient": {
                "name": patient_info.get("name", "Unknown"),
                "age": patient_info.get("age", "Unknown"),
                "gender": patient_info.get("gender", "Unknown"),
                "phone": patient_info.get("phone", "Unknown"),
                "allergies": patient_info.get("allergies", "None reported"),
                "medical_history": patient_info.get("medical_history", "None reported")
            },
            "emergency": {
                "condition": emergency_details.get("condition", "Unspecified"),
                "symptoms": emergency_details.get("symptoms", []),
                "severity": emergency_details.get("severity", "Unknown"),
                "onset_time": emergency_details.get("onset_time", "Unknown"),
                "latest_user_utterance": emergency_details.get("latest_user_utterance", "")
            },
            "location": caller_location,
            "country_code": country_code,
            "legal_compliance": "Follows emergency services regulations.",
            "instructions_for_operator": "AI is staying on the line to assist with information relay."
        }
        return data_packet

    async def stay_on_line(self, call_id: str):
        """
        (Conceptual) Ensures the AI maintains the connection with the caller
        until emergency services arrive or explicitly disconnected.
        """
        session = self.call_session_manager.get_session(call_id)
        if session:
            session.metadata["stay_on_line_active"] = True
            logger.info(f"AI instructed to stay on line for call {call_id}.")
            # This would typically involve signaling the SIP/WebRTC client
            # to maintain the connection and possibly play calming messages.
        else:
            logger.warning(f"Cannot 'stay on line': Call session {call_id} not found.")

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock dependencies
    class MockCallSessionManager:
        def __init__(self):
            self.sessions = {}
        def get_session(self, call_id: str):
            if call_id not in self.sessions:
                self.sessions[call_id] = type('obj', (object,), {
                    "call_id": call_id,
                    "metadata": {},
                    "caller_id": "+15551234567"
                })()
            return self.sessions[call_id]

    class MockEmergencyCallRouter:
        async def _dial_emergency_services(self, session, dial_number, dispatcher_data):
            logger.info(f"MOCK: EmergencyCallRouter dialing {dial_number} for session {session.call_id}.")
            session.metadata["router_dialed"] = True


    session_manager_mock = MockCallSessionManager()
    emergency_router_mock = MockEmergencyCallRouter()
    
    dispatch_system = AmbulanceDispatchSystem(
        call_session_manager=session_manager_mock,
        emergency_call_router=emergency_router_mock
    )

    async def run_dispatch_flow():
        call_id = "emergency_call_001"
        patient_info = {
            "name": "Jane Doe", "age": 65, "gender": "Female",
            "allergies": "Penicillin", "medical_history": "Hypertension, Diabetes"
        }
        emergency_details = {
            "condition": "Suspected Heart Attack",
            "symptoms": ["crushing chest pain", "shortness of breath", "left arm pain"],
            "severity": "critical",
            "onset_time": "15 minutes ago",
            "latest_user_utterance": "My chest hurts so bad, I can't breathe!"
        }
        caller_location = {"lat": 34.0522, "lon": -118.2437, "address": "123 Main St, Anytown, CA", "source": "GPS"}
        country_code = "US"

        print("\n--- Flow 1: Dispatch Ambulance (US) ---")
        dispatch_status = await dispatch_system.dispatch_ambulance(
            call_id, patient_info, emergency_details, country_code, caller_location
        )
        print(f"Dispatch Status: {dispatch_status}")
        session = session_manager_mock.get_session(call_id)
        assert session.metadata.get("emergency_dispatched") == True
        assert session.metadata.get("emergency_number_dialed") == "911"
        
        await dispatch_system.stay_on_line(call_id)
        assert session.metadata.get("stay_on_line_active") == True

        print("\n--- Flow 2: Dispatch Ambulance (India) ---")
        call_id_in = "emergency_call_002"
        context_in = {"call_id": call_id_in, "country_code": "IN", "caller_location": {"lat": 28.6139, "lon": 77.2090}}
        dispatch_status_in = await dispatch_system.dispatch_ambulance(
            call_id_in, patient_info, emergency_details, "IN", context_in["caller_location"]
        )
        print(f"Dispatch Status (India): {dispatch_status_in}")
        session_in = session_manager_mock.get_session(call_id_in)
        assert session_in.metadata.get("emergency_number_dialed") == "108"

        print("\n--- Flow 3: Silent Dial (Conceptual) ---")
        call_id_silent = "emergency_call_003"
        dispatch_status_silent = await dispatch_system.dispatch_ambulance(
            call_id_silent, patient_info, emergency_details, "US", caller_location, silent_dial=True
        )
        print(f"Dispatch Status (Silent): {dispatch_status_silent}")
        session_silent = session_manager_mock.get_session(call_id_silent)
        assert session_silent.metadata.get("silent_dial_active") == True


    import asyncio
    asyncio.run(run_dispatch_flow())