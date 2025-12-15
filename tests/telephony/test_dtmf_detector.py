import sys
sys.path.append('.')

import unittest
import asyncio
import numpy as np
from typing import Dict, Any

from src.telephony.dtmf_detector import DTMFDetector, DTMF_ROW_FREQS, DTMF_COL_FREQS

# --- Mock Dependencies ---
class MockCallEventManager:
    def __init__(self):
        self.published_events = []
    async def publish(self, event_type: str, event_data: Dict[str, Any]):
        self.published_events.append({"type": event_type, "data": event_data})

class MockTelemetryEmitter:
    def __init__(self):
        self.events = []
    def emit_event(self, event_name: str, data: Dict):
        self.events.append({"name": event_name, "data": data})

class TestDTMFDetector(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_cem = MockCallEventManager()
        self.mock_te = MockTelemetryEmitter()
        self.sample_rate = 8000
        self.detector = DTMFDetector(self.mock_cem, self.mock_te, sample_rate=self.sample_rate)

    def _generate_dtmf_tone(self, digit: str, duration_s: float) -> bytes:
        t = np.linspace(0, duration_s, int(self.sample_rate * duration_s), endpoint=False)
        f1 = DTMF_ROW_FREQS[digit]
        f2 = DTMF_COL_FREQS[digit]
        
        tone1 = np.sin(2 * np.pi * f1 * t)
        tone2 = np.sin(2 * np.pi * f2 * t)
        dtmf_tone = (tone1 + tone2) * 0.5
        
        return (dtmf_tone * 32767).astype(np.int16).tobytes()

    async def _feed_audio_to_detector(self, audio_bytes: bytes, session_id: str) -> str | None:
        frame_size = int(self.sample_rate * 0.02 * 2) # 20ms frames, 16-bit
        num_frames = len(audio_bytes) // frame_size
        
        detected_digit = None
        for i in range(num_frames):
            frame = audio_bytes[i*frame_size : (i+1)*frame_size]
            detected = await self.detector.detect_dtmf(frame, session_id)
            if detected:
                detected_digit = detected
        return detected_digit

    async def test_detect_single_digit(self):
        digit_to_test = '7'
        audio = self._generate_dtmf_tone(digit_to_test, 0.2) # 200ms duration
        detected = await self._feed_audio_to_detector(audio, "session1")
        
        self.assertEqual(detected, digit_to_test)
        self.assertEqual(len(self.mock_cem.published_events), 1)
        self.assertEqual(self.mock_cem.published_events[0]['data']['digit'], digit_to_test)

    async def test_no_detection_with_noise(self):
        noise = np.random.normal(0, 1000, int(self.sample_rate * 0.5)).astype(np.int16).tobytes()
        detected = await self._feed_audio_to_detector(noise, "session2")
        
        self.assertIsNone(detected)

    async def test_no_detection_with_single_frequency(self):
        duration_s = 0.2
        t = np.linspace(0, duration_s, int(self.sample_rate * duration_s), endpoint=False)
        f1 = 697 # Just one frequency
        tone = np.sin(2 * np.pi * f1 * t)
        audio = (tone * 32767).astype(np.int16).tobytes()
        
        detected = await self._feed_audio_to_detector(audio, "session3")
        self.assertIsNone(detected)

    async def test_short_tone_is_ignored(self):
        # Detector min duration is 40ms, let's generate a 20ms tone.
        self.detector.min_tone_duration_ms = 40
        audio = self._generate_dtmf_tone('1', 0.02)
        detected = await self._feed_audio_to_detector(audio, "session4")
        
        # This test is tricky because the detector's state logic is time-based.
        # A simple feed might not correctly simulate the timing needed.
        # However, if the total audio length is shorter than the detection window, it should fail.
        # Let's adjust the test to be more direct.
        self.assertIsNone(detected, "A tone shorter than min_tone_duration_ms should be ignored")
    
    async def test_detects_all_standard_digits(self):
        digits_to_test = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '*', '#']
        for i, digit in enumerate(digits_to_test):
            with self.subTest(digit=digit):
                audio = self._generate_dtmf_tone(digit, 0.2)
                self.mock_cem.published_events.clear()
                detected = await self._feed_audio_to_detector(audio, f"session_all_{i}")
                self.assertEqual(detected, digit)
                self.assertEqual(len(self.mock_cem.published_events), 1)

if __name__ == "__main__":
    unittest.main()