# src/monitoring/metrics_collector.py
import time
from functools import wraps

from prometheus_client import Counter, Histogram, Gauge


class MetricsCollector:
    def __init__(self):
        # Métriques de performance
        self.request_duration = Histogram(
            'altiora_request_duration_seconds',
            'Request duration in seconds',
            ['endpoint', 'method', 'status']
        )

        self.model_inference_time = Histogram(
            'altiora_model_inference_seconds',
            'Model inference time in seconds',
            ['model', 'operation']
        )

        # Métriques métier
        self.scenarios_processed = Counter(
            'altiora_scenarios_processed_total',
            'Total number of scenarios processed',
            ['status']
        )

        self.tests_generated = Counter(
            'altiora_tests_generated_total',
            'Total number of tests generated',
            ['test_type', 'status']
        )

        # Métriques système
        self.active_connections = Gauge(
            'altiora_active_connections',
            'Number of active connections',
            ['service']
        )

        self.cache_hit_rate = Gauge(
            'altiora_cache_hit_rate',
            'Cache hit rate percentage'
        )

    def track_request(self, endpoint: str, method: str):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                status = "success"

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = "error"
                    raise
                finally:
                    duration = time.time() - start_time
                    self.request_duration.labels(
                        endpoint=endpoint,
                        method=method,
                        status=status
                    ).observe(duration)

            return wrapper

        return decorator
