# src/core/telemetry_emitter.py
"""
Handles the collection and emission of anonymous usage data and performance
metrics using the OpenTelemetry standard.
"""
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
# from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# from . import __version__

class TelemetryEmitter:
    def __init__(self, service_name: str = "AI_Hospital_API", version: str = "0.1.0"):
        """Initializes the telemetry system."""
        
        resource = Resource(attributes={
            "service.name": service_name,
            "service.version": version,
        })

        # --- Metrics (for Prometheus) ---
        # The Prometheus exporter starts a server to be scraped.
        # reader = PrometheusMetricReader()
        # self.meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        # metrics.set_meter_provider(self.meter_provider)
        
        # --- Tracing (for Jaeger, Datadog APM, etc.) ---
        # For this example, we'll just print traces to the console.
        self.tracer_provider = TracerProvider(resource=resource)
        self.tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(self.tracer_provider)

        # Get a tracer and meter for the application
        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)

        # --- Define Metrics ---
        self.call_duration_histogram = self.meter.create_histogram(
            "call.duration", unit="s", description="Duration of user calls"
        )
        self.api_latency_histogram = self.meter.create_histogram(
            "api.latency", unit="ms", description="Latency of external API calls (STT, LLM, TTS)"
        )
        self.error_rate_counter = self.meter.create_counter(
            "errors.total", description="Total number of errors"
        )
        self.intent_counter = self.meter.create_counter(
            "intent.classification", description="Count of classified intents"
        )
        
        print("TelemetryEmitter initialized.")

    def track_call_duration(self, duration_seconds: float, attributes: dict):
        """Tracks the duration of a completed call."""
        self.call_duration_histogram.record(duration_seconds, attributes=attributes)

    def track_api_latency(self, latency_ms: float, api_name: str):
        """Tracks the latency of a dependency."""
        self.api_latency_histogram.record(latency_ms, attributes={"api.name": api_name})

    def track_error(self, error_type: str):
        """Increments the error counter."""
        self.error_rate_counter.add(1, attributes={"error.type": error_type})

    def track_intent(self, intent: str):
        """Increments the counter for a specific intent."""
        self.intent_counter.add(1, attributes={"intent": intent})

    def trace_function(self, func):
        """A decorator to automatically trace the execution of a function."""
        def wrapper(*args, **kwargs):
            with self.tracer.start_as_current_span(func.__name__) as span:
                span.set_attribute("function.args", str(args))
                span.set_attribute("function.kwargs", str(kwargs))
                result = func(*args, **kwargs)
                return result
        return wrapper

# It is now recommended to create a single instance of TelemetryEmitter
# in your application's main entry point and pass it around.
# Example:
#
# from src.core.telemetry_emitter import TelemetryEmitter
# telemetry = TelemetryEmitter()
#
# @telemetry.trace_function
# def my_function():
#     ...