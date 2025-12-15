# src/intelligence/anomaly_detector.py

from collections import deque
from typing import Dict, Any, List
import statistics
import time

# Assuming this import will be available from other modules
# from src.core.telemetry_emitter import TelemetryEmitter

class AnomalyDetector:
    """
    Detects unusual patterns in user behavior, system performance, or API usage.
    Uses simple statistical methods to identify deviations from normal operation.
    """
    def __init__(self, telemetry_emitter_instance, window_size: int = 100):
        """
        Initializes the AnomalyDetector.
        
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance for alerting.
        :param window_size: The number of data points to keep in the rolling window for statistics.
        """
        self.telemetry = telemetry_emitter_instance
        self.window_size = window_size
        
        # Stores historical data for various metrics
        self.metrics_data: Dict[str, deque[float]] = {}
        self.thresholds: Dict[str, Dict[str, float]] = {
            "call_duration": {"std_multiplier": 3, "min_threshold": 10}, # Flag if > 3 std deviations from mean, and > 10s
            "error_rate": {"threshold": 0.05}, # Flag if error rate > 5%
            "unusual_intent_count": {"std_multiplier": 2, "min_threshold": 5}, # Flag if count > 2 std deviations from mean and > 5 occurrences
            "api_latency_ms": {"std_multiplier": 3, "min_latency": 1000}, # Flag if > 3 std deviations and > 1000ms
        }
        print("✅ AnomalyDetector initialized.")

    def add_metric_data(self, metric_name: str, value: float):
        """
        Adds a new data point for a given metric.
        
        :param metric_name: The name of the metric (e.g., "call_duration", "error_rate").
        :param value: The value of the metric.
        """
        if metric_name not in self.metrics_data:
            self.metrics_data[metric_name] = deque(maxlen=self.window_size)
        self.metrics_data[metric_name].append(value)
        
    def detect_anomaly(self, metric_name: str, current_value: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Detects anomalies for a specific metric based on its historical data.
        
        :param metric_name: The name of the metric to check.
        :param current_value: The most recent value for the metric.
        :param context: Optional context for the anomaly (e.g., session ID, user ID).
        :return: A dictionary indicating if an anomaly was detected and its details.
        """
        report = {
            "metric_name": metric_name,
            "current_value": current_value,
            "anomaly_detected": False,
            "reason": None,
            "severity": "low"
        }
        
        if metric_name not in self.metrics_data or len(self.metrics_data[metric_name]) < 5: # Need enough data for stats
            return report

        history = list(self.metrics_data[metric_name])
        threshold_config = self.thresholds.get(metric_name, {})

        if metric_name == "error_rate":
            if current_value > threshold_config.get("threshold", 0.05):
                report["anomaly_detected"] = True
                report["reason"] = f"Error rate {current_value*100:.1f}% exceeds threshold {threshold_config.get('threshold', 0.05)*100:.1f}%. "
                report["severity"] = "critical"
        elif "std_multiplier" in threshold_config:
            mean = statistics.mean(history)
            stdev = statistics.stdev(history) if len(history) > 1 else 0
            
            upper_bound = mean + (stdev * threshold_config["std_multiplier"])
            lower_bound = mean - (stdev * threshold_config["std_multiplier"])

            is_outlier = False
            if current_value > upper_bound and current_value > threshold_config.get("min_threshold", 0):
                is_outlier = True
                report["reason"] = f"Value {current_value:.2f} is significantly higher than average ({mean:.2f} +/- {stdev:.2f} STD)."
                report["severity"] = "medium"
            elif current_value < lower_bound and current_value < threshold_config.get("min_threshold", 0):
                is_outlier = True
                report["reason"] = f"Value {current_value:.2f} is significantly lower than average ({mean:.2f} +/- {stdev:.2f} STD)."
                report["severity"] = "medium"
            
            report["anomaly_detected"] = is_outlier

        if report["anomaly_detected"]:
            self.telemetry.emit_event(
                "anomaly_detected",
                {
                    "metric": metric_name,
                    "value": current_value,
                    "reason": report["reason"],
                    "severity": report["severity"],
                    "context": context
                }
            )
            
        return report

# Example Usage
if __name__ == "__main__":
    
    # Mock TelemetryEmitter
    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # Initialize
    mock_te = MockTelemetryEmitter()
    detector = AnomalyDetector(mock_te, window_size=10) # Small window for quick demo

    # --- Simulate normal call durations ---
    print("\n--- Simulating normal call durations ---")
    for i in range(10):
        duration = 30 + (i % 3) * 2 + (time.time() % 1) * 2
        detector.add_metric_data("call_duration", duration)
        report = detector.detect_anomaly("call_duration", duration, {"session_id": f"s_norm_{i}"})
        if report["anomaly_detected"]:
            print(f"  --> ANOMALY: {report['reason']}")
        else:
            print(f"  --> Normal: {duration:.2f}s")
    
    # --- Simulate an unusually long call ---
    print("\n--- Simulating an unusually long call ---")
    long_duration = 200.0
    detector.add_metric_data("call_duration", long_duration)
    report_long = detector.detect_anomaly("call_duration", long_duration, {"session_id": "s_long_1"})
    print(f"  --> Report for {long_duration:.2f}s call: {report_long}")

    # --- Simulate normal error rates ---
    print("\n--- Simulating normal error rates ---")
    for i in range(10):
        error_rate = 0.01 + (i % 2) * 0.005
        detector.add_metric_data("error_rate", error_rate)
        report = detector.detect_anomaly("error_rate", error_rate, {"component": "LLM"})
        if report["anomaly_detected"]:
            print(f"  --> ANOMALY: {report['reason']}")
        else:
            print(f"  --> Normal error rate: {error_rate:.3f}")

    # --- Simulate a high error rate ---
    print("\n--- Simulating a high error rate ---")
    high_error_rate = 0.1
    detector.add_metric_data("error_rate", high_error_rate)
    report_high_error = detector.detect_anomaly("error_rate", high_error_rate, {"component": "LLM"})
    print(f"  --> Report for {high_error_rate:.3f} error rate: {report_high_error}")

    # --- Simulate unusual intent counts (e.g., too many emergency calls) ---
    print("\n--- Simulating unusual intent counts ---")
    for i in range(10):
        intent_count = 2 + (i % 3)
        detector.add_metric_data("unusual_intent_count", intent_count)
        report = detector.detect_anomaly("unusual_intent_count", intent_count, {"intent_type": "medical_emergency"})
        if report["anomaly_detected"]:
            print(f"  --> ANOMALY: {report['reason']}")
        else:
            print(f"  --> Normal emergency intent count: {intent_count}")
            
    unusual_intent_spike = 15
    detector.add_metric_data("unusual_intent_count", unusual_intent_spike)
    report_spike = detector.detect_anomaly("unusual_intent_count", unusual_intent_spike, {"intent_type": "medical_emergency"})
    print(f"  --> Report for {unusual_intent_spike} emergency intent spike: {report_spike}")
