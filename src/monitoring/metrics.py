# src/monitoring/metrics.py
import time
from functools import wraps

from prometheus_client import Counter, Histogram, Gauge, Info

# Batch
BATCH_DOCS_TOTAL = Gauge("altiora_batch_docs_total",
                         "Nombre total de documents à traiter")
BATCH_SUCCESS_TOTAL = Counter("altiora_batch_success_total",
                              "Documents traités avec succès")
BATCH_DURATION = Histogram("altiora_batch_duration_seconds",
                           "Durée du batch complet")

# Métriques métier
sfd_processed = Counter(
    'altiora_sfd_processed_total',
    'Nombre de SFD traitées',
    ['status', 'module']
)

test_generation_duration = Histogram(
    'altiora_test_generation_seconds',
    'Temps de génération des tests',
    ['model', 'test_type']
)

active_models = Gauge(
    'altiora_active_models',
    'Modèles actuellement chargés',
    ['model_name']
)

model_info = Info(
    'altiora_model',
    'Informations sur les modèles'
)


# Décorateur de monitoring
def monitor_performance(metric_name: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                status = "success"
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start
                test_generation_duration.labels(
                    model=metric_name,
                    test_type=kwargs.get('test_type', 'unknown')
                ).observe(duration)
            return result

        return wrapper

    return decorator
