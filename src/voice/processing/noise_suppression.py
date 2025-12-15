# src/voice/processing/noise_suppression.py
"""
Cleans up incoming audio by removing background noise, which significantly
improves speech-to-text accuracy.
"""
import numpy as np
# import noisereduce as nr
from pydub import AudioSegment
import io

# from ...core import logger

class NoiseSuppressor:
    """
    Applies noise reduction algorithms to audio data.
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        print("NoiseSuppressor initialized.")

    def _bytes_to_numpy(self, audio_data: bytes) -> np.ndarray:
        """Converts raw audio bytes (assuming WAV) to a NumPy array."""
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format="wav")
            audio = audio.set_frame_rate(self.sample_rate).set_channels(1)
            samples = np.array(audio.get_array_of_samples()).astype(np.float32)
            return samples
        except Exception as e:
            # logger.error(f"Could not convert audio bytes to numpy array: {e}")
            return None

    def _numpy_to_bytes(self, audio_samples: np.ndarray) -> bytes:
        """Converts a NumPy array back to WAV audio bytes."""
        # Normalize and convert to 16-bit integer
        int_samples = (audio_samples * 32767).astype(np.int16)
        
        audio_segment = AudioSegment(
            int_samples.tobytes(),
            frame_rate=self.sample_rate,
            sample_width=2, # 16-bit
            channels=1
        )
        
        buffer = io.BytesIO()
        audio_segment.export(buffer, format="wav")
        buffer.seek(0)
        return buffer.read()

    def reduce_noise(self, audio_data: bytes) -> bytes:
        """
        Reduces noise from an audio clip.
        This is a CPU-intensive operation and should be run in a process pool.
        """
        # audio_samples = self._bytes_to_numpy(audio_data)
        # if audio_samples is None:
        #     return audio_data # Return original audio on conversion failure

        # # The first 0.5 seconds are used to create a noise profile
        # noise_clip = audio_samples[:int(self.sample_rate * 0.5)]
        
        # # Perform noise reduction
        # reduced_noise_samples = nr.reduce_noise(
        #     y=audio_samples,
        #     sr=self.sample_rate,
        #     y_noise=noise_clip,
        #     prop_decrease=1.0, # Aggressive reduction
        #     n_fft=512
        # )
        
        # logger.info("Successfully applied noise reduction to audio clip.")
        # return self._numpy_to_bytes(reduced_noise_samples)

        print("Applying noise suppression...")
        # Placeholder just returns the original data
        return audio_data

# Example Usage
# async def process_noisy_audio(audio_bytes: bytes):
#     suppressor = NoiseSuppressor()
#     # Offload to CPU pool
#     clean_audio = await pool_manager.run_in_cpu_pool(suppressor.reduce_noise, audio_bytes)
#     return clean_audio
