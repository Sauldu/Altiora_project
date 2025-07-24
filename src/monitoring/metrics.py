# src/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge, Info

# Batch
BATCH_DOCS_TOTAL = Gauge("altiora_batch_docs_total", "Nombre total de documents à traiter")
BATCH_SUCCESS_TOTAL = Counter("altiora_batch_success_total", "Documents traités avec succès")
BATCH_DURATION = Histogram("altiora_batch_duration_seconds", "Durée du batch complet")

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

# Métriques pour le monitoring en production
request_count = Counter('qa_requests_total', 'Total QA requests')
response_time = Histogram('qa_response_time_seconds', 'Response time')
active_models = Gauge('qa_active_models', 'Number of loaded models')
