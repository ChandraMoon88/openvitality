# src/voice/processing/echo_cancellation.py
"""
Prevents the AI from hearing its own voice when the user is on speakerphone,
which would otherwise cause a feedback loop.
"""
from collections import deque
import numpy as np

# A placeholder for a real AEC library like speexdsp or webrtc_audio_processing
# import aec_library 

# from ...core import logger

class EchoCanceller:
    """
    Implements Acoustic Echo Cancellation (AEC) by subtracting the AI's
    own speech from the incoming microphone audio.
    """
    def __init__(self, sample_rate: int = 16000, buffer_duration_s: int = 2):
        """
        Initializes the EchoCanceller.

        Args:
            sample_rate: The audio sample rate.
            buffer_duration_s: The duration of outgoing audio to keep for cancellation.
        """
        self.sample_rate = sample_rate
        self.buffer_size = sample_rate * buffer_duration_s
        
        # A circular buffer to hold the last N seconds of the AI's speech (playback)
        self.playback_buffer = deque(maxlen=self.buffer_size)
        
        # Initialize the AEC algorithm from a library
        # self.aec_instance = aec_library.AEC(sample_rate=self.sample_rate)

        print("EchoCanceller initialized.")

    def add_to_playback_buffer(self, audio_chunk: np.ndarray):
        """
        Adds a chunk of the AI's speech (what is being sent to the user)
        to the playback buffer.

        Args:
            audio_chunk: A NumPy array of audio samples.
        """
        self.playback_buffer.extend(audio_chunk)

    def cancel_echo(self, mic_input: np.ndarray) -> np.ndarray:
        """
        Processes the incoming microphone audio to remove the echo of the
        AI's own speech.

        Args:
            mic_input: A chunk of audio from the user's microphone.

        Returns:
            A chunk of audio with the echo removed.
        """
        if len(self.playback_buffer) == 0:
            # Nothing to cancel
            return mic_input
        
        # Convert playback buffer to a numpy array
        playback_signal = np.array(self.playback_buffer)
        
        # This is where the magic happens. The actual library call would
        # take the microphone input and the playback signal and return
        # the cleaned-up signal.
        # clean_signal = self.aec_instance.process(mic_input, playback_signal)
        
        # logger.debug("Applied acoustic echo cancellation.")
        
        # Placeholder logic: just return the original input
        clean_signal = mic_input
        
        return clean_signal

# Example integration:
#
# aec = EchoCanceller()
#
# async def handle_outgoing_audio(audio_chunk):
#     # This audio is being sent to the user
#     aec.add_to_playback_buffer(audio_chunk)
#     await send_to_user(audio_chunk)
#
# async def handle_incoming_audio(mic_chunk):
#     # This audio is from the user's microphone
#     clean_chunk = aec.cancel_echo(mic_chunk)
#     await process_for_stt(clean_chunk)
