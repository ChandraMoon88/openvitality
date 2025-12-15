# src/voice/stt/vad_engine.py
"""
Voice Activity Detection (VAD) engine to determine if an audio chunk
contains speech or silence.
"""
import webrtcvad
from collections import deque

class VADEngine:
    """
    Uses the WebRTC VAD algorithm, which is a standard for its quality
    and efficiency.
    """
    def __init__(self, sensitivity: int = 3, sample_rate: int = 16000, frame_duration_ms: int = 30, silence_threshold_ms: int = 800):
        """
        Initializes the VAD engine.

        Args:
            sensitivity: How aggressive the VAD should be (0=least, 3=most).
            sample_rate: Sample rate of the audio (8000, 16000, 32000, or 48000).
            frame_duration_ms: Duration of each audio frame in milliseconds (10, 20, or 30).
            silence_threshold_ms: Duration of silence in ms to consider user finished speaking.
        """
        if sample_rate not in [8000, 16000, 32000, 48000]:
            raise ValueError("VAD sample rate must be 8000, 16000, 32000, or 48000.")
        if frame_duration_ms not in [10, 20, 30]:
            raise ValueError("VAD frame duration must be 10, 20, or 30 ms.")

        self.vad = webrtcvad.Vad(sensitivity)
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        # Frame size in samples (16-bit PCM, so 2 bytes per sample)
        self.frame_size_bytes = (sample_rate * frame_duration_ms // 1000) * 2
        
        # Buffer to detect end of speech
        self.silence_threshold_ms = silence_threshold_ms
        num_silence_frames = self.silence_threshold_ms // frame_duration_ms
        self.silence_buffer = deque(maxlen=num_silence_frames)
        self.reset_vad_state()
        
        print(f"VADEngine initialized with sensitivity {sensitivity}, sample_rate {sample_rate}, frame_duration_ms {frame_duration_ms}.")

    def reset_vad_state(self):
        """Resets the internal state of the VAD buffer."""
        self.silence_buffer.clear()
        for _ in range(self.silence_buffer.maxlen):
            self.silence_buffer.append(True) # Fill with silence initially

    def is_speech(self, audio_frame: bytes) -> bool:
        """
        Analyzes a single audio frame and returns True if it likely contains speech.
        
        Args:
            audio_frame: A chunk of audio data. Must be the correct size
                         (e.g., for 16kHz, 30ms -> 960 bytes).
        """
        if len(audio_frame) != self.frame_size_bytes:
            # This indicates an issue with chunking. For webrtcvad, frames must be exact.
            print(f"VAD frame size mismatch: Expected {self.frame_size_bytes}, got {len(audio_frame)}")
            return False # Treat as non-speech if frame is malformed
        
        try:
            is_speech = self.vad.is_speech(audio_frame, self.sample_rate)
            self.silence_buffer.append(not is_speech)
            return is_speech
        except Exception as e:
            # Handle potential errors from the VAD library
            print(f"VAD processing error: {e}. Treating as non-speech.")
            return False
        
    def has_user_finished_speaking(self) -> bool:
        """
        Checks if the user has been silent long enough to be considered
        to have finished their turn.
        """
        # True if the buffer is full and contains only silence frames
        return len(self.silence_buffer) == self.silence_buffer.maxlen and all(self.silence_buffer)

    def process_stream(self, audio_stream):
        """
        A generator that yields (is_speech, frame) tuples for an audio stream.
        (Conceptual - not used directly by SipAudioBridge in current design)
        """
        pass
