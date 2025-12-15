# src/voice/tts/audio_cache_manager.py
"""
Manages caching for generated audio files to improve response time
and reduce redundant TTS API calls.
"""
import hashlib
from pathlib import Path
import os
import time

# from ...core import logger

class AudioCacheManager:
    """
    Stores and retrieves generated TTS audio files from a local directory.
    Uses an LRU (Least Recently Used) strategy for cache eviction.
    """
    def __init__(self, cache_dir: str = "assets/audio/cache", max_size_mb: int = 1024):
        self.cache_dir = Path(cache_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        # Ensure the cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"AudioCacheManager initialized at {self.cache_dir}.")

    def _get_hash(self, text: str) -> str:
        """Creates a SHA256 hash of the input text to use as a filename."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    async def get_audio(self, text: str) -> bytes | None:
        """
        Retrieves an audio file from the cache.
        Returns the audio data as bytes if found, otherwise None.
        """
        filename = self._get_hash(text) + ".mp3"
        filepath = self.cache_dir / filename
        
        if filepath.exists():
            # Update the file's access time for LRU eviction
            filepath.touch()
            return filepath.read_bytes()
        
        return None

    async def save_audio(self, text: str, audio_data: bytes):
        """
        Saves a newly generated audio file to the cache.
        """
        filename = self._get_hash(text) + ".mp3"
        filepath = self.cache_dir / filename
        
        # Before saving, ensure we're not exceeding the cache size limit
        await self._enforce_cache_limit()
        
        filepath.write_bytes(audio_data)
        # logger.debug(f"Saved audio to cache: {filepath}")

    async def prewarm_cache(self, common_phrases: list[str], tts_provider):
        """
        Pre-generates and caches audio for a list of common phrases at startup.
        
        Args:
            common_phrases: A list of strings to pre-generate.
            tts_provider: A TTS provider instance to use for generation.
        """
        # logger.info("Pre-warming audio cache...")
        for phrase in common_phrases:
            if not await self.get_audio(phrase):
                # logger.debug(f"Pre-warming cache for: '{phrase}'")
                audio_data = await tts_provider.generate_voice(phrase)
                if audio_data:
                    await self.save_audio(phrase, audio_data)
        # logger.info("Audio cache pre-warming complete.")

    async def _enforce_cache_limit(self):
        """
        Checks the cache size and evicts the least recently used files if
        the size limit is exceeded.
        """
        files = sorted(self.cache_dir.iterdir(), key=lambda f: f.stat().st_atime)
        current_size = sum(f.stat().st_size for f in files)
        
        while current_size > self.max_size_bytes:
            if not files:
                break
            # Evict the least recently used (oldest access time) file
            lru_file = files.pop(0)
            file_size = lru_file.stat().st_size
            lru_file.unlink()
            current_size -= file_size
            # logger.info(f"Cache limit exceeded. Evicted LRU file: {lru_file.name}")
