# src/monitoring/telemetry.py
from opentelemetry import trace, metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider


def setup_telemetry():
    """
    Initialise OpenTelemetry :
    - Traces (Jaeger)
    - Métriques (Prometheus exposé via /metrics)
    - Dash sera utilisé pour visualiser
    """
    # Traces
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer("altiora")

    # Métriques Prometheus
    meter_provider = MeterProvider()
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter("altiora")

    # Métriques personnalisées
    sfd_counter = meter.create_counter(
        "sfd_processed_total",
        description="Total SFDs processed"
    )

    test_generation_histogram = meter.create_histogram(
        "test_generation_duration_seconds",
        description="Test generation duration"
    )

    return tracer, meter
