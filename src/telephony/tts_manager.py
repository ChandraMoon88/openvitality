# src/telephony/tts_manager.py

from typing import Dict, Any, List, Generator
import asyncio
import json
import hashlib
import os

# Assuming these imports will be available from other modules
# from src.voice.tts.edge_tts_free import EdgeTTSFree
# from src.voice.tts.elevenlabs_connector import ElevenlabsConnector
# from src.voice.tts.ssml_generator import SSMLGenerator
# from src.voice.tts.audio_cache_manager import AudioCacheManager
# from src.telephony.call_event_manager import CallEventManager
# from src.core.telemetry_emitter import TelemetryEmitter


class TTSManager:
    """
    Manages Text-to-Speech (TTS) services, including selecting appropriate voices,
    applying SSML for expressive speech, and caching generated audio.
    """
    def __init__(self, edge_tts_instance, elevenlabs_instance, ssml_generator_instance, audio_cache_manager_instance, call_event_manager_instance, telemetry_emitter_instance, config: Dict[str, Any]):
        """
        Initializes the TTSManager.
        
        :param edge_tts_instance: An initialized EdgeTTSFree instance.
        :param elevenlabs_instance: An initialized ElevenlabsConnector instance.
        :param ssml_generator_instance: An initialized SSMLGenerator instance.
        :param audio_cache_manager_instance: An initialized AudioCacheManager instance.
        :param call_event_manager_instance: An initialized CallEventManager instance.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        :param config: Application configuration, including default TTS settings.
        """
        self.edge_tts = edge_tts_instance
        self.elevenlabs_tts = elevenlabs_instance
        self.ssml_generator = ssml_generator_instance
        self.audio_cache = audio_cache_manager_instance
        self.event_manager = call_event_manager_instance
        self.telemetry = telemetry_emitter_instance
        self.config = config
        
        self.default_voice_map = config.get("tts_voices", {
            "en": "en-US-JennyNeural",
            "hi": "hi-IN-SwaraNeural",
            "es": "es-MX-DaliaNeural",
        })
        self.elevenlabs_priority_phrases = config.get("elevenlabs_priority_phrases", ["greeting", "empathy"])
        self.elevenlabs_max_chars = config.get("elevenlabs_max_chars", 10000) # Free tier limit
        self._elevenlabs_char_count = 0
        
        print("✅ TTSManager initialized.")

    async def synthesize_speech(self, text: str, session_context: Dict[str, Any], use_ssml: bool = True) -> bytes:
        """
        Synthesizes speech from text, selecting the appropriate voice and applying SSML.
        
        :param text: The text to convert to speech.
        :param session_context: A dictionary containing session-specific information (e.g., detected_language).
        :param use_ssml: If True, uses SSML to enhance speech (pauses, emphasis).
        :return: Raw audio data (e.g., WAV or MP3 bytes).
        """
        session_id = session_context.get("session_id", "unknown_session")
        language = session_context.get("detected_language", "en")
        
        # 1. Check audio cache
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        cached_audio_path = self.audio_cache.get_cached_audio(text_hash)
        if cached_audio_path and os.path.exists(cached_audio_path):
            with open(cached_audio_path, "rb") as f:
                audio_data = f.read()
            self.telemetry.emit_event("tts_cache_hit", {"session_id": session_id, "text_hash": text_hash})
            print(f"🎵 TTS cache hit for session {session_id}.")
            return audio_data

        # 2. Select TTS provider (ElevenLabs for priority phrases, else EdgeTTS)
        tts_provider = self.edge_tts # Default to free EdgeTTS
        voice_id = self.default_voice_map.get(language, self.default_voice_map["en"])
        
        for phrase_type in self.elevenlabs_priority_phrases:
            if phrase_type in session_context.get("ai_intent", ""):
                if self._elevenlabs_char_count + len(text) <= self.elevenlabs_max_chars:
                    tts_provider = self.elevenlabs_tts
                    # ElevenLabs might have specific voice IDs or settings
                    # For simplicity, assume default voice for now.
                    self._elevenlabs_char_count += len(text)
                    print(f"Using ElevenLabs for priority phrase. Current char count: {self._elevenlabs_char_count}")
                else:
                    print("ElevenLabs character limit reached, falling back to EdgeTTS.")
                break
        
        # 3. Apply SSML if enabled
        final_text = text
        if use_ssml:
            final_text = self.ssml_generator.generate_ssml(text, session_context)
        
        # 4. Synthesize speech
        try:
            audio_data = await tts_provider.synthesize(final_text, voice_id, language)
            
            # 5. Cache generated audio
            await self.audio_cache.cache_audio(text_hash, audio_data)
            self.telemetry.emit_event("tts_synthesis_success", {"session_id": session_id, "provider": tts_provider.__class__.__name__})
            return audio_data
        except Exception as e:
            print(f"🚨 Error synthesizing speech with {tts_provider.__class__.__name__}: {e}")
            self.telemetry.emit_event("tts_synthesis_error", {"session_id": session_id, "provider": tts_provider.__class__.__name__, "error": str(e)})
            
            # Fallback to a different provider or a generic audio response
            if tts_provider == self.elevenlabs_tts:
                print("Falling back to EdgeTTS due to ElevenLabs error.")
                audio_data = await self.edge_tts.synthesize(final_text, voice_id, language)
                await self.audio_cache.cache_audio(text_hash, audio_data)
                return audio_data
            
            return b"" # Return empty bytes on failure

    async def stream_speech(self, text: str, session_context: Dict[str, Any], use_ssml: bool = True) -> Generator[bytes, None, None]:
        """
        Streams speech from text, yielding chunks of audio as they are generated.
        
        :param text: The text to convert to speech.
        :param session_context: Session-specific information.
        :param use_ssml: If True, uses SSML.
        :return: A generator that yields audio data chunks.
        """
        session_id = session_context.get("session_id", "unknown_session")
        language = session_context.get("detected_language", "en")
        
        # For simplicity, caching is not applied to streaming as it often involves unique, longer phrases.
        # However, a robust system would still try to cache full streamed responses if possible.
        
        tts_provider = self.edge_tts # Default to EdgeTTS for streaming
        voice_id = self.default_voice_map.get(language, self.default_voice_map["en"])
        
        # Apply SSML if enabled
        final_text = text
        if use_ssml:
            final_text = self.ssml_generator.generate_ssml(text, session_context)

        try:
            async for chunk in tts_provider.stream(final_text, voice_id, language):
                yield chunk
            self.telemetry.emit_event("tts_streaming_success", {"session_id": session_id, "provider": tts_provider.__class__.__name__})
        except Exception as e:
            print(f"🚨 Error streaming speech with {tts_provider.__class__.__name__}: {e}")
            self.telemetry.emit_event("tts_streaming_error", {"session_id": session_id, "provider": tts_provider.__class__.__name__, "error": str(e)})
            yield b"" # Yield empty bytes on error


# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockEdgeTTSFree:
        async def synthesize(self, text: str, voice_id: str, lang: str) -> bytes:
            print(f"Mock EdgeTTS: Synthesizing '{text}' with voice {voice_id}.")
            return b"edge_tts_audio_data_for_" + text.encode()
        async def stream(self, text: str, voice_id: str, lang: str) -> Generator[bytes, None, None]:
            print(f"Mock EdgeTTS: Streaming '{text}' with voice {voice_id}.")
            for word in text.split():
                yield b"edge_tts_chunk_" + word.encode() + b" "
                await asyncio.sleep(0.05)

    class MockElevenlabsConnector:
        def __init__(self, config=None):
            self.config = config or {}
            self.api_key = self.config.get("elevenlabs_api_key", "mock-key")
        async def synthesize(self, text: str, voice_id: str, lang: str) -> bytes:
            print(f"Mock ElevenLabs: Synthesizing '{text}' with voice {voice_id}.")
            return b"elevenlabs_audio_data_for_" + text.encode()
        async def stream(self, text: str, voice_id: str, lang: str) -> Generator[bytes, None, None]:
            print(f"Mock ElevenLabs: Streaming '{text}' with voice {voice_id}.")
            for word in text.split():
                yield b"elevenlabs_chunk_" + word.encode() + b" "
                await asyncio.sleep(0.05)


    class MockSSMLGenerator:
        def generate_ssml(self, text: str, session_context: Dict) -> str:
            if "emphasis" in text.lower():
                return f"<speak>{text}</speak>" # Simple passthrough for mock
            return text

    class MockAudioCacheManager:
        def __init__(self):
            self.cache_dir = "data/tts_cache"
            os.makedirs(self.cache_dir, exist_ok=True)
            self._cache: Dict[str, str] = {} # {text_hash: file_path}
        def get_cached_audio(self, text_hash: str) -> str | None:
            return self._cache.get(text_hash)
        async def cache_audio(self, text_hash: str, audio_data: bytes):
            file_path = os.path.join(self.cache_dir, f"{text_hash}.mp3")
            with open(file_path, "wb") as f:
                f.write(audio_data)
            self._cache[text_hash] = file_path
            print(f"Mock AudioCache: Cached audio to {file_path}")

    class MockCallEventManager:
        def __init__(self): self.published_events = []
        async def publish(self, event_type: str, event_data: Dict[str, Any]):
            self.published_events.append({"type": event_type, "data": event_data})
            print(f"Mock EventManager: Published '{event_type}' - {event_data}")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # Ensure data/tts_cache directory exists
    os.makedirs("data/tts_cache", exist_ok=True)

    # --- Initialize ---
    mock_edge = MockEdgeTTSFree()
    mock_eleven = MockElevenlabsConnector()
    mock_ssml = MockSSMLGenerator()
    mock_acm = MockAudioCacheManager()
    mock_cem = MockCallEventManager()
    mock_te = MockTelemetryEmitter()
    mock_config = {
        "tts_voices": {"en": "en-US-JennyNeural", "hi": "hi-IN-SwaraNeural"},
        "elevenlabs_priority_phrases": ["greeting"],
        "elevenlabs_max_chars": 10000
    }
    
    tts_manager = TTSManager(mock_edge, mock_eleven, mock_ssml, mock_acm, mock_cem, mock_te, mock_config)

    session_context_1 = {"session_id": "s_tts_1", "detected_language": "en", "ai_intent": "greeting"}
    session_context_2 = {"session_id": "s_tts_2", "detected_language": "hi", "ai_intent": "general"}

    # --- Test 1: Synthesize speech (ElevenLabs for greeting) ---
    print("\n--- Test 1: Synthesize speech (ElevenLabs) ---")
    text_1 = "Hello, I am your AI assistant."
    audio_1 = asyncio.run(tts_manager.synthesize_speech(text_1, session_context_1))
    print(f"Synthesized Audio 1 (len): {len(audio_1)} bytes")

    # --- Test 2: Synthesize speech (EdgeTTS for general query) ---
    print("\n--- Test 2: Synthesize speech (EdgeTTS) ---")
    text_2 = "How can I help you today?"
    audio_2 = asyncio.run(tts_manager.synthesize_speech(text_2, session_context_2))
    print(f"Synthesized Audio 2 (len): {len(audio_2)} bytes")

    # --- Test 3: Synthesize speech (cache hit) ---
    print("\n--- Test 3: Synthesize speech (cache hit) ---")
    audio_1_cached = asyncio.run(tts_manager.synthesize_speech(text_1, session_context_1))
    print(f"Synthesized Audio 1 (cached len): {len(audio_1_cached)} bytes")

    # --- Test 4: Stream speech ---
    print("\n--- Test 4: Stream speech ---")
    text_stream = "This is a streamed response from the AI."
    stream_chunks = []
    async def run_stream():
        async for chunk in tts_manager.stream_speech(text_stream, session_context_1):
            stream_chunks.append(chunk)
    asyncio.run(run_stream())
    print(f"Streamed audio chunks count: {len(stream_chunks)}, total bytes: {sum(len(c) for c in stream_chunks)}")

    # Clean up created files
    if os.path.exists("data/tts_cache"):
        for filename in os.listdir("data/tts_cache"):
            os.remove(os.path.join("data/tts_cache", filename))
        os.rmdir("data/tts_cache")
