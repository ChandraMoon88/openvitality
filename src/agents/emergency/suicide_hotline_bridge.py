import logging
import json
from typing import Dict, Any, Optional
import asyncio

# Assuming CallSessionManager to keep track of the call
from src.voice.telephony.call_session_manager import CallSessionManager

logger = logging.getLogger(__name__)

class SuicideHotlineBridge:
    """
    Manages mental health crisis intervention by connecting users experiencing
    suicidal ideation or severe distress to appropriate crisis hotlines.
    It focuses on a 'warm transfer' and ensuring the user is never left alone.
    """
    def __init__(self, call_session_manager: CallSessionManager, telephony_connector: Any = None):
        self.call_session_manager = call_session_manager
        self.telephony_connector = telephony_connector # e.g., SIP_Trunk_Handler or Twilio_Connector for transfers
        
        # Regional suicide hotline numbers
        self.regional_hotline_numbers: Dict[str, str] = {
            "US": "988", # Suicide & Crisis Lifeline
            "IN": "9152987821", # AASRA
            "GB": "116123", # Samaritans
            "DEFAULT": "Contact your local emergency services." # Fallback text
        }
        # Calming audio file path (conceptual)
        self.calming_audio_path = "assets/audio/calming_music.mp3" 
        logger.info("SuicideHotlineBridge initialized.")

    async def escalate_to_hotline(self,
                                  call_id: str,
                                  country_code: str,
                                  user_utterance: str,
                                  silent_transfer: bool = False) -> Dict[str, Any]:
        """
        Initiates a warm transfer to a regional suicide prevention hotline.

        Args:
            call_id (str): The ID of the current active call session.
            country_code (str): ISO 3166-1 alpha-2 country code (e.g., "US", "IN").
            user_utterance (str): The user's statement that triggered the escalation.
            silent_transfer (bool): If true, AI won't verbally announce connecting to hotline.

        Returns:
            Dict[str, Any]: Status of the transfer attempt.
        """
        session = self.call_session_manager.get_session(call_id)
        if not session:
            logger.error(f"Cannot escalate to hotline: Call session {call_id} not found.")
            return {"status": "failed", "reason": "Call session not found."}

        # 1. Determine the correct hotline number
        hotline_number = self.regional_hotline_numbers.get(country_code.upper(), self.regional_hotline_numbers["DEFAULT"])
        
        logger.critical(f"Mental health crisis detected for Call ID: {call_id}. Attempting to connect to hotline: {hotline_number}")
        logger.debug(f"User utterance: '{user_utterance}'")

        # Update session metadata
        session.metadata["suicide_hotline_escalation_active"] = True
        session.metadata["hotline_number_attempted"] = hotline_number
        session.metadata["initial_crisis_utterance"] = user_utterance
        
        transfer_message = (
            f"I hear you, and I want you to know you're not alone. "
            f"Your safety and well-being are incredibly important. "
            f"I am now connecting you directly to a crisis hotline where "
            f"trained professionals can provide immediate support. "
            f"Please stay on the line. The number is {hotline_number}."
        )
        
        if silent_transfer:
            transfer_message = "I am now connecting you to specialized support. Please stay on the line."

        # 2. Perform a "warm transfer" (conceptual)
        if self.telephony_connector:
            try:
                # Assuming telephony_connector has a method like transfer_call_to_number
                # This would typically involve playing the transfer message first, then initiating the transfer.
                await self.telephony_connector.play_audio_and_transfer(call_id, transfer_message, hotline_number, calming_audio=self.calming_audio_path)
                logger.info(f"Played transfer message and attempting warm transfer to {hotline_number} for call {call_id}.")
                # For a mock, we just update status
                session.metadata["transfer_status"] = "initiated"
                
                # If the transfer mechanism supports keeping AI on line as backup, enable it
                await self.stay_engaged_if_hotline_busy(call_id, hotline_number)
                
                return {"status": "transfer_initiated", "hotline": hotline_number, "message": transfer_message}

            except Exception as e:
                logger.error(f"Failed to initiate warm transfer for call {call_id}: {e}")
                session.metadata["transfer_status"] = "failed"
                # Fallback: AI stays engaged
                await self.stay_engaged_if_hotline_busy(call_id, hotline_number, transfer_failed=True)
                return {"status": "transfer_failed", "hotline": hotline_number, "message": "I was unable to connect you to the hotline directly, but I'm still here with you. Please hold while I try again, or consider calling them directly."}
        else:
            logger.warning("Telephony connector not provided. Cannot make actual call to hotline.")
            # Fallback: AI stays engaged and provides the number
            await self.stay_engaged_if_hotline_busy(call_id, hotline_number, telephony_unavailable=True)
            return {"status": "no_telephony_connector", "hotline": hotline_number, "message": transfer_message + " I am still here to talk if you need me, or you can try calling the number directly."}

    async def stay_engaged_if_hotline_busy(self, call_id: str, hotline_number: str, transfer_failed: bool = False, telephony_unavailable: bool = False):
        """
        Ensures the AI stays engaged if the hotline is busy or the transfer fails.
        Provides a script and, conceptually, calming audio.
        """
        session = self.call_session_manager.get_session(call_id)
        if session:
            session.metadata["ai_engaged_as_fallback"] = True
            if transfer_failed:
                logger.warning(f"Hotline transfer failed for call {call_id}. AI engaging as fallback.")
            elif telephony_unavailable:
                logger.warning(f"Telephony connector unavailable for call {call_id}. AI engaging as fallback.")
            else:
                logger.info(f"Hotline busy for call {call_id}. AI engaging as fallback, playing calming audio.")
            
            # Script: "I'm staying right here with you"
            # Conceptual: Play calming audio in background if possible
            # await self.telephony_connector.play_audio_in_background(call_id, self.calming_audio_path)
            
            response_text = (
                "I'm staying right here with you. It's okay. "
                "I will keep trying to connect you, or you can try calling the hotline directly at: "
                f"{hotline_number}. We can talk until then."
            )
            # This response would be spoken to the user by the main dialogue manager
            session.metadata["ai_fallback_message"] = response_text
        else:
            logger.warning(f"Cannot engage AI fallback: Call session {call_id} not found.")


    def never_hang_up(self, call_id: str):
        """
        (Conceptual) Ensures the AI never hangs up on a user in crisis.
        This would be implemented by the core telephony module checking a flag in the session.
        """
        session = self.call_session_manager.get_session(call_id)
        if session:
            session.metadata["do_not_hang_up"] = True
            logger.critical(f"DO NOT HANG UP on call {call_id}. User in mental health crisis.")
        else:
            logger.warning(f"Cannot set 'do_not_hang_up' flag: Call session {call_id} not found.")

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

    class MockTelephonyConnector:
        async def play_audio_and_transfer(self, call_id: str, message: str, number: str, calming_audio: str = None):
            logger.info(f"MOCK: Playing message: '{message}' then transferring call {call_id} to {number}.")
            if calming_audio: logger.info(f"MOCK: Playing calming audio from {calming_audio}.")
            # Simulate transfer success/failure
            if "busy" in number: # Simulate busy hotline
                raise Exception("Hotline busy")
        
        async def play_audio_in_background(self, call_id: str, audio_path: str):
            logger.info(f"MOCK: Playing background audio {audio_path} for call {call_id}.")

    session_manager_mock = MockCallSessionManager()
    telephony_connector_mock = MockTelephonyConnector()
    
    hotline_bridge = SuicideHotlineBridge(
        call_session_manager=session_manager_mock,
        telephony_connector=telephony_connector_mock
    )

    async def run_hotline_flow():
        call_id_us = "hotline_call_US"
        call_id_in = "hotline_call_IN"
        call_id_failed = "hotline_call_failed"
        user_crisis_text = "I feel like giving up, I can't take this anymore."

        print("\n--- Flow 1: US Hotline Transfer ---")
        transfer_status_us = await hotline_bridge.escalate_to_hotline(
            call_id_us, "US", user_crisis_text
        )
        print(f"Transfer Status (US): {transfer_status_us}")
        session_us = session_manager_mock.get_session(call_id_us)
        assert session_us.metadata.get("suicide_hotline_escalation_active") == True
        assert session_us.metadata.get("hotline_number_attempted") == "988"
        hotline_bridge.never_hang_up(call_id_us)
        assert session_us.metadata.get("do_not_hang_up") == True

        print("\n--- Flow 2: India Hotline Transfer ---")
        transfer_status_in = await hotline_bridge.escalate_to_hotline(
            call_id_in, "IN", user_crisis_text
        )
        print(f"Transfer Status (IN): {transfer_status_in}")
        session_in = session_manager_mock.get_session(call_id_in)
        assert session_in.metadata.get("hotline_number_attempted") == "9152987821"

        print("\n--- Flow 3: Failed Transfer (AI Fallback) ---")
        # Temporarily change a hotline number to simulate busy
        old_us_hotline = hotline_bridge.regional_hotline_numbers["US"]
        hotline_bridge.regional_hotline_numbers["US"] = "busy" # Simulate a busy number
        transfer_status_failed = await hotline_bridge.escalate_to_hotline(
            call_id_failed, "US", user_crisis_text
        )
        hotline_bridge.regional_hotline_numbers["US"] = old_us_hotline # Restore
        print(f"Transfer Status (Failed): {transfer_status_failed}")
        session_failed = session_manager_mock.get_session(call_id_failed)
        assert session_failed.metadata.get("ai_engaged_as_fallback") == True
        assert "I was unable to connect you" in transfer_status_failed["message"]

    import asyncio
    asyncio.run(run_hotline_flow())