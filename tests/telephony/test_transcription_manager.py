import sys
sys.path.append('.')

import unittest
import asyncio
from typing import Dict, Any, Callable

from src.telephony.transcription_manager import TranscriptionManager

# --- Mock Dependencies ---
class MockSTTProcessor:
    pass

class MockCallEventManager:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    async def publish(self, event_type: str, event_data: Dict[str, Any]):
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                await handler(event_data)

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

class MockPIIScrubber:
    def scrub_text(self, text: str, user_id: str = None) -> str:
        return text.replace("sensitive@pii.com", "[REDACTED_EMAIL]")

class MockTelemetryEmitter:
    def __init__(self):
        self.events = []
    def emit_event(self, event_name: str, data: Dict):
        self.events.append({"name": event_name, "data": data})

class TestTranscriptionManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_stt_proc = MockSTTProcessor()
        self.mock_cem = MockCallEventManager()
        self.mock_pii = MockPIIScrubber()
        self.mock_te = MockTelemetryEmitter()
        self.mock_config = {"transcription_redact_pii_realtime": True}
        
        self.manager = TranscriptionManager(self.mock_stt_proc, self.mock_cem, self.mock_pii, self.mock_te, self.mock_config)

    async def test_start_and_stop_transcription(self):
        session_id = "s1"
        self.assertNotIn(session_id, self.manager.active_transcriptions)
        
        # We need to cancel the background task created by start_transcription
        original_create_task = asyncio.create_task
        task = None
        def mock_create_task(coro):
            nonlocal task
            task = original_create_task(coro)
            return task
        
        asyncio.create_task = mock_create_task

        await self.manager.start_transcription(session_id, "mock_source")
        self.assertIn(session_id, self.manager.active_transcriptions)
        
        await self.manager.stop_transcription(session_id)
        self.assertNotIn(session_id, self.manager.active_transcriptions)
        
        # cleanup
        if task:
            task.cancel()
        asyncio.create_task = original_create_task


    async def test_audio_handling_and_transcript_generation(self):
        session_id = "s2"
        await self.manager.start_transcription(session_id, "mock_source")
        
        # Manually publish an audio event
        audio_chunk = b"hello world"
        await self.mock_cem.publish(f"audio_received_for_stt_{session_id}", {"session_id": session_id, "audio_chunk": audio_chunk})
        
        transcripts = await self.manager.get_transcripts(session_id, real_time=False)
        self.assertEqual(len(transcripts), 1)
        self.assertEqual(transcripts[0]['text'], "hello world")

        await self.manager.stop_transcription(session_id)

    async def test_pii_scrubbing(self):
        session_id = "s3"
        await self.manager.start_transcription(session_id, "mock_source")
        
        # With the new flexible mock STT, we can send the PII phrase directly.
        audio_chunk_pii = b"my email is sensitive@pii.com"
        await self.mock_cem.publish(f"audio_received_for_stt_{session_id}", {"session_id": session_id, "audio_chunk": audio_chunk_pii})
        
        transcripts = await self.manager.get_transcripts(session_id, real_time=False)
        
        self.assertEqual(len(transcripts), 1)
        self.assertEqual(transcripts[0]['text'], "my email is [REDACTED_EMAIL]")

        await self.manager.stop_transcription(session_id)

    async def test_end_to_end_simulation(self):
        session_id = "s4"
        
        await self.manager.start_transcription(session_id, "mock_source")
        
        # Give the simulation time to run and produce a few phrases
        await asyncio.sleep(3) 
        
        # The simulation should have generated some transcripts
        transcripts = await self.manager.get_transcripts(session_id, real_time=False)
        self.assertGreater(len(transcripts), 0)
        
        # The simulation should also stop itself, so let's wait a bit more and check
        await asyncio.sleep(4) # Total time > sum of sleeps in sim
        self.assertNotIn(session_id, self.manager.active_transcriptions)


if __name__ == "__main__":
    unittest.main()