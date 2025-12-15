import sys
sys.path.append('.')

import unittest
import asyncio
import os
import shutil
import hashlib
from typing import Dict, Any, Generator

from src.telephony.tts_manager import TTSManager

# --- Mock Dependencies ---
class MockEdgeTTSFree:
    async def synthesize(self, text: str, voice_id: str, lang: str) -> bytes:
        return b"edge_tts_audio:" + text.encode()
    async def stream(self, text: str, voice_id: str, lang: str):
        for word in text.split():
            yield b"edge_chunk:" + word.encode()

class MockElevenlabsConnector:
    async def synthesize(self, text: str, voice_id: str, lang: str) -> bytes:
        return b"elevenlabs_audio:" + text.encode()
    async def stream(self, text: str, voice_id: str, lang: str):
        for word in text.split():
            yield b"eleven_chunk:" + word.encode()

class MockSSMLGenerator:
    def generate_ssml(self, text: str, session_context: Dict) -> str:
        return f"<ssml>{text}</ssml>"

class MockAudioCacheManager:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self._cache = {}
    def get_cached_audio(self, text_hash: str) -> str | None:
        return self._cache.get(text_hash)
    async def cache_audio(self, text_hash: str, audio_data: bytes):
        path = os.path.join(self.cache_dir, f"{text_hash}.mock")
        with open(path, "wb") as f:
            f.write(audio_data)
        self._cache[text_hash] = path

class MockCallEventManager:
    async def publish(self, event_type: str, event_data: Dict[str, Any]):
        pass

class MockTelemetryEmitter:
    def __init__(self):
        self.events = []
    def emit_event(self, event_name: str, data: Dict):
        self.events.append({"name": event_name, "data": data})

class TestTTSManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.cache_dir = "temp_tts_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.mock_edge = MockEdgeTTSFree()
        self.mock_eleven = MockElevenlabsConnector()
        self.mock_ssml = MockSSMLGenerator()
        self.mock_acm = MockAudioCacheManager(self.cache_dir)
        self.mock_cem = MockCallEventManager()
        self.mock_te = MockTelemetryEmitter()
        self.mock_config = {
            "tts_voices": {"en": "en-voice"},
            "elevenlabs_priority_phrases": ["greeting"],
            "elevenlabs_max_chars": 1000
        }
        
        self.tts_manager = TTSManager(self.mock_edge, self.mock_eleven, self.mock_ssml, self.mock_acm, self.mock_cem, self.mock_te, self.mock_config)

    def tearDown(self):
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)

    async def test_synthesize_speech_default_provider(self):
        context = {"session_id": "s1", "ai_intent": "general"}
        text = "some general text"
        audio = await self.tts_manager.synthesize_speech(text, context)
        self.assertTrue(audio.startswith(b"edge_tts_audio"))

    async def test_synthesize_speech_priority_provider(self):
        context = {"session_id": "s2", "ai_intent": "greeting"}
        text = "a greeting text"
        audio = await self.tts_manager.synthesize_speech(text, context)
        self.assertTrue(audio.startswith(b"elevenlabs_audio"))

    async def test_caching(self):
        context = {"session_id": "s3"}
        text = "text to be cached"
        
        # First call - should synthesize and cache
        self.mock_edge.synthesize = unittest.mock.AsyncMock(return_value=b"audio")
        await self.tts_manager.synthesize_speech(text, context)
        self.mock_edge.synthesize.assert_called_once()

        # Second call - should hit cache and not synthesize
        self.mock_edge.synthesize.reset_mock()
        await self.tts_manager.synthesize_speech(text, context)
        self.mock_edge.synthesize.assert_not_called()
        self.assertTrue(any(e['name'] == 'tts_cache_hit' for e in self.mock_te.events))

    async def test_ssml_application(self):
        context = {"session_id": "s4"}
        text = "text for ssml"
        
        self.mock_ssml.generate_ssml = unittest.mock.MagicMock(return_value="<ssml>text</ssml>")
        self.mock_edge.synthesize = unittest.mock.AsyncMock(return_value=b"audio")

        await self.tts_manager.synthesize_speech(text, context, use_ssml=True)
        
        self.mock_ssml.generate_ssml.assert_called_once_with(text, context)
        self.mock_edge.synthesize.assert_called_with("<ssml>text</ssml>", "en-voice", "en")

    async def test_streaming(self):
        context = {"session_id": "s5"}
        text = "this is streamed"
        
        chunks = []
        async for chunk in self.tts_manager.stream_speech(text, context):
            chunks.append(chunk)
            
        self.assertEqual(len(chunks), 4)
        self.assertTrue(chunks[0].startswith(b"edge_chunk"))

    async def test_provider_fallback(self):
        context = {"session_id": "s6", "ai_intent": "greeting"} # Should trigger ElevenLabs
        text = "trigger fallback"
        
        # Make ElevenLabs fail
        self.mock_eleven.synthesize = unittest.mock.AsyncMock(side_effect=Exception("API Error"))
        self.mock_edge.synthesize = unittest.mock.AsyncMock(return_value=b"fallback_audio")

        audio = await self.tts_manager.synthesize_speech(text, context)
        
        self.mock_eleven.synthesize.assert_called_once()
        self.mock_edge.synthesize.assert_called_once()
        self.assertEqual(audio, b"fallback_audio")
        self.assertTrue(any(e['name'] == 'tts_synthesis_error' for e in self.mock_te.events))


if __name__ == "__main__":
    unittest.main()