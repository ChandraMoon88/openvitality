import sys
sys.path.append('.')

import unittest
import numpy as np
import audioop
from typing import Dict, Any

from src.telephony.audio_mixer import AudioMixer

# --- Mock Dependencies ---
class MockCodecTranscoder:
    def resample(self, audio_data, in_rate, out_rate, sample_width):
        if in_rate == out_rate: return audio_data
        # A very basic mock of resampling
        resampled_data, _ = audioop.ratecv(audio_data, sample_width, 1, in_rate, out_rate, None)
        return resampled_data

    def convert_channels(self, audio_data, in_channels, out_channels, sample_width):
        if in_channels == out_channels: return audio_data
        if in_channels == 2 and out_channels == 1:
            return audioop.tomono(audio_data, sample_width, 1, 1)
        if in_channels == 1 and out_channels == 2:
            return audioop.tostereo(audio_data, sample_width, 1, 1)
        return audio_data

class MockTelemetryEmitter:
    def __init__(self):
        self.events = []
    def emit_event(self, event_name: str, data: Dict):
        self.events.append({"name": event_name, "data": data})

class TestAudioMixer(unittest.TestCase):

    def setUp(self):
        self.mock_transcoder = MockCodecTranscoder()
        self.mock_te = MockTelemetryEmitter()
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2
        self.mixer = AudioMixer(
            sample_rate=self.sample_rate,
            channels=self.channels,
            sample_width=self.sample_width,
            transcoder_instance=self.mock_transcoder,
            telemetry_emitter_instance=self.mock_te
        )

    def _generate_sine_wave(self, frequency, duration, sample_rate, channels):
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        audio = (np.sin(2 * np.pi * frequency * t) * 10000).astype(np.int16)
        if channels == 2:
            audio_stereo = np.empty((audio.size * 2,), dtype=np.int16)
            audio_stereo[0::2] = audio
            audio_stereo[1::2] = audio
            return audio_stereo.tobytes()
        return audio.tobytes()

    def test_add_and_remove_stream(self):
        self.assertEqual(len(self.mixer.active_streams), 0)
        self.mixer.add_stream("stream1")
        self.assertEqual(len(self.mixer.active_streams), 1)
        self.assertIn("stream1", self.mixer.active_streams)
        
        # Check telemetry
        self.assertEqual(len(self.mock_te.events), 1)
        self.assertEqual(self.mock_te.events[0]['name'], 'audio_mixer_stream_added')

        self.mixer.remove_stream("stream1")
        self.assertEqual(len(self.mixer.active_streams), 0)

        # Check telemetry
        self.assertEqual(len(self.mock_te.events), 2)
        self.assertEqual(self.mock_te.events[1]['name'], 'audio_mixer_stream_removed')

    def test_mix_single_stream(self):
        audio_data = self._generate_sine_wave(440, 0.1, self.sample_rate, self.channels)
        self.mixer.add_stream("stream1", audio_buffer=audio_data)

        # Mix a 20ms frame
        frame = self.mixer.mix_audio_frames(20)
        frame_size = int(self.sample_rate * 0.02 * self.channels * self.sample_width)
        self.assertEqual(len(frame), frame_size)
        
        # The mixed frame should be identical to the input frame since there's only one
        self.assertEqual(frame, audio_data[:frame_size])

    def test_mix_multiple_streams(self):
        audio_data1 = self._generate_sine_wave(440, 0.1, self.sample_rate, self.channels)
        audio_data2 = self._generate_sine_wave(880, 0.1, self.sample_rate, self.channels)

        self.mixer.add_stream("stream1", audio_buffer=audio_data1)
        self.mixer.add_stream("stream2", audio_buffer=audio_data2)
        
        frame = self.mixer.mix_audio_frames(20)
        frame_size = int(self.sample_rate * 0.02 * self.channels * self.sample_width)

        # Manual mixing for verification
        arr1 = np.frombuffer(audio_data1[:frame_size], dtype=np.int16)
        arr2 = np.frombuffer(audio_data2[:frame_size], dtype=np.int16)
        expected_mix = np.clip(arr1 + arr2, -32768, 32767).astype(np.int16)

        mixed_arr = np.frombuffer(frame, dtype=np.int16)
        
        # Check if the mixed output is correct
        self.assertTrue(np.array_equal(mixed_arr, expected_mix))

    def test_mute_stream(self):
        audio_data1 = self._generate_sine_wave(440, 0.1, self.sample_rate, self.channels)
        audio_data2 = self._generate_sine_wave(880, 0.1, self.sample_rate, self.channels)

        self.mixer.add_stream("stream1", audio_buffer=audio_data1)
        self.mixer.add_stream("stream2", audio_buffer=audio_data2)

        # Mute stream2
        self.mixer.update_stream_settings("stream2", muted=True)
        
        frame = self.mixer.mix_audio_frames(20)
        frame_size = int(self.sample_rate * 0.02 * self.channels * self.sample_width)

        # The output should now only be from stream1
        self.assertEqual(frame, audio_data1[:frame_size])

    def test_volume_control(self):
        audio_data = self._generate_sine_wave(440, 0.1, self.sample_rate, self.channels)
        self.mixer.add_stream("stream1", audio_buffer=audio_data, volume=0.5)
        
        frame = self.mixer.mix_audio_frames(20)
        frame_size = int(self.sample_rate * 0.02 * self.channels * self.sample_width)

        original_arr = np.frombuffer(audio_data[:frame_size], dtype=np.int16)
        expected_arr = (original_arr * 0.5).astype(np.int16)

        mixed_arr = np.frombuffer(frame, dtype=np.int16)

        self.assertTrue(np.allclose(mixed_arr, expected_arr, atol=1)) # atol for rounding differences

    def test_mix_with_resampling_and_channel_conversion(self):
        # 24kHz stereo stream
        audio_data_stereo = self._generate_sine_wave(300, 0.1, 24000, 2)
        self.mixer.add_stream("stereo_stream", audio_buffer=audio_data_stereo, source_sample_rate=24000, source_channels=2)

        # Mix a 20ms frame, which should be converted to 16kHz mono
        frame = self.mixer.mix_audio_frames(20)
        expected_frame_size = int(self.sample_rate * 0.02 * self.channels * self.sample_width)
        self.assertEqual(len(frame), expected_frame_size)
        
        # A simple check: a non-silent frame should be produced
        self.assertNotEqual(frame, b'\x00' * expected_frame_size)

if __name__ == "__main__":
    unittest.main()