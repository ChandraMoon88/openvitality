import subprocess
import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)

class AudioCodec(Enum):
    PCMU = "PCMU"  # G.711 μ-law
    PCMA = "PCMA"  # G.711 A-law
    G729 = "G729"  # Low bandwidth codec
    OPUS = "OPUS"  # Modern, adaptive
    PCM_S16LE = "PCM_S16LE" # Raw 16-bit signed little-endian PCM

class CodecManager:
    """
    Manages audio codec negotiation and transcoding for telephony.
    """
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._check_ffmpeg_availability()
        self.supported_codecs = {
            AudioCodec.PCMU: {"name": "pcm_mulaw", "sample_rate": 8000, "channels": 1, "bit_rate": 64},
            AudioCodec.PCMA: {"name": "pcm_alaw", "sample_rate": 8000, "channels": 1, "bit_rate": 64},
            # G.729 typically requires licensing for actual encoding/decoding, 
            # this is a placeholder. For open-source, often needs specific libraries.
            AudioCodec.G729: {"name": "g729", "sample_rate": 8000, "channels": 1, "bit_rate": 8},
            AudioCodec.OPUS: {"name": "libopus", "sample_rate": 48000, "channels": 1, "bit_rate": "auto"},
            AudioCodec.PCM_S16LE: {"name": "pcm_s16le", "sample_rate": 16000, "channels": 1, "bit_rate": "auto"},
        }
        logger.info("CodecManager initialized. Supported codecs: %s", [c.name for c in self.supported_codecs.keys()])

    def _check_ffmpeg_availability(self):
        """Checks if ffmpeg is available in the system path."""
        try:
            subprocess.run([self.ffmpeg_path, "-version"], check=True, capture_output=True)
            logger.info(f"FFmpeg found at {self.ffmpeg_path}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error(f"FFmpeg not found at '{self.ffmpeg_path}'. Transcoding will not be available. "
                         "Please install FFmpeg or provide the correct path.")
            self.ffmpeg_path = None # Disable ffmpeg functionality

    def get_codec_info(self, codec: AudioCodec) -> dict | None:
        """Returns information about a specific codec."""
        return self.supported_codecs.get(codec)

    def negotiate_codec(self, offered_codecs: list[AudioCodec], preferred_codecs: list[AudioCodec] = None) -> AudioCodec | None:
        """
        Negotiates the best common codec between offered and preferred lists.
        Prioritizes preferred codecs if provided.
        """
        if preferred_codecs is None:
            # Default preference: OPUS > PCMU > PCMA > G729 (assuming quality/bandwidth)
            preferred_codecs = [AudioCodec.OPUS, AudioCodec.PCMU, AudioCodec.PCMA, AudioCodec.G729]
        
        for pref_codec in preferred_codecs:
            if pref_codec in offered_codecs and pref_codec in self.supported_codecs:
                logger.info(f"Negotiated codec: {pref_codec.name}")
                return pref_codec
        
        logger.warning("No common supported codec found between offered and preferred lists.")
        return None

    def transcode(self, input_audio_data: bytes, input_format: AudioCodec,
                  output_format: AudioCodec, output_sample_rate: int = None,
                  output_channels: int = None) -> bytes:
        """
        Transcodes audio data from one format to another using FFmpeg.

        Args:
            input_audio_data (bytes): The raw audio data to transcode.
            input_format (AudioCodec): The current format of the input audio data.
            output_format (AudioCodec): The desired output format.
            output_sample_rate (int): Desired output sample rate. If None, uses default for output_format.
            output_channels (int): Desired output channels. If None, uses default for output_format.

        Returns:
            bytes: The transcoded audio data.

        Raises:
            ValueError: If FFmpeg is not available or transcoding fails.
        """
        if not self.ffmpeg_path:
            raise ValueError("FFmpeg is not available for transcoding.")

        input_info = self.get_codec_info(input_format)
        output_info = self.get_codec_info(output_format)

        if not input_info or not output_info:
            raise ValueError("Invalid input or output codec specified.")

        cmd = [
            self.ffmpeg_path,
            "-f", input_info["name"],
            "-ar", str(input_info["sample_rate"]),
            "-ac", str(input_info["channels"]),
            "-i", "pipe:0",  # Read input from stdin
            "-f", output_info["name"],
            "-ar", str(output_sample_rate if output_sample_rate else output_info["sample_rate"]),
            "-ac", str(output_channels if output_channels else output_info["channels"]),
            "-y", # Overwrite output files without asking
            "pipe:1"  # Write output to stdout
        ]
        
        # Specific options for certain codecs
        if output_format == AudioCodec.OPUS:
            # Opus often prefers 48kHz, but we can specify if needed
            cmd.extend(["-acodec", "libopus"])
            if output_sample_rate is None:
                cmd[cmd.index("-ar") + 1] = str(48000) # Default Opus to 48kHz if not specified
        elif output_format == AudioCodec.G729:
            cmd.extend(["-acodec", "libg729"]) # Requires ffmpeg compiled with libg729

        logger.debug(f"FFmpeg transcode command: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        output_data, stderr_data = process.communicate(input=input_audio_data)

        if process.returncode != 0:
            error_message = stderr_data.decode(errors='ignore')
            logger.error(f"FFmpeg transcoding failed (Exit code: {process.returncode}): {error_message}")
            raise ValueError(f"Transcoding failed: {error_message}")

        logger.info(f"Transcoded audio from {input_format.name} to {output_format.name} "
                    f"(Input size: {len(input_audio_data)} bytes, Output size: {len(output_data)} bytes)")
        return output_data

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    codec_manager = CodecManager()

    # Example 1: Negotiate codec
    offered = [AudioCodec.G729, AudioCodec.PCMA, AudioCodec.OPUS]
    preferred = [AudioCodec.OPUS, AudioCodec.PCMU]
    negotiated = codec_manager.negotiate_codec(offered, preferred)
    if negotiated:
        print(f"Negotiated Codec: {negotiated.name}")
    else:
        print("No suitable codec found.")

    # Example 2: Transcode PCMU (mu-law) to PCM_S16LE (raw linear PCM)
    # This example requires actual audio data and a working ffmpeg installation.
    try:
        # Create dummy PCMU audio data (simple sine wave)
        # 1 second of 8kHz mu-law silence
        dummy_pcmu_data = b'\xff' * 8000 # mu-law silence is often 0xFF

        print(f"\nAttempting to transcode {AudioCodec.PCMU.name} to {AudioCodec.PCM_S16LE.name}...")
        
        # Transcode to 16kHz 16-bit PCM_S16LE
        output_pcm_data = codec_manager.transcode(
            input_audio_data=dummy_pcmu_data,
            input_format=AudioCodec.PCMU,
            output_format=AudioCodec.PCM_S16LE,
            output_sample_rate=16000,
            output_channels=1
        )
        print(f"Transcoding successful. Output PCM data size: {len(output_pcm_data)} bytes.")

        # You can save this to a file to verify
        # with open("output.pcm", "wb") as f:
        #     f.write(output_pcm_data)
        # print("Saved transcoded PCM data to output.pcm")

    except ValueError as e:
        print(f"Transcoding example failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during transcoding example: {e}")

    # Example 3: Transcode PCM_S16LE to PCMU
    try:
        # Assuming output_pcm_data from previous step
        if 'output_pcm_data' in locals() and output_pcm_data:
            print(f"\nAttempting to transcode {AudioCodec.PCM_S16LE.name} back to {AudioCodec.PCMU.name}...")
            # Transcode back to 8kHz 8-bit PCMU
            output_pcmu_data = codec_manager.transcode(
                input_audio_data=output_pcm_data,
                input_format=AudioCodec.PCM_S16LE,
                output_format=AudioCodec.PCMU,
                output_sample_rate=8000,
                output_channels=1
            )
            print(f"Transcoding successful. Output PCMU data size: {len(output_pcmu_data)} bytes.")
    except ValueError as e:
        print(f"Transcoding example failed: {e}")
