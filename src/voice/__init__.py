# src/voice/__init__.py
"""
The voice module handles all speech-to-text (STT) and text-to-speech (TTS)
functionality for the AI Hospital application.
"""
from abc import ABC, abstractmethod
from typing import Dict, Type

# from .stt.whisper_manager import WhisperGroqSTT
# from .stt.google_speech_v2 import GoogleWebSpeechSTT
# from .stt.azure_speech import AzureCognitiveSpeechSTT
# from ..core import config, logger

class SpeechProvider(ABC):
    """Abstract base class for a speech-to-text provider."""
    
    @abstractmethod
    async def transcribe(self, audio_data: bytes, language: str = None) -> str:
        """Transcribes a block of audio data."""
        pass

    @abstractmethod
    async def transcribe_stream(self, audio_stream, language: str = None):
        """Transcribes a real-time audio stream."""
        pass

# --- Provider Registry ---
# A registry to hold all available STT provider classes.
# PROVIDER_REGISTRY: Dict[str, Type[SpeechProvider]] = {
#     "whisper_groq": WhisperGroqSTT,
#     "google_web": GoogleWebSpeechSTT,
#     "azure": AzureCognitiveSpeechSTT,
# }

# --- Factory Method ---
def get_stt_provider(provider_name: str = None) -> SpeechProvider:
    """
    Factory function to get an instance of an STT provider.
    
    Args:
        provider_name: The name of the provider to get. If None, uses the
                       default from the application configuration.
                       
    Returns:
        An instance of a class that inherits from SpeechProvider.
    """
    # if provider_name is None:
    #     provider_name = config.stt.default_provider # e.g., 'whisper_groq'

    # provider_class = PROVIDER_REGISTRY.get(provider_name)
    
    # if not provider_class:
    #     logger.error(f"STT provider '{provider_name}' not found. Falling back to default.")
    #     provider_class = PROVIDER_REGISTRY[config.stt.default_provider]
        
    # logger.info(f"Using STT provider: {provider_name}")
    # return provider_class()

    print(f"STT Provider factory called for: {provider_name or 'default'}")
    return None # Placeholder

__all__ = ["SpeechProvider", "get_stt_provider"]
