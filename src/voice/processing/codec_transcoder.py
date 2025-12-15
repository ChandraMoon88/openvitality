import subprocess
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class CodecTranscoder:
    """
    Provides robust audio transcoding functionalities using FFmpeg.
    Supports decoding to raw PCM, encoding from PCM to various formats,
    resampling, and channel conversion.
    """
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._check_ffmpeg_availability()

    def _check_ffmpeg_availability(self):
        """Checks if ffmpeg is available in the system path."""
        try:
            subprocess.run([self.ffmpeg_path, "-version"], check=True, capture_output=True)
            logger.info(f"FFmpeg found at {self.ffmpeg_path}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error(f"FFmpeg not found at '{self.ffmpeg_path}'. Transcoding will not be available. "
                         "Please install FFmpeg or provide the correct path.")
            self.ffmpeg_path = None # Disable ffmpeg functionality

    def transcode_audio(
                        self,
                        input_data: bytes,
                        input_format: str, # e.g., "s16le", "mulaw", "opus"
                        input_sample_rate: int,
                        input_channels: int,
                        output_format: str, # e.g., "s16le", "mulaw", "opus"
                        output_sample_rate: Optional[int] = None,
                        output_channels: Optional[int] = None,
                        output_codec: Optional[str] = None # e.g., "pcm_s16le", "pcm_mulaw", "libopus"
                        ) -> bytes:
        """
        Transcodes raw audio data from one format to another.

        Args:
            input_data (bytes): The raw audio bytes to transcode.
            input_format (str): Input format descriptor (e.g., "s16le", "mulaw").
            input_sample_rate (int): Input sample rate (e.g., 8000, 16000).
            input_channels (int): Input number of channels (e.g., 1 for mono).
            output_format (str): Output format descriptor (e.g., "s16le", "mulaw").
            output_sample_rate (Optional[int]): Desired output sample rate. If None, keep input.
            output_channels (Optional[int]): Desired output channels. If None, keep input.
            output_codec (Optional[str]): FFmpeg audio codec name (e.g., "pcm_s16le", "libopus").
                                          If None, FFmpeg will guess based on output_format.

        Returns:
            bytes: The transcoded audio data.

        Raises:
            ValueError: If FFmpeg is not available or transcoding fails.
        """
        if not self.ffmpeg_path:
            raise ValueError("FFmpeg is not available for transcoding.")
        
        # Determine FFmpeg input format string based on common telephony codecs
        ffmpeg_input_format = input_format
        if input_format == "s16le":
            ffmpeg_input_format = "s16le"
        elif input_format == "mulaw":
            ffmpeg_input_format = "mulaw"
        elif input_format == "alaw":
            ffmpeg_input_format = "alaw"
        elif input_format == "opus":
            # For opus input without a container, we usually need to specify the codec
            # This might be tricky if input_data is just raw opus frames without an OGG container.
            # For robustness, consider if you always receive opus within a container.
            ffmpeg_input_format = "opus" # ffmpeg can usually auto-detect this
            output_codec = output_codec if output_codec else "pcm_s16le" # Default to PCM output

        cmd = [
            self.ffmpeg_path,
            "-f", ffmpeg_input_format,
            "-ar", str(input_sample_rate),
            "-ac", str(input_channels),
            "-i", "pipe:0",  # Read input from stdin
        ]

        if output_codec:
            cmd.extend(["-acodec", output_codec])
        
        if output_sample_rate:
            cmd.extend(["-ar", str(output_sample_rate)])
        if output_channels:
            cmd.extend(["-ac", str(output_channels)])

        cmd.extend([
            "-f", output_format,
            "-y", # Overwrite output files without asking
            "pipe:1"  # Write output to stdout
        ])
        
        logger.debug(f"FFmpeg transcode command: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        output_data, stderr_data = process.communicate(input=input_data)

        if process.returncode != 0:
            error_message = stderr_data.decode(errors='ignore')
            logger.error(f"FFmpeg transcoding failed (Exit code: {process.returncode}): {error_message}")
            raise ValueError(f"Transcoding failed: {error_message}")

        logger.info(f"Transcoded audio from '{input_format}' ({input_sample_rate}Hz, {input_channels}ch) "
                    f"to '{output_format}' ({output_sample_rate if output_sample_rate else input_sample_rate}Hz, "
                    f"{output_channels if output_channels else input_channels}ch). "
                    f"Input size: {len(input_data)} bytes, Output size: {len(output_data)} bytes.")
        return output_data

    def decode_to_pcm_s16le(
                            self,
                            input_data: bytes,
                            input_format: str,
                            input_sample_rate: int,
                            input_channels: int,
                            target_sample_rate: int = 16000,
                            target_channels: int = 1) -> bytes:
        """
        Decodes arbitrary audio input to 16-bit signed little-endian PCM (s16le).
        This is a common intermediate format for STT engines.
        """
        return self.transcode_audio(
            input_data=input_data,
            input_format=input_format,
            input_sample_rate=input_sample_rate,
            input_channels=input_channels,
            output_format="s16le",
            output_sample_rate=target_sample_rate,
            output_channels=target_channels,
            output_codec="pcm_s16le"
        )

    def encode_from_pcm_s16le(
                                self,
                                pcm_data: bytes,
                                pcm_sample_rate: int,
                                pcm_channels: int,
                                output_format: str,
                                output_sample_rate: Optional[int] = None,
                                output_channels: Optional[int] = None,
                                output_codec: Optional[str] = None) -> bytes:
        """
        Encodes 16-bit signed little-endian PCM (s16le) to a target audio format.
        """
        return self.transcode_audio(
            input_data=pcm_data,
            input_format="s16le",
            input_sample_rate=pcm_sample_rate,
            input_channels=pcm_channels,
            output_format=output_format,
            output_sample_rate=output_sample_rate,
            output_channels=output_channels,
            output_codec=output_codec
        )


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    transcoder = CodecTranscoder()

    # --- Example 1: Decode mu-law (from SIP) to 16kHz mono PCM (for STT) ---
    print("\n--- Decoding mu-law to PCM (for STT) ---")
    # Simulate 1 second of 8kHz mono mu-law audio (8000 bytes)
    dummy_mulaw_data = b'\xff\x01\xfe\x02' * 2000 # Example mu-law data
    try:
        pcm_data_16k = transcoder.decode_to_pcm_s16le(
            input_data=dummy_mulaw_data,
            input_format="mulaw",
            input_sample_rate=8000,
            input_channels=1,
            target_sample_rate=16000,
            target_channels=1
        )
        print(f"Decoded mu-law to PCM_S16LE. Output size: {len(pcm_data_16k)} bytes.")
        # Expected size for 1s of 16kHz mono 16-bit PCM: 16000 * 1 * 2 = 32000 bytes
        assert len(pcm_data_16k) == 32000
    except ValueError as e:
        print(f"Decode example failed: {e}")

    # --- Example 2: Encode 16kHz mono PCM (from TTS) to mu-law (for SIP) ---
    print("\n--- Encoding PCM to mu-law (for SIP) ---")
    # Simulate 1 second of 16kHz mono 16-bit PCM audio (32000 bytes)
    dummy_pcm_data_16k = b'\x00\x00\x01\x00\x02\x00\x03\x00' * 4000 # Example PCM data
    try:
        mulaw_data_8k = transcoder.encode_from_pcm_s16le(
            pcm_data=dummy_pcm_data_16k,
            pcm_sample_rate=16000,
            pcm_channels=1,
            output_format="mulaw",
            output_sample_rate=8000,
            output_channels=1,
            output_codec="pcm_mulaw"
        )
        print(f"Encoded PCM_S16LE to mu-law. Output size: {len(mulaw_data_8k)} bytes.")
        # Expected size for 1s of 8kHz mono mu-law: 8000 * 1 * 1 = 8000 bytes
        assert len(mulaw_data_8k) == 8000
    except ValueError as e:
        print(f"Encode example failed: {e}")

    # --- Example 3: Resample 8kHz PCM to 16kHz PCM ---
    print("\n--- Resampling PCM ---")
    dummy_pcm_data_8k = b'\x00\x00\x01\x00\x02\x00\x03\x00' * 2000 # 1s 8kHz mono 16-bit PCM
    try:
        resampled_pcm = transcoder.transcode_audio(
            input_data=dummy_pcm_data_8k,
            input_format="s16le",
            input_sample_rate=8000,
            input_channels=1,
            output_format="s16le",
            output_sample_rate=16000,
            output_channels=1,
            output_codec="pcm_s16le"
        )
        print(f"Resampled 8kHz PCM to 16kHz PCM. Output size: {len(resampled_pcm)} bytes.")
        assert len(resampled_pcm) == 32000 # 16000 * 1 * 2
    except ValueError as e:
        print(f"Resample example failed: {e}")

    # --- Example 4: Convert Stereo to Mono ---
    print("\n--- Stereo to Mono Conversion ---")
    # 1s of 16kHz stereo 16-bit PCM (64000 bytes)
    dummy_pcm_data_stereo = b'\x00\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05\x00\x06\x00\x07\x00' * 4000
    try:
        mono_pcm = transcoder.transcode_audio(
            input_data=dummy_pcm_data_stereo,
            input_format="s16le",
            input_sample_rate=16000,
            input_channels=2,
            output_format="s16le",
            output_sample_rate=16000,
            output_channels=1,
            output_codec="pcm_s16le"
        )
        print(f"Converted stereo PCM to mono PCM. Output size: {len(mono_pcm)} bytes.")
        assert len(mono_pcm) == 32000 # 16000 * 1 * 2
    except ValueError as e:
        print(f"Stereo to mono example failed: {e}")
