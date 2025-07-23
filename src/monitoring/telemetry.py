# src/monitoring/telemetry.py
from opentelemetry import trace, metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider


def setup_telemetry():
    # Traces
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer("altiora")

    # Metrics
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter("altiora")

    # Créer des métriques personnalisées
    sfd_counter = meter.create_counter(
        "sfd_processed_total",
        description="Total SFDs processed"
    )

    test_generation_histogram = meter.create_histogram(
        "test_generation_duration_seconds",
        description="Test generation duration"
    )

    return tracer, meter