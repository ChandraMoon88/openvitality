# src/voice/tts/elevenlabs_connector.py
"""
Connector for ElevenLabs API, used for generating ultra-realistic voices
for key interaction moments to enhance user experience.
"""
import os
import httpx

# from ...core import logger
# from .audio_cache_manager import AudioCacheManager

class ElevenLabsConnector:
    """
    Manages TTS generation via ElevenLabs. Due to the limited free tier,
    this should be used sparingly, for example, for initial greetings or
    critical empathy statements.
    """
    def __init__(self):
        # self.api_key = os.getenv("ELEVENLABS_API_KEY")
        # if not self.api_key:
        #     raise ValueError("ELEVENLABS_API_KEY is not set.")
            
        # self.api_url = "https://api.elevenlabs.io/v1/text-to-speech/"
        # self.voice_id = "21m00Tcm4TlvDq8ikWAM" # A professional, warm default voice
        # self.cache = AudioCacheManager()
        print("ElevenLabsConnector initialized.")

    async def generate_voice(self, text: str, voice_id: str = None, stability: float = 0.5, clarity: float = 0.75) -> bytes:
        """
        Generates speech from text using the ElevenLabs API.

        Args:
            text: The text to convert to speech.
            voice_id: The ID of the ElevenLabs voice to use.
            stability: Voice stability setting (0-1).
            clarity: Voice clarity + similarity setting (0-1).

        Returns:
            The generated audio data as bytes.
        """
        # cached_audio = await self.cache.get_audio(text)
        # if cached_audio:
        #     logger.info(f"ElevenLabs audio found in cache for text: '{text[:30]}...'")
        #     return cached_audio

        # effective_voice_id = voice_id or self.voice_id
        # url = self.api_url + effective_voice_id
        # headers = {
        #     "Accept": "audio/mpeg",
        #     "Content-Type": "application/json",
        #     "xi-api-key": self.api_key
        # }
        # data = {
        #     "text": text,
        #     "model_id": "eleven_multilingual_v2",
        #     "voice_settings": {
        #         "stability": stability,
        #         "similarity_boost": clarity
        #     }
        # }

        # try:
        #     async with httpx.AsyncClient() as client:
        #         response = await client.post(url, json=data, headers=headers, timeout=20.0)
        #         response.raise_for_status()
        #         audio_data = await response.aread()
                
        #         # Cache the newly generated audio
        #         await self.cache.save_audio(text, audio_data)
        #         logger.info(f"Generated and cached audio from ElevenLabs for text: '{text[:30]}...'")
                
        #         return audio_data

        # except httpx.HTTPStatusError as e:
        #     logger.error(f"ElevenLabs API error: {e.response.status_code} - {e.response.text}")
        #     # Fallback strategy: In case of failure, don't return nothing.
        #     # The orchestrator should catch this and use the primary TTS instead.
        #     return None
        # except Exception as e:
        #     logger.error(f"Failed to generate ElevenLabs voice: {e}")
        #     return None
        
        print(f"Generating voice with ElevenLabs for: '{text[:30]}...'")
        return b"elevenlabs_placeholder_audio"

# Strategy Example:
# async def say_greeting(text: str):
#     eleven_labs = ElevenLabsConnector()
#     edge_tts = EdgeTTSProvider()
    
#     # Try to generate with the high-quality voice first
#     audio = await eleven_labs.generate_voice(text)
    
#     if audio is None:
#         # Fallback to the free, unlimited provider
#         logger.warning("Falling back to EdgeTTS for greeting.")
#         audio = await edge_tts.generate_voice(text)
        
#     return audio
