# src/monitoring/tracer.py
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def setup_tracing(app=None, service_name: str = "altiora"):
    """
    Initialise OpenTelemetry :
    - FastAPI routes
    - Redis calls
    - HTTPX clients
    """
    # 1. Tracer provider
    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    # 2. Jaeger exporter
    jaeger = JaegerExporter(
        agent_host_name="localhost",
        agent_port=6831,
    )
    provider.add_span_processor(BatchSpanProcessor(jaeger))

    # 3. Auto-instrumentation
    if app:
        FastAPIInstrumentor.instrument_app(app)
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    return trace.get_tracer(service_name)