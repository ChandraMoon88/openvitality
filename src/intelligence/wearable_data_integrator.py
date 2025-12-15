# src/intelligence/wearable_data_integrator.py

from typing import Dict, Any, List
import asyncio
import json
import datetime
import random

# Assuming these imports will be available from other modules
# from src.core.memory_manager import MemoryManager
# from src.intelligence.anomaly_detector import AnomalyDetector
# from src.core.telemetry_emitter import TelemetryEmitter


class WearableDataIntegrator:
    """
    Integrates and analyzes data from various wearable devices (fitness trackers, smartwatches).
    Normalizes diverse data formats and detects anomalies or trends in biometric data.
    """
    def __init__(self, memory_manager_instance, anomaly_detector_instance, telemetry_emitter_instance):
        """
        Initializes the WearableDataIntegrator.
        
        :param memory_manager_instance: An initialized MemoryManager instance for data storage.
        :param anomaly_detector_instance: An initialized AnomalyDetector instance for trend/anomaly detection.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.memory_manager = memory_manager_instance
        self.anomaly_detector = anomaly_detector_instance
        self.telemetry = telemetry_emitter_instance
        
        # Mapping of raw device metric names to canonical names
        self.metric_normalization_map = {
            "heart_rate_bpm": "heart_rate_bpm",
            "hr": "heart_rate_bpm",
            "heartrate": "heart_rate_bpm",
            "steps": "steps_count",
            "step_count": "steps_count",
            "sleep_hours": "sleep_duration_hours",
            "sleep_duration": "sleep_duration_hours",
            "spo2": "blood_oxygen_percent",
            "blood_oxygen": "blood_oxygen_percent",
            "activity_minutes": "active_minutes",
            "active_time": "active_minutes",
        }
        
        print("✅ WearableDataIntegrator initialized.")

    async def integrate_data(self, user_id: str, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Integrates and processes incoming data from a wearable device for a specific user.
        
        :param user_id: The ID of the user.
        :param device_data: A dictionary containing raw data from the wearable device.
                            Example: {"device_type": "Fitbit", "timestamp": "...", "metrics": {"hr": 75, "steps": 10000}}
        :return: A dictionary of processed and potentially normalized data, along with any detected anomalies.
        """
        processed_data = {
            "user_id": user_id,
            "timestamp": device_data.get("timestamp", datetime.datetime.now().isoformat()),
            "device_type": device_data.get("device_type", "unknown"),
            "normalized_metrics": {},
            "anomalies": [],
            "raw_data_hash": hash(json.dumps(device_data, sort_keys=True)) # For data integrity/deduplication
        }
        
        # 1. Normalize Metric Names and Values
        raw_metrics = device_data.get("metrics", {})
        for raw_name, value in raw_metrics.items():
            canonical_name = self.metric_normalization_map.get(raw_name.lower(), raw_name.lower())
            processed_data["normalized_metrics"][canonical_name] = value

        print(f"Integrating wearable data for user {user_id} from {processed_data['device_type']}.")

        # 2. Detect Anomalies and Trends
        for metric_name, value in processed_data["normalized_metrics"].items():
            # Add data to anomaly detector's history
            self.anomaly_detector.add_metric_data(metric_name, float(value))
            # Check for anomalies
            anomaly_report = self.anomaly_detector.detect_anomaly(
                metric_name, float(value), {"user_id": user_id, "device_type": processed_data["device_type"]}
            )
            if anomaly_report["anomaly_detected"]:
                processed_data["anomalies"].append(anomaly_report)
                print(f"  Anomaly detected for {metric_name}: {anomaly_report['reason']}")

        # 3. Store Processed Data in MemoryManager
        await self.memory_manager.store_wearable_data(user_id, processed_data)
        
        self.telemetry.emit_event(
            "wearable_data_integrated",
            {
                "user_id": user_id,
                "device_type": processed_data["device_type"],
                "metrics_count": len(processed_data["normalized_metrics"]),
                "anomalies_count": len(processed_data["anomalies"])
            }
        )
        return processed_data

    async def get_trends_and_insights(self, user_id: str, metric_name: str, period_days: int = 30) -> Dict[str, Any]:
        """
        Retrieves historical data for a metric and provides trends and insights.
        
        :param user_id: The ID of the user.
        :param metric_name: The canonical name of the metric (e.g., "heart_rate_bpm").
        :param period_days: The number of days to look back for data.
        :return: A dictionary containing historical data, trends, and summary statistics.
        """
        print(f"Getting trends for {metric_name} for user {user_id} over {period_days} days.")
        
        historical_data = await self.memory_manager.get_wearable_data_history(user_id, metric_name, period_days)
        
        insights = {
            "metric_name": metric_name,
            "historical_data": historical_data,
            "summary_statistics": {},
            "trends": "No significant trend detected.",
            "insights_text": ""
        }
        
        if historical_data:
            values = [d["value"] for d in historical_data if "value" in d]
            if values:
                insights["summary_statistics"] = {
                    "average": np.mean(values),
                    "min": np.min(values),
                    "max": np.max(values),
                    "std_dev": np.std(values) if len(values) > 1 else 0
                }
                
                # Simple trend detection (e.g., linear regression or simple comparison)
                if len(values) > 5: # Need enough points for a trend
                    first_avg = np.mean(values[:len(values)//2])
                    second_avg = np.mean(values[len(values)//2:])
                    if second_avg > first_avg * 1.05: # 5% increase
                        insights["trends"] = "Increasing trend observed."
                    elif second_avg < first_avg * 0.95: # 5% decrease
                        insights["trends"] = "Decreasing trend observed."
                
                # Use LLM for a more natural language interpretation of insights
                insights["insights_text"] = await self._generate_llm_insights(user_id, metric_name, insights)

        self.telemetry.emit_event("wearable_data_trends_generated", {"user_id": user_id, "metric": metric_name})
        return insights

    async def _generate_llm_insights(self, user_id: str, metric_name: str, data_insights: Dict[str, Any]) -> str:
        """
        Uses an LLM to generate natural language insights from wearable data trends.
        """
        system_prompt = f"""You are a medical AI assistant analyzing wearable device data.
        Provide actionable and easy-to-understand insights based on the provided trends and statistics for user {user_id}.
        Focus on how these insights relate to general health. Always include a disclaimer about consulting a medical professional."""
        
        user_prompt = f"""Metric: {metric_name}
        Summary Statistics: {data_insights['summary_statistics']}
        Trends: {data_insights['trends']}
        
        What are the key takeaways for the user regarding their health?"""
        
        llm_response = await self.llm.generate_response(user_prompt, [{"role": "system", "text": system_prompt}])
        return llm_response

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockMemoryManager:
        def __init__(self):
            self.wearable_data: Dict[str, List[Dict]] = {}
        async def store_wearable_data(self, user_id: str, data: Dict):
            if user_id not in self.wearable_data:
                self.wearable_data[user_id] = []
            self.wearable_data[user_id].append({"timestamp": data["timestamp"], "value": data["normalized_metrics"].get("heart_rate_bpm")})
            print(f"Mock MM: Stored wearable data for {user_id}.")
        async def get_wearable_data_history(self, user_id: str, metric_name: str, period_days: int) -> List[Dict]:
            if user_id in self.wearable_data and metric_name == "heart_rate_bpm":
                # Filter by period_days (simplified)
                return [d for d in self.wearable_data[user_id] if (datetime.datetime.now() - datetime.datetime.fromisoformat(d["timestamp"])).days < period_days]
            return []

    class MockAnomalyDetector:
        def __init__(self):
            self.metrics_data: Dict[str, List[float]] = {}
        def add_metric_data(self, metric_name: str, value: float):
            if metric_name not in self.metrics_data:
                self.metrics_data[metric_name] = []
            self.metrics_data[metric_name].append(value)
        def detect_anomaly(self, metric_name: str, current_value: float, context: Dict) -> Dict:
            if metric_name == "heart_rate_bpm" and current_value > 120:
                return {"metric_name": metric_name, "current_value": current_value, "anomaly_detected": True, "reason": "High heart rate spike.", "severity": "high"}
            if metric_name == "sleep_duration_hours" and current_value < 4:
                return {"metric_name": metric_name, "current_value": current_value, "anomaly_detected": True, "reason": "Very short sleep duration.", "severity": "medium"}
            return {"metric_name": metric_name, "current_value": current_value, "anomaly_detected": False}

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    class MockLLMProvider:
        def __init__(self, config=None): pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            if "heart rate" in prompt:
                return "Your average heart rate is [avg]. There's an [increasing/decreasing] trend. Consistent high heart rate can be a sign of stress or underlying conditions. Consult your doctor if concerned."
            return "Mock LLM insight."
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-wearable-insights"

    # --- Initialize ---
    mock_mm = MockMemoryManager()
    mock_ad = MockAnomalyDetector()
    mock_te = MockTelemetryEmitter()
    mock_llm = MockLLMProvider()
    
    integrator = WearableDataIntegrator(mock_mm, mock_ad, mock_te)

    user_id_1 = "user_w_1"
    
    # --- Test 1: Integrate normal heart rate data ---
    print("\n--- Test 1: Integrate normal heart rate data ---")
    data_1_normal = {"device_type": "Fitbit", "timestamp": datetime.datetime.now().isoformat(), "metrics": {"hr": 70, "steps": 8000}}
    processed_1 = asyncio.run(integrator.integrate_data(user_id_1, data_1_normal))
    print(f"Processed Data: {json.dumps(processed_1, indent=2)}")

    # --- Test 2: Integrate high heart rate data (anomaly) ---
    print("\n--- Test 2: Integrate high heart rate data (anomaly) ---")
    data_2_high_hr = {"device_type": "Fitbit", "timestamp": datetime.datetime.now().isoformat(), "metrics": {"hr": 130, "steps": 1000}}
    processed_2 = asyncio.run(integrator.integrate_data(user_id_1, data_2_high_hr))
    print(f"Processed Data: {json.dumps(processed_2, indent=2)}")

    # --- Test 3: Integrate low sleep data (anomaly) ---
    print("\n--- Test 3: Integrate low sleep data (anomaly) ---")
    data_3_low_sleep = {"device_type": "AppleWatch", "timestamp": datetime.datetime.now().isoformat(), "metrics": {"sleep_duration": 3.5}}
    processed_3 = asyncio.run(integrator.integrate_data(user_id_1, data_3_low_sleep))
    print(f"Processed Data: {json.dumps(processed_3, indent=2)}")

    # --- Test 4: Get trends and insights for heart rate ---
    print("\n--- Test 4: Get trends and insights for heart rate ---")
    # Add more data points for trend analysis
    for i in range(5):
        asyncio.run(integrator.integrate_data(user_id_1, {"device_type": "Fitbit", "timestamp": (datetime.datetime.now() - datetime.timedelta(days=5-i)).isoformat(), "metrics": {"hr": 65 + i*2}}))
    
    trends_report = asyncio.run(integrator.get_trends_and_insights(user_id_1, "heart_rate_bpm", period_days=10))
    print(f"Trends Report: {json.dumps(trends_report, indent=2)}")
