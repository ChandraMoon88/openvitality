# src/voice/tts/edge_tts_free.py
"""
The primary Text-to-Speech engine, using Microsoft Edge's free and
unlimited online TTS service via the `edge-tts` library.
"""
import asyncio
import edge_tts

# from ...core import logger
# from .audio_cache_manager import AudioCacheManager

class EdgeTTSProvider:
    """
    This is the workhorse TTS provider for the system. It's completely free,
    supports a vast number of languages and voices, and provides high-quality
    neural output.
    """
    def __init__(self):
        # self.cache = AudioCacheManager()
        self.voice_map = {
            "en": "en-US-JennyNeural",
            "hi": "hi-IN-SwaraNeural",
            "te": "te-IN-ShrutiNeural",
            "ta": "ta-IN-PallaviNeural", # ValluvarNeural is not in the standard list, Pallavi is an alternative
            "es": "es-MX-DaliaNeural",
            "ar": "ar-EG-SalmaNeural",
            # Add other mappings as needed
        }
        print("EdgeTTSProvider initialized.")

    async def generate_voice(self, text: str, language: str = "en", rate: str = "+0%", pitch: str = "+0Hz") -> bytes:
        """
        Generates speech from text using the edge-tts library.

        Args:
            text: The text to convert to speech (can include SSML).
            language: The ISO code for the language (e.g., 'en', 'hi').
            rate: The speed of the speech (e.g., "-10%", "+20%").
            pitch: The pitch of the speech (e.g., "-10Hz", "+20Hz").

        Returns:
            The generated audio data as bytes (MP3 format).
        """
        # cache_key = f"{text}|{language}|{rate}|{pitch}"
        # cached_audio = await self.cache.get_audio(cache_key)
        # if cached_audio:
        #     logger.info(f"EdgeTTS audio found in cache for text: '{text[:30]}...'")
        #     return cached_audio

        voice = self.voice_map.get(language, "en-US-JennyNeural")
        
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            
            # The library writes to a file, so we'll use an in-memory byte stream
            audio_buffer = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])
            
            audio_data = bytes(audio_buffer)
            # await self.cache.save_audio(cache_key, audio_data)
            # logger.info(f"Generated and cached audio from EdgeTTS for text: '{text[:30]}...'")
            return audio_data

        except Exception as e:
            # logger.error(f"Edge-TTS generation failed: {e}")
            # Return a silent audio clip or handle this error upstream
            return b""

    async def stream_voice(self, text: str, language: str = "en"):
        """
        A generator that yields audio chunks for real-time streaming.
        """
        voice = self.voice_map.get(language, "en-US-JennyNeural")
        # logger.info(f"Streaming EdgeTTS for language '{language}' with voice '{voice}'")
        try:
            communicate = edge_tts.Communicate(text, voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as e:
            # logger.error(f"Edge-TTS streaming failed: {e}")
            yield b"" # Yield empty bytes to signal end or error
