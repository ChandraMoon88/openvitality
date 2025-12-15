import sys
import os
import unittest
from unittest.mock import patch, Mock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.telemetry_emitter import TelemetryEmitter

class TestTelemetryEmitter(unittest.TestCase):

    @patch('opentelemetry.trace.set_tracer_provider')
    @patch('opentelemetry.metrics.set_meter_provider')
    @patch('opentelemetry.trace.get_tracer')
    @patch('opentelemetry.metrics.get_meter')
    def setUp(self, mock_get_meter, mock_get_tracer, mock_set_meter_provider, mock_set_tracer_provider):
        """
        Set up a TelemetryEmitter instance and mock its internal OTel objects.
        """
        # Mock the meter and tracer creation
        self.mock_meter = Mock()
        self.mock_tracer = Mock()
        mock_get_meter.return_value = self.mock_meter
        mock_get_tracer.return_value = self.mock_tracer
        
        # Mock the metric objects that are created
        self.mock_histogram = Mock()
        self.mock_counter = Mock()
        self.mock_meter.create_histogram.return_value = self.mock_histogram
        self.mock_meter.create_counter.return_value = self.mock_counter
        
        # Now, instantiate the class under test
        self.telemetry_emitter = TelemetryEmitter()

    def test_init_creates_metrics(self):
        """Test that the required metrics are created upon initialization."""
        self.mock_meter.create_histogram.assert_any_call(
            "call.duration", unit="s", description="Duration of user calls"
        )
        self.mock_meter.create_histogram.assert_any_call(
            "api.latency", unit="ms", description="Latency of external API calls (STT, LLM, TTS)"
        )
        self.mock_meter.create_counter.assert_any_call(
            "errors.total", description="Total number of errors"
        )
        self.mock_meter.create_counter.assert_any_call(
            "intent.classification", description="Count of classified intents"
        )

    def test_track_call_duration(self):
        """Test tracking call duration."""
        self.telemetry_emitter.track_call_duration(120.5, {"region": "us"})
        self.telemetry_emitter.call_duration_histogram.record.assert_called_with(120.5, attributes={"region": "us"})

    def test_track_api_latency(self):
        """Test tracking API latency."""
        self.telemetry_emitter.track_api_latency(350.0, "google_stt")
        self.telemetry_emitter.api_latency_histogram.record.assert_called_with(350.0, attributes={"api.name": "google_stt"})

    def test_track_error(self):
        """Test tracking an error."""
        self.telemetry_emitter.track_error("DatabaseError")
        self.telemetry_emitter.error_rate_counter.add.assert_called_with(1, attributes={"error.type": "DatabaseError"})

    def test_track_intent(self):
        """Test tracking an intent classification."""
        self.telemetry_emitter.track_intent("symptom_report")
        self.telemetry_emitter.intent_counter.add.assert_called_with(1, attributes={"intent": "symptom_report"})
        
    def test_trace_function_decorator(self):
        """Test that the tracing decorator starts a span."""
        mock_span = Mock()
        # Configure the mock tracer to return a context manager that returns the mock span
        mock_context_manager = Mock()
        mock_context_manager.__enter__.return_value = mock_span
        self.mock_tracer.start_as_current_span.return_value = mock_context_manager
        
        @self.telemetry_emitter.trace_function
        def my_test_function(a, b=None):
            return "result"
            
        result = my_test_function(1, b="test")
        
        self.assertEqual(result, "result")
        self.mock_tracer.start_as_current_span.assert_called_with('my_test_function')
        mock_span.set_attribute.assert_any_call("function.args", str((1,)))
        mock_span.set_attribute.assert_any_call("function.kwargs", str({'b': 'test'}))


if __name__ == '__main__':
    unittest.main()