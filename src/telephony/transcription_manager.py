# src/telephony/transcription_manager.py

from typing import Dict, Any, List
import asyncio
import json
import datetime
import random
from typing import Callable

# Assuming these imports will be available from other modules
# from src.voice.stt.whisper_manager import WhisperManager
# from src.voice.stt.google_speech_v2 import GoogleSpeechV2
# from src.voice.stt.azure_speech import AzureSpeech
# from src.voice.stt.streaming_processor import StreamingProcessor
# from src.telephony.call_event_manager import CallEventManager
# from src.intelligence.pii_scrubber import PIIScrubber
# from src.core.telemetry_emitter import TelemetryEmitter


class TranscriptionManager:
    """
    Manages real-time and post-call transcription services, integrating with
    various Speech-to-Text (STT) providers and handling PII redaction.
    """
    def __init__(self, stt_processor_instance, call_event_manager_instance, pii_scrubber_instance, telemetry_emitter_instance, config: Dict[str, Any]):
        """
        Initializes the TranscriptionManager.
        
        :param stt_processor_instance: An initialized StreamingProcessor instance (or similar STT entry point).
        :param call_event_manager_instance: An initialized CallEventManager instance.
        :param pii_scrubber_instance: An initialized PIIScrubber instance for redaction.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        :param config: Application configuration, including STT settings.
        """
        self.stt_processor = stt_processor_instance
        self.event_manager = call_event_manager_instance
        self.pii_scrubber = pii_scrubber_instance
        self.telemetry = telemetry_emitter_instance
        self.config = config
        
        # Stores active transcription sessions: {session_id: {"transcript_buffer": List[str], "stt_stream_handle": Any, ...}}
        self.active_transcriptions: Dict[str, Dict[str, Any]] = {}
        
        # Whether to redact PII from real-time transcripts before publishing
        self.redact_pii_realtime = config.get("transcription_redact_pii_realtime", True)
        print("✅ TranscriptionManager initialized.")

    async def start_transcription(self, session_id: str, audio_source: Any, user_id: str = None) -> bool:
        """
        Starts a real-time streaming transcription for a given session.
        
        :param session_id: The ID of the call session.
        :param audio_source: An object or callable that provides audio chunks (e.g., from an audio bridge).
        :param user_id: Optional, the ID of the user (for PII scrubbing context).
        :return: True if transcription started successfully, False otherwise.
        """
        if session_id in self.active_transcriptions:
            print(f"Transcription already active for session {session_id}.")
            return True

        print(f"Starting transcription for session {session_id}...")
        
        # In a real system, the `stt_processor` would manage the actual STT API stream.
        # This mock will just create a buffer and simulate incoming audio.
        
        # The STT processor needs a way to push results back to this manager.
        # This mock assumes `stt_processor` has a callback or event mechanism.
        
        self.active_transcriptions[session_id] = {
            "transcript_buffer": [], # Stores final transcripts
            "realtime_buffer": [],   # Stores interim transcripts
            "stt_stream_handle": {"mock_stream": "active"}, # Placeholder for STT stream object
            "start_time": datetime.datetime.now(),
            "audio_source": audio_source, # Store source to read from
            "user_id": user_id
        }
        
        # Start a background task to simulate reading audio and processing STT
        asyncio.create_task(self._simulate_stt_stream(session_id))

        self.telemetry.emit_event("transcription_started", {"session_id": session_id, "user_id": user_id})
        self.event_manager.subscribe(f"audio_received_for_stt_{session_id}", self._handle_incoming_audio_for_stt)
        print(f"✅ Transcription started for session {session_id}.")
        return True

    async def stop_transcription(self, session_id: str):
        """
        Stops the transcription for a given session and finalizes any pending transcripts.
        
        :param session_id: The ID of the call session.
        """
        transcription_info = self.active_transcriptions.pop(session_id, None)
        if transcription_info:
            # Clean up STT stream
            # stt_processor.stop_stream(transcription_info["stt_stream_handle"])
            unsubscribe_handler = getattr(self.event_manager, 'unsubscribe', None)
            if callable(unsubscribe_handler):
                unsubscribe_handler(f"audio_received_for_stt_{session_id}", self._handle_incoming_audio_for_stt) # Mock unsubscribe
            
            duration = (datetime.datetime.now() - transcription_info["start_time"]).total_seconds()
            
            final_transcript = " ".join(transcription_info["transcript_buffer"])
            
            self.telemetry.emit_event("transcription_stopped", {"session_id": session_id, "duration": duration, "final_transcript_len": len(final_transcript)})
            await self.event_manager.publish("final_transcript_ready", {"session_id": session_id, "transcript": final_transcript})
            
            print(f"🛑 Transcription stopped for session {session_id}. Final transcript length: {len(final_transcript)}.")
        else:
            print(f"No active transcription found for session {session_id}.")

    async def _handle_incoming_audio_for_stt(self, event_data: Dict[str, Any]):
        """
        Internal handler for audio chunks arriving for STT processing.
        """
        session_id = event_data["session_id"]
        audio_chunk = event_data["audio_chunk"]
        
        if session_id not in self.active_transcriptions:
            return

        # Simulate STT processing of the chunk by decoding the bytes.
        # This makes the mock flexible for testing.
        mock_text = audio_chunk.decode('utf-8', errors='ignore')
            
        if mock_text:
            interim_transcript = f"Interim: {mock_text}"
            final_transcript = mock_text # This would be an actual final segment from STT

            # Redact PII from transcripts
            if self.redact_pii_realtime:
                interim_transcript = self.pii_scrubber.scrub_text(interim_transcript, user_id=self.active_transcriptions[session_id]["user_id"])
                final_transcript = self.pii_scrubber.scrub_text(final_transcript, user_id=self.active_transcriptions[session_id]["user_id"])
            
            self.active_transcriptions[session_id]["realtime_buffer"].append(interim_transcript)
            self.active_transcriptions[session_id]["transcript_buffer"].append(final_transcript)
            
            await self.event_manager.publish("interim_transcript_ready", {"session_id": session_id, "transcript_chunk": interim_transcript})
            await self.event_manager.publish("final_transcript_chunk_ready", {"session_id": session_id, "transcript_chunk": final_transcript})
            self.telemetry.emit_event("transcription_chunk", {"session_id": session_id, "type": "final", "chunk_len": len(final_transcript)})

    async def _simulate_stt_stream(self, session_id: str):
        """Simulates continuous audio input and STT processing."""
        audio_feed_mock = ["hello", "how are you", "I feel sick", "thank you", "goodbye"]
        for phrase in audio_feed_mock:
            await asyncio.sleep(random.uniform(0.5, 1.5)) # Simulate user speaking
            if session_id not in self.active_transcriptions:
                break
            
            print(f"  [Simulated Audio] User said: '{phrase}'")
            # Publish mock audio chunk. In real life, audio mixer would feed directly.
            await self.event_manager.publish(f"audio_received_for_stt_{session_id}", {"session_id": session_id, "audio_chunk": phrase.encode('utf-8')})
        
        if session_id in self.active_transcriptions:
            await self.stop_transcription(session_id)


    async def get_transcripts(self, session_id: str, real_time: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves the accumulated transcripts for a session.
        
        :param session_id: The ID of the call session.
        :param real_time: If True, returns interim transcripts; otherwise, returns final transcripts.
        :return: A list of transcript chunks.
        """
        transcription_info = self.active_transcriptions.get(session_id)
        if transcription_info:
            buffer_to_return = transcription_info["realtime_buffer"] if real_time else transcription_info["transcript_buffer"]
            # Return as a list of dicts to align with common transcript formats
            return [{"timestamp": datetime.datetime.now().isoformat(), "text": text_chunk, "type": "interim" if real_time else "final"} for text_chunk in buffer_to_return]
        return []

    def unsubscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], Any]):
        """
        Unsubscribes a handler from a specific event type.
        (Added for completeness in mock_call_event_manager)
        """
        if event_type in self.event_manager._handlers: # Accessing protected member for mock
            self.event_manager._handlers[event_type] = [h for h in self.event_manager._handlers[event_type] if h != handler]

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockSTTProcessor:
        pass # The logic is simulated within TranscriptionManager for this example

    class MockCallEventManager:
        def __init__(self):
            self._handlers = {}
        async def publish(self, event_type: str, event_data: Dict[str, Any]):
            print(f"Mock EventManager: Publishing '{event_type}'")
            # Manually call handler for this mock
            if event_type in self._handlers:
                for handler in self._handlers[event_type]:
                    await handler(event_data)
        def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], Any]):
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
        def unsubscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], Any]):
            if event_type in self._handlers:
                self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]


    class MockPIIScrubber:
        def scrub_text(self, text: str, user_id: str = None) -> str:
            return text.replace("my email is sensitive@pii.com", "[REDACTED_EMAIL]")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_stt_proc = MockSTTProcessor()
    mock_cem = MockCallEventManager()
    mock_pii = MockPIIScrubber()
    mock_te = MockTelemetryEmitter()
    mock_config = {"transcription_redact_pii_realtime": True}
    
    transcription_manager = TranscriptionManager(mock_stt_proc, mock_cem, mock_pii, mock_te, mock_config)

    session_id_1 = "s_trans_1"
    user_id_1 = "user_trans_1"

    # --- Test 1: Start transcription and observe simulated output ---
    print("\n--- Test 1: Start transcription ---")
    async def run_transcription_test():
        start_success = await transcription_manager.start_transcription(session_id_1, audio_source="mock_audio_stream", user_id=user_id_1)
        if start_success:
            print(f"Transcription for {session_id_1} is running. Waiting for simulated audio...")
            await asyncio.sleep(7) # Give time for simulation to run
            await transcription_manager.stop_transcription(session_id_1)
            
            print("\n--- Retrieved Transcripts ---")
            final_transcripts = await transcription_manager.get_transcripts(session_id_1, real_time=False)
            print(f"Final Transcripts: {final_transcripts}")
            
            interim_transcripts = await transcription_manager.get_transcripts(session_id_1, real_time=True)
            print(f"Interim Transcripts: {interim_transcripts}")
        else:
            print("Failed to start transcription.")

    asyncio.run(run_transcription_test())

    # --- Test 2: Test PII Redaction ---
    print("\n--- Test 2: PII Redaction ---")
    session_id_2 = "s_trans_2_pii"
    user_id_2 = "user_trans_2_pii"

    async def run_pii_test():
        start_success = await transcription_manager.start_transcription(session_id_2, audio_source="mock_audio_stream_pii", user_id=user_id_2)
        if start_success:
            # Simulate audio with PII
            await asyncio.sleep(1)
            await mock_cem.publish(f"audio_received_for_stt_{session_id_2}", {"session_id": session_id_2, "audio_chunk": b"Hello, my email is sensitive@pii.com."})
            await asyncio.sleep(1)
            await transcription_manager.stop_transcription(session_id_2)
            
            pii_transcripts = await transcription_manager.get_transcripts(session_id_2)
            print(f"\nPII Redacted Transcripts: {pii_transcripts}")

    asyncio.run(run_pii_test())
    
    print("\nTranscriptionManager simulation complete.")
