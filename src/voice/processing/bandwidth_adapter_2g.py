import logging
import time
from enum import Enum, auto
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class NetworkQuality(Enum):
    EXCELLENT = auto()
    GOOD = auto()
    MEDIUM = auto()
    POOR = auto() # Equivalent to 2G/EDGE conditions

class BandwidthAdapter2G:
    """
    Adapts system behavior based on detected network quality to maintain
    usability, especially in low-bandwidth environments like 2G.
    """
    def __init__(self, 
                 initial_quality: NetworkQuality = NetworkQuality.EXCELLENT,
                 quality_thresholds: Optional[Dict[str, float]] = None,
                 latency_monitor_window: int = 5):
        self.current_quality = initial_quality
        self.last_adaptation_time = time.time()
        self.latency_monitor_window = latency_monitor_window # seconds for average latency
        self.recent_latencies = [] # Stores (timestamp, latency_ms)
        self.recent_packet_losses = [] # Stores (timestamp, packet_loss_percent)

        # Customizable thresholds for quality degradation
        self.quality_thresholds = quality_thresholds if quality_thresholds else {
            "poor_latency_ms": 500,    # Latency > 500ms for poor
            "medium_latency_ms": 200,  # Latency > 200ms for medium
            "poor_packet_loss_pct": 10, # Packet loss > 10% for poor
            "medium_packet_loss_pct": 3 # Packet loss > 3% for medium
        }
        logger.info(f"BandwidthAdapter2G initialized with initial quality: {self.current_quality.name}")

    def update_network_metrics(self, latency_ms: Optional[float] = None, packet_loss_pct: Optional[float] = None):
        """
        Updates the internal network metrics and re-evaluates network quality.
        """
        current_time = time.time()
        
        if latency_ms is not None:
            self.recent_latencies.append((current_time, latency_ms))
        if packet_loss_pct is not None:
            self.recent_packet_losses.append((current_time, packet_loss_pct))

        # Remove old metrics outside the monitoring window
        self.recent_latencies = [(ts, lat) for ts, lat in self.recent_latencies if current_time - ts <= self.latency_monitor_window]
        self.recent_packet_losses = [(ts, pl) for ts, pl in self.recent_packet_losses if current_time - ts <= self.latency_monitor_window]

        self._evaluate_network_quality()

    def _evaluate_network_quality(self):
        """
        Determines the current network quality based on accumulated metrics.
        """
        avg_latency = sum([lat for _, lat in self.recent_latencies]) / len(self.recent_latencies) if self.recent_latencies else 0
        avg_packet_loss = sum([pl for _, pl in self.recent_packet_losses]) / len(self.recent_packet_losses) if self.recent_packet_losses else 0

        new_quality = NetworkQuality.EXCELLENT
        if avg_latency > self.quality_thresholds["poor_latency_ms"] or avg_packet_loss > self.quality_thresholds["poor_packet_loss_pct"]:
            new_quality = NetworkQuality.POOR
        elif avg_latency > self.quality_thresholds["medium_latency_ms"] or avg_packet_loss > self.quality_thresholds["medium_packet_loss_pct"]:
            new_quality = NetworkQuality.MEDIUM
        elif avg_latency == 0 and avg_packet_loss == 0: # No data or perfect connection
            new_quality = NetworkQuality.EXCELLENT
        else:
            new_quality = NetworkQuality.GOOD

        if new_quality != self.current_quality:
            self.current_quality = new_quality
            self.last_adaptation_time = time.time()
            self._apply_adaptation()
            logger.warning(f"Network quality changed to {self.current_quality.name} (Latency: {avg_latency:.2f}ms, Packet Loss: {avg_packet_loss:.2f}%)")

    def _apply_adaptation(self):
        """
        Applies system-wide adaptations based on the current network quality.
        These are conceptual actions that would interact with other modules.
        """
        if self.current_quality == NetworkQuality.POOR:
            logger.warning("Applying POOR network adaptations: lower audio quality, shorter responses, simpler TTS.")
            # Example actions:
            # self.codec_manager.set_preferred_codec(AudioCodec.G729)
            # self.tts_manager.set_voice_profile("simple_fast")
            # self.response_generator.set_response_length_limit(50)
            # self.stt_streaming_processor.disable_interim_transcripts()
            self._notify_user("Connection is poor, switching to low-bandwidth mode.")
        elif self.current_quality == NetworkQuality.MEDIUM:
            logger.info("Applying MEDIUM network adaptations: reduced audio quality, slightly shorter responses.")
            # self.codec_manager.set_preferred_codec(AudioCodec.PCMU)
            # self.tts_manager.set_voice_profile("standard")
            # self.response_generator.set_response_length_limit(100)
            self._notify_user("Connection is unstable, adjusting for better performance.")
        else: # GOOD or EXCELLENT
            logger.info("Applying HIGH network adaptations: optimal audio quality, full features.")
            # self.codec_manager.set_preferred_codec(AudioCodec.OPUS)
            # self.tts_manager.set_voice_profile("realistic")
            # self.response_generator.set_response_length_limit(None)
            # self.stt_streaming_processor.enable_interim_transcripts()
            if self.current_quality == NetworkQuality.GOOD and time.time() - self.last_adaptation_time > 60: # Avoid frequent notifications
                 self._notify_user("Connection quality improved.")


    def _notify_user(self, message: str):
        """
        Sends a notification to the user about network quality changes.
        This would integrate with TTS or data channel.
        """
        logger.info(f"User Notification: {message}")
        # Example:
        # self.tts_manager.speak(message, interrupt_current_speech=True)
        # self.webrtc_server.send_data_channel_message(message)

    def get_current_adaptation_settings(self) -> Dict[str, Any]:
        """
        Returns a dictionary of current recommended settings based on bandwidth.
        """
        if self.current_quality == NetworkQuality.POOR:
            return {
                "audio_sample_rate": 8000,
                "audio_bitrate_kbps": 16,
                "tts_voice_profile": "simple_fast",
                "max_response_length_words": 50,
                "interim_transcripts_enabled": False
            }
        elif self.current_quality == NetworkQuality.MEDIUM:
            return {
                "audio_sample_rate": 16000,
                "audio_bitrate_kbps": 64,
                "tts_voice_profile": "standard",
                "max_response_length_words": 100,
                "interim_transcripts_enabled": True
            }
        else: # GOOD or EXCELLENT
            return {
                "audio_sample_rate": 48000,
                "audio_bitrate_kbps": 128,
                "tts_voice_profile": "realistic",
                "max_response_length_words": None,
                "interim_transcripts_enabled": True
            }

    def get_network_quality(self) -> NetworkQuality:
        return self.current_quality

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    adapter = BandwidthAdapter2G()

    print("\n--- Initial State ---")
    print(f"Current Quality: {adapter.get_network_quality().name}")
    print(f"Current Settings: {adapter.get_current_adaptation_settings()}")

    print("\n--- Simulate Excellent Connection ---")
    adapter.update_network_metrics(latency_ms=50, packet_loss_pct=0.1)
    print(f"Current Quality: {adapter.get_network_quality().name}")
    print(f"Current Settings: {adapter.get_current_adaptation_settings()}")

    print("\n--- Simulate Medium Connection ---")
    adapter.update_network_metrics(latency_ms=250, packet_loss_pct=2.5)
    print(f"Current Quality: {adapter.get_network_quality().name}")
    print(f"Current Settings: {adapter.get_current_adaptation_settings()}")

    print("\n--- Simulate Poor Connection (2G-like) ---")
    adapter.update_network_metrics(latency_ms=600, packet_loss_pct=12.0)
    print(f"Current Quality: {adapter.get_network_quality().name}")
    print(f"Current Settings: {adapter.get_current_adaptation_settings()}")
    
    print("\n--- Simulate Fluctuation (brief improvement) ---")
    adapter.update_network_metrics(latency_ms=100, packet_loss_pct=1.0)
    print(f"Current Quality: {adapter.get_network_quality().name}")
    print(f"Current Settings: {adapter.get_current_adaptation_settings()}")

    print("\n--- Simulate Return to Poor ---")
    adapter.update_network_metrics(latency_ms=700, packet_loss_pct=15.0)
    print(f"Current Quality: {adapter.get_network_quality().name}")
    print(f"Current Settings: {adapter.get_current_adaptation_settings()}")
