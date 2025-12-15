# src/telephony/dtmf_detector.py

from typing import Dict, Any, Callable
import numpy as np
import asyncio
import json
import time

# Assuming these imports will be available from other modules
# from src.telephony.call_event_manager import CallEventManager
# from src.core.telemetry_emitter import TelemetryEmitter

# DTMF Frequencies (standard ITU-T Q.23)
# Row frequencies (low tones)
DTMF_ROW_FREQS = {
    '1': 697, '2': 697, '3': 697, 'A': 697,
    '4': 770, '5': 770, '6': 770, 'B': 770,
    '7': 852, '8': 852, '9': 852, 'C': 852,
    '*': 941, '0': 941, '#': 941, 'D': 941,
}
# Column frequencies (high tones)
DTMF_COL_FREQS = {
    '1': 1209, '4': 1209, '7': 1209, '*': 1209,
    '2': 1336, '5': 1336, '8': 1336, '0': 1336,
    '3': 1477, '6': 1477, '9': 1477, '#': 1477,
    'A': 1633, 'B': 1633, 'C': 1633, 'D': 1633,
}

# Map frequency pairs to characters
DTMF_TONES = {}
for char in DTMF_ROW_FREQS.keys():
    DTMF_TONES[(DTMF_ROW_FREQS[char], DTMF_COL_FREQS[char])] = char


