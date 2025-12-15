# src/telephony/audio_mixer.py

from typing import Dict, Any, List
import numpy as np
import audioop
import random

# Assuming these imports will be available from other modules
# from src.voice.processing.codec_transcoder import CodecTranscoder # For resampling/codec conversion
# from src.core.telemetry_emitter import TelemetryEmitter


class AudioMixer:
    """
    Mixes multiple incoming audio streams into a single outgoing stream.
    Supports basic volume control and ensures compatible audio formats.
    """
    def __init__(self, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2, transcoder_instance=None, telemetry_emitter_instance=None):
        """
        Initializes the AudioMixer.
        
        :param sample_rate: The target sample rate for the mixed output (Hz).
        :param channels: The target number of channels for the mixed output (1 for mono).
        :param sample_width: The target sample width in bytes (2 for 16-bit PCM).
        :param transcoder_instance: An optional CodecTranscoder instance for advanced conversions.
        :param telemetry_emitter_instance: An optional TelemetryEmitter instance.
        """
        self.target_sample_rate = sample_rate
        self.target_channels = channels
        self.target_sample_width = sample_width
        self.transcoder = transcoder_instance
        self.telemetry = telemetry_emitter_instance
        
        # Stores active audio streams: {stream_id: {"audio_buffer": bytes, "volume": float, "muted": bool, "source_sr": int, "source_channels": int}}
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        
        # Buffer for the mixed output
        self._mixed_output_buffer = b''
        
        print("✅ AudioMixer initialized.")

    def add_stream(self, stream_id: str, audio_buffer: bytes = b'', volume: float = 1.0, muted: bool = False, source_sample_rate: int = 16000, source_channels: int = 1):
        """
        Adds a new audio stream to be mixed.
        
        :param stream_id: A unique identifier for this stream.
        :param audio_buffer: Initial audio data for the stream.
        :param volume: Volume level for this stream (0.0 to 1.0).
        :param muted: If True, this stream will not be mixed.
        :param source_sample_rate: The original sample rate of this stream.
        :param source_channels: The original number of channels of this stream.
        """
        self.active_streams[stream_id] = {
            "audio_buffer": audio_buffer,
            "volume": max(0.0, min(1.0, volume)), # Clamp volume
            "muted": muted,
            "source_sr": source_sample_rate,
            "source_channels": source_channels
        }
        print(f"Added audio stream: {stream_id}")
        if self.telemetry:
            self.telemetry.emit_event("audio_mixer_stream_added", {"stream_id": stream_id})

    def remove_stream(self, stream_id: str):
        """
        Removes an audio stream from the mixer.
        
        :param stream_id: The unique identifier of the stream to remove.
        """
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
            print(f"Removed audio stream: {stream_id}")
            if self.telemetry:
                self.telemetry.emit_event("audio_mixer_stream_removed", {"stream_id": stream_id})
        else:
            print(f"Stream {stream_id} not found.")

    def update_stream_settings(self, stream_id: str, volume: float = None, muted: bool = None):
        """
        Updates settings for an existing audio stream.
        """
        stream_info = self.active_streams.get(stream_id)
        if stream_info:
            if volume is not None:
                stream_info["volume"] = max(0.0, min(1.0, volume))
            if muted is not None:
                stream_info["muted"] = muted
            print(f"Updated settings for stream {stream_id}: Volume={stream_info['volume']}, Muted={stream_info['muted']}")
        else:
            print(f"Stream {stream_id} not found.")

    def feed_audio_to_stream(self, stream_id: str, audio_data: bytes):
        """
        Adds audio data to a specific stream's buffer.
        """
        stream_info = self.active_streams.get(stream_id)
        if stream_info:
            stream_info["audio_buffer"] += audio_data
        else:
            print(f"Cannot feed audio to non-existent stream: {stream_id}")

    def mix_audio_frames(self, frame_duration_ms: int = 20) -> bytes:
        """
        Mixes audio from all active streams and returns a single output frame.
        
        :param frame_duration_ms: The duration of the output audio frame in milliseconds.
        :return: A bytes object containing the mixed audio frame (16-bit PCM).
        """
        frame_size_samples = int(self.target_sample_rate * (frame_duration_ms / 1000.0))
        frame_size_bytes = frame_size_samples * self.target_channels * self.target_sample_width
        
        # If we already have enough mixed audio, return from buffer
        if len(self._mixed_output_buffer) >= frame_size_bytes:
            frame = self._mixed_output_buffer[:frame_size_bytes]
            self._mixed_output_buffer = self._mixed_output_buffer[frame_size_bytes:]
            return frame

        # Prepare a zero-initialized buffer for mixing
        mixed_frame_np = np.zeros(frame_size_samples * self.target_channels, dtype=np.int16)

        for stream_id, stream_info in list(self.active_streams.items()): # Iterate over copy as stream might be removed
            if stream_info["muted"]:
                continue

            # Ensure enough audio is available in buffer
            # Calculate required bytes for source stream's frame duration
            source_frame_size_samples = int(stream_info["source_sr"] * (frame_duration_ms / 1000.0))
            source_frame_size_bytes = source_frame_size_samples * stream_info["source_channels"] * self.target_sample_width
            
            if len(stream_info["audio_buffer"]) < source_frame_size_bytes:
                # Not enough data for a full frame from this stream, skip for now.
                continue

            # Extract current frame from stream's buffer
            stream_frame_bytes = stream_info["audio_buffer"][:source_frame_size_bytes]
            stream_info["audio_buffer"] = stream_info["audio_buffer"][source_frame_size_bytes:]

            # Convert to target format (resampling, channel conversion if needed)
            processed_stream_frame = self._process_audio_frame(
                stream_frame_bytes,
                stream_info["source_sr"], stream_info["source_channels"]
            )
            
            # Convert to numpy array for mixing
            stream_frame_np = np.frombuffer(processed_stream_frame, dtype=np.int16)
            
            # Apply volume
            stream_frame_np = (stream_frame_np * stream_info["volume"]).astype(np.int16)

            # Mix (add) to the main buffer
            mixed_frame_np = mixed_frame_np + stream_frame_np[:mixed_frame_np.size]
        
        # Clip to 16-bit range to prevent overflow distortion
        mixed_frame_np = np.clip(mixed_frame_np, -32768, 32767).astype(np.int16)
        
        # Store in internal buffer
        self._mixed_output_buffer += mixed_frame_np.tobytes()

        # If we have enough after mixing, return the frame
        if len(self._mixed_output_buffer) >= frame_size_bytes:
            frame = self._mixed_output_buffer[:frame_size_bytes]
            self._mixed_output_buffer = self._mixed_output_buffer[frame_size_bytes:]
            return frame
        else:
            return b'\x00' * frame_size_bytes # Return silence if not enough for a full frame yet

    def _process_audio_frame(self, audio_data: bytes, source_sr: int, source_channels: int) -> bytes:
        """
        Converts an audio frame to the mixer's target format (sample rate, channels).
        """
        # 1. Channel conversion
        if source_channels != self.target_channels:
            if self.transcoder:
                audio_data = self.transcoder.convert_channels(audio_data, source_channels, self.target_channels, self.target_sample_width)
            elif source_channels == 2 and self.target_channels == 1:
                audio_data = audioop.tomono(audio_data, self.target_sample_width, 1, 1) # Stereo to Mono
            elif source_channels == 1 and self.target_channels == 2:
                audio_data = audioop.tostereo(audio_data, self.target_sample_width, 1, 1) # Mono to Stereo
            else:
                # Fallback or error if transcoder not available and complex channel change
                raise ValueError(f"Unsupported channel conversion: {source_channels} to {self.target_channels} without transcoder.")

        # 2. Resampling
        if source_sr != self.target_sample_rate:
            if self.transcoder:
                audio_data = self.transcoder.resample(audio_data, source_sr, self.target_sample_rate, self.target_sample_width)
            else:
                audio_data, _ = audioop.ratecv(audio_data, self.target_sample_width, self.target_channels, source_sr, self.target_sample_rate, None)
        
        return audio_data

