# src/voice/stt/whisper_manager.py
"""
Manages Speech-to-Text functionality using the Whisper model via Groq's
free, high-speed inference API.
"""
import os
import httpx
from pydub import AudioSegment
import io

# from ...core import logger, config
# from ...core.error_handler_global import NetworkError
# from .. import SpeechProvider, get_stt_provider

class WhisperGroqSTT(SpeechProvider):
    """
    Primary STT provider using Whisper on Groq's LPU infrastructure.
    """
    def __init__(self):
        # self.api_key = os.getenv("GROQ_API_KEY")
        # self.api_url = "https://api.groq.com/openai/v1/audio/transcriptions"
        # self.model = "whisper-large-v3"
        # if not self.api_key:
        #     logger.warning("GROQ_API_KEY not found. WhisperGroqSTT will not be available.")
        #     raise ValueError("GROQ_API_KEY is not set in environment variables.")
        print("WhisperGroqSTT initialized.")


    def _preprocess_audio(self, audio_data: bytes) -> io.BytesIO:
        """
        Converts any input audio format to a 16kHz mono WAV file in memory.
        """
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            audio = audio.set_frame_rate(16000).set_channels(1)
            
            # Export to an in-memory file
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            return wav_buffer
        except Exception as e:
            # logger.error(f"Audio preprocessing failed: {e}")
            raise ValueError("Could not process the provided audio file.") from e

    async def transcribe(self, audio_data: bytes, language: str = None) -> str:
        """
        Transcribes a block of audio data using the Groq API.
        
        Returns:
            The transcribed text.
        """
        # preprocessed_audio = self._preprocess_audio(audio_data)
        
        # files = {
        #     'file': ('audio.wav', preprocessed_audio, 'audio/wav')
        # }
        # data = {
        #     'model': self.model,
        # }
        # if language:
        #     data['language'] = language

        # headers = {'Authorization': f'Bearer {self.api_key}'}

        # try:
        #     async with httpx.AsyncClient() as client:
        #         response = await client.post(self.api_url, headers=headers, data=data, files=files, timeout=15.0)
        #         response.raise_for_status()
        #         result = response.json()

        #         transcription = result.get("text", "")
        #         if not transcription.strip():
        #             logger.warning("Groq transcription returned empty text.")
                
        #         return transcription

        # except httpx.HTTPStatusError as e:
        #     logger.error(f"Groq API request failed with status {e.response.status_code}: {e.response.text}")
        #     # Fallback to Google provider
        #     logger.info("Falling back to Google Speech Recognition.")
        #     google_provider = get_stt_provider("google_web")
        #     return await google_provider.transcribe(audio_data, language)
        # except httpx.RequestError as e:
        #     raise NetworkError(f"Network error while calling Groq API: {e}") from e
        
        # Placeholder
        print("Transcribing with Whisper via Groq...")
        return "This is a placeholder transcription from Whisper."

    async def transcribe_stream(self, audio_stream, language: str = None):
        """Streaming is not directly supported by this provider's REST API."""
        # logger.warning("WhisperGroqSTT does not support streaming directly. Use StreamingProcessor.")
        yield "Streaming not supported by this provider."