class DTMFDetector:
    """
    Detects DTMF (Dual-Tone Multi-Frequency) tones from incoming raw audio streams.
    Processes audio frames to identify the presence of specific frequency pairs
    that correspond to DTMF digits.
    """
    def __init__(self, call_event_manager_instance, telemetry_emitter_instance, sample_rate: int = 8000):
        """
        Initializes the DTMFDetector.
        
        :param call_event_manager_instance: An initialized CallEventManager instance.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        :param sample_rate: The sample rate of the incoming audio (Hz, typically 8000 for telephony).
        """
        self.event_manager = call_event_manager_instance
        self.telemetry = telemetry_emitter_instance
        self.sample_rate = sample_rate
        
        self.min_tone_duration_ms = 40 # Minimum duration a tone must be present to be detected
        self.max_freq_deviation = 10 # Hz, allowed deviation from target DTMF frequencies
        self.power_threshold = 1e6 # Minimum power to consider a signal (avoids noise detection)

        # Buffer to accumulate audio frames
        self.audio_buffer = np.array([], dtype=np.int16)
        self.fft_window_size = 400  # ~50ms window for 8000Hz
        self.fft_step_size = 200    # ~25ms step (50% overlap)

        # State tracking based on samples, not real-time
        self.current_tone = None
        self.current_tone_samples = 0
        self.min_tone_duration_samples = int(self.sample_rate * self.min_tone_duration_ms / 1000)
        self.last_detected_digit = None # For debouncing

        print("✅ DTMFDetector initialized.")

    def _find_best_tone(self, window):
        """Finds the best matching DTMF tone in a given audio window."""
        n = len(window)
        if n == 0:
            return None

        # Apply a Hanning window for better frequency resolution
        hann_window = np.hanning(n)
        window = window * hann_window

        fft_result = np.fft.fft(window)
        freqs = np.fft.fftfreq(n, d=1/self.sample_rate)
        
        magnitudes = np.abs(fft_result)

        row_freq, row_mag = 0, 0
        col_freq, col_mag = 0, 0

        # Find the peak frequency in the low-frequency group
        for f in set(DTMF_ROW_FREQS.values()):
            # Find the closest frequency bin
            idx = np.argmin(np.abs(freqs - f))
            if magnitudes[idx] > row_mag:
                row_mag = magnitudes[idx]
                row_freq = f
        
        # Find the peak frequency in the high-frequency group
        for f in set(DTMF_COL_FREQS.values()):
            idx = np.argmin(np.abs(freqs - f))
            if magnitudes[idx] > col_mag:
                col_mag = magnitudes[idx]
                col_freq = f
        
        # Check if the magnitudes are above the threshold
        if row_mag > self.power_threshold and col_mag > self.power_threshold:
            return DTMF_TONES.get((row_freq, col_freq))

        return None

    async def detect_dtmf(self, audio_frame_bytes: bytes, session_id: str) -> str | None:
        """
        Processes an incoming raw audio frame (16-bit PCM mono) to detect DTMF tones.
        """
        audio_frame_np = np.frombuffer(audio_frame_bytes, dtype=np.int16)
        self.audio_buffer = np.concatenate((self.audio_buffer, audio_frame_np))

        final_detected_digit = None

        while len(self.audio_buffer) >= self.fft_window_size:
            window = self.audio_buffer[:self.fft_window_size]
            
            digit = self._find_best_tone(window)

            if digit:
                if self.current_tone == digit:
                    self.current_tone_samples += self.fft_step_size
                else:
                    # New tone starts
                    self.current_tone = digit
                    self.current_tone_samples = self.fft_step_size
                    self.last_detected_digit = None # Reset debounce on new tone
                
                # Check if duration is met and it's not the one we just detected
                if self.current_tone_samples >= self.min_tone_duration_samples and self.current_tone != self.last_detected_digit:
                    final_detected_digit = self.current_tone
                    self.last_detected_digit = self.current_tone # Debounce
            else:
                # Silence or non-DTMF sound
                self.current_tone = None
                self.current_tone_samples = 0
                self.last_detected_digit = None

            # Move buffer forward
            self.audio_buffer = self.audio_buffer[self.fft_step_size:]

        if final_detected_digit:
            await self.event_manager.publish("dtmf_received", {"session_id": session_id, "digit": final_detected_digit})
            self.telemetry.emit_event("dtmf_detected", {"session_id": session_id, "digit": final_detected_digit})
        
        return final_detected_digit

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockCallEventManager:
        def __init__(self):
            self.published_events = []
        async def publish(self, event_type: str, event_data: Dict[str, Any]):
            self.published_events.append({"type": event_type, "data": event_data})
            print(f"Mock EventManager: Published '{event_type}' - {event_data}")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_cem = MockCallEventManager()
    mock_te = MockTelemetryEmitter()
    
    detector = DTMFDetector(mock_cem, mock_te, sample_rate=8000)

    # --- Test 1: Simulate DTMF '5' tone ---
    print("\n--- Test 1: Simulate DTMF '5' tone ---")
    session_id = "s_dtmf_1"
    
    # Generate a 500ms audio frame for DTMF '5' (770Hz + 1336Hz)
    sample_rate_dtmf = 8000
    duration_dtmf = 0.5 # seconds
    t = np.linspace(0, duration_dtmf, int(sample_rate_dtmf * duration_dtmf), endpoint=False)
    
    f1 = 770  # Row frequency for '5'
    f2 = 1336 # Column frequency for '5'
    
    # Generate two sine waves and add them
    tone1 = np.sin(2 * np.pi * f1 * t)
    tone2 = np.sin(2 * np.pi * f2 * t)
    dtmf_tone = (tone1 + tone2) * 0.5 # Scale to prevent clipping
    
    # Convert to 16-bit PCM bytes
    dtmf_audio_bytes = (dtmf_tone * 32767).astype(np.int16).tobytes()

    # Split into smaller frames and feed to detector
    frame_size_bytes = int(sample_rate_dtmf * 0.02 * 2) # 20ms frames, 16-bit mono
    num_frames = len(dtmf_audio_bytes) // frame_size_bytes
    
    detected_digit = None
    for i in range(num_frames):
        frame = dtmf_audio_bytes[i*frame_size_bytes : (i+1)*frame_size_bytes]
        detected = asyncio.run(detector.detect_dtmf(frame, session_id))
        if detected:
            detected_digit = detected
            print(f"  [Main Loop] Detected digit: {detected_digit}")
            # In a real app, you might break or act on the first detection.
            # For this demo, let's keep going.
        asyncio.run(asyncio.sleep(0.01)) # Simulate small processing delay

    print(f"Final detected digit for Test 1: {detected_digit}") # Should be '5'
    print(f"Events published: {mock_cem.published_events}")

    # --- Test 2: Simulate noise (no DTMF) ---
    print("\n--- Test 2: Simulate noise (no DTMF) ---")
    session_id_noise = "s_dtmf_noise"
    noise_audio_bytes = np.random.normal(0, 1000, int(sample_rate_dtmf * 0.5)).astype(np.int16).tobytes()
    detected_digit_noise = None
    
    for i in range(num_frames):
        frame = noise_audio_bytes[i*frame_size_bytes : (i+1)*frame_size_bytes]
        detected = asyncio.run(detector.detect_dtmf(frame, session_id_noise))
        if detected:
            detected_digit_noise = detected
        asyncio.run(asyncio.sleep(0.01))
    
    print(f"Final detected digit for Test 2 (noise): {detected_digit_noise}") # Should be None