# Example Usage
if __name__ == "__main__":
    
    # --- Mock CodecTranscoder (from src/voice/processing/codec_transcoder.py) ---
    class MockCodecTranscoder:
        def resample(self, audio_data, in_rate, out_rate, sample_width):
            if in_rate == out_rate: return audio_data
            # Simulate resampling by just returning a different length of data
            factor = out_rate / in_rate
            return audio_data * int(factor) # Very crude simulation
        def convert_channels(self, audio_data, in_channels, out_channels, sample_width):
            if in_channels == out_channels: return audio_data
            if in_channels == 2 and out_channels == 1: # Stereo to mono
                return audio_data[::2] # Half the data
            if in_channels == 1 and out_channels == 2: # Mono to stereo
                return audio_data * 2 # Double the data
            return audio_data # Default
    
    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_transcoder = MockCodecTranscoder()
    mock_te = MockTelemetryEmitter()
    
    mixer = AudioMixer(sample_rate=16000, channels=1, transcoder_instance=mock_transcoder, telemetry_emitter_instance=mock_te)

    # --- Test 1: Add and mix multiple streams ---
    print("\n--- Test 1: Add and mix multiple streams ---")
    
    # User's voice (e.g., from STT input)
    # 1 second of 16kHz mono 16-bit PCM sine wave
    sample_rate_user = 16000
    duration_user = 1 # seconds
    frequency_user = 440 # Hz (A4 note)
    t_user = np.linspace(0, duration_user, int(sample_rate_user * duration_user), endpoint=False)
    audio_user = (np.sin(2 * np.pi * frequency_user * t_user) * 10000).astype(np.int16).tobytes()
    
    mixer.add_stream("user_voice", audio_user, volume=0.8, source_sample_rate=sample_rate_user, source_channels=1)

    # AI's TTS output
    sample_rate_ai = 24000 # Different sample rate
    duration_ai = 1 # seconds
    frequency_ai = 660 # Hz (E5 note)
    t_ai = np.linspace(0, duration_ai, int(sample_rate_ai * duration_ai), endpoint=False)
    audio_ai = (np.sin(2 * np.pi * frequency_ai * t_ai) * 10000).astype(np.int16).tobytes()
    
    mixer.add_stream("ai_tts", audio_ai, volume=0.6, source_sample_rate=sample_rate_ai, source_channels=1)

    # Background music (stereo, 48kHz)
    sample_rate_music = 48000
    duration_music = 1 # seconds
    frequency_music_left = 110 # Hz (A2)
    frequency_music_right = 165 # Hz (E3)
    t_music = np.linspace(0, duration_music, int(sample_rate_music * duration_music), endpoint=False)
    audio_music_left = (np.sin(2 * np.pi * frequency_music_left * t_music) * 5000).astype(np.int16)
    audio_music_right = (np.sin(2 * np.pi * frequency_music_right * t_music) * 5000).astype(np.int16)
    audio_music = np.empty((audio_music_left.size + audio_music_right.size,), dtype=np.int16)
    audio_music[0::2] = audio_music_left
    audio_music[1::2] = audio_music_right
    audio_music_bytes = audio_music.tobytes()

    mixer.add_stream("bg_music", audio_music_bytes, volume=0.2, source_sample_rate=sample_rate_music, source_channels=2)

    # Mix 10 frames (200ms of audio)
    for i in range(10):
        mixed_frame = mixer.mix_audio_frames(frame_duration_ms=20)
        print(f"Mixed frame {i+1}: {len(mixed_frame)} bytes")
        if mixed_frame == b'\x00' * (16000 * 1 * 2 * 20 // 1000): # Check if silence (no more data)
             # In a real system, you'd feed new audio to streams as needed.
            mixer.feed_audio_to_stream("user_voice", audio_user) # Keep feeding same audio for demo
            mixer.feed_audio_to_stream("ai_tts", audio_ai)
            mixer.feed_audio_to_stream("bg_music", audio_music_bytes)
            
        asyncio.run(asyncio.sleep(0.01)) # Simulate real-time processing

    # --- Test 2: Mute a stream ---
    print("\n--- Test 2: Mute a stream ---")
    mixer.update_stream_settings("bg_music", muted=True)
    mixed_frame_muted = mixer.mix_audio_frames(frame_duration_ms=20)
    print(f"Mixed frame after muting music: {len(mixed_frame_muted)} bytes")

    # --- Test 3: Remove a stream ---
    print("\n--- Test 3: Remove a stream ---")
    mixer.remove_stream("ai_tts")
    mixed_frame_removed = mixer.mix_audio_frames(frame_duration_ms=20)
    print(f"Mixed frame after removing AI TTS: {len(mixed_frame_removed)} bytes")

    print("\nAudioMixer simulation complete.")
