# src/monitoring/metrics_collector.py
"""Collecteur de métriques pour l'application Altiora.

Ce module fournit une classe `MetricsCollector` qui centralise la définition
et l'exposition des métriques Prometheus. Il inclut des compteurs, des
histogrammes et des jauges pour suivre la performance technique et les
indicateurs métier de l'application.
"""

import time
from functools import wraps
from typing import Callable, Any

from prometheus_client import Counter, Histogram, Gauge


class MetricsCollector:
    """Collecte et expose diverses métriques pour la surveillance de l'application."""

    def __init__(self):
        """Initialise toutes les métriques Prometheus utilisées dans l'application."""
        # Métriques de performance technique.
        self.request_duration = Histogram(
            'altiora_request_duration_seconds',
            'Durée des requêtes en secondes',
            ['endpoint', 'method', 'status'] # Labels pour filtrer les métriques.
        )

        self.model_inference_time = Histogram(
            'altiora_model_inference_seconds',
            'Temps d'inférence des modèles en secondes',
            ['model', 'operation']
        )

        # Métriques métier (Business Metrics).
        self.scenarios_processed = Counter(
            'altiora_scenarios_processed_total',
            'Nombre total de scénarios traités',
            ['status'] # Ex: 'success', 'failed'.
        )

        self.tests_generated = Counter(
            'altiora_tests_generated_total',
            'Nombre total de tests générés',
            ['test_type', 'status'] # Ex: 'e2e', 'api', 'success', 'failed'.
        )

        # Métriques système (ex: connexions actives, taux de hit du cache).
        self.active_connections = Gauge(
            'altiora_active_connections',
            'Nombre de connexions actives',
            ['service']
        )

        self.cache_hit_rate = Gauge(
            'altiora_cache_hit_rate',
            'Pourcentage de hits du cache'
        )

        # Métriques spécifiques pour le monitoring en production (utilisées par le Dash).
        self.request_count = Counter('qa_requests_total', 'Nombre total de requêtes QA')
        self.response_time = Histogram('qa_response_time_seconds', 'Temps de réponse des requêtes QA')
        self.active_models = Gauge('qa_active_models', 'Nombre de modèles chargés en mémoire')

    def track_request(self, endpoint: str, method: str) -> Callable:
        """Décorateur pour suivre la durée et le statut des requêtes HTTP."

        Args:
            endpoint: Le chemin de l'endpoint (ex: '/api/v1/sfd').
            method: La méthode HTTP (ex: 'POST', 'GET').

        Returns:
            Un décorateur qui peut être appliqué à une fonction asynchrone.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                status_label = "success"

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    status_label = "error"
                    raise # Re-lève l'exception après l'avoir traitée.
                finally:
                    duration = time.time() - start_time
                    # Observe la durée de la requête.
                    self.request_duration.labels(
                        endpoint=endpoint,
                        method=method,
                        status=status_label
                    ).observe(duration)
                    # Incrémente le compteur de requêtes QA.
                    self.request_count.inc()
                    # Observe le temps de réponse global des requêtes QA.
                    self.response_time.observe(duration)

            return wrapper

        return decorator


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging
    from prometheus_client import generate_latest, start_http_server

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Démarre un serveur HTTP pour exposer les métriques Prometheus.
    # Accédez à http://localhost:8000/metrics dans votre navigateur.
    start_http_server(8000)
    logging.info("Serveur Prometheus démarré sur le port 8000.")

    metrics = MetricsCollector()

    @metrics.track_request(endpoint="/api/process", method="POST")
    async def process_data_mock(data: str, simulate_error: bool = False):
        logging.info(f"Traitement des données : {data}")
        await asyncio.sleep(0.1 + (len(data) * 0.01)) # Simule un travail.
        if simulate_error:
            raise ValueError("Erreur simulée lors du traitement.")
        metrics.scenarios_processed.labels(status="success").inc()
        metrics.tests_generated.labels(test_type="e2e", status="success").inc()
        return {"status": "processed", "data": data}

    async def demo():
        print("\n--- Démonstration du MetricsCollector ---")

        # Simule des requêtes réussies.
        for i in range(5):
            try:
                await process_data_mock(f"item_{i}")
            except Exception:
                pass

        # Simule une requête en échec.
        try:
            await process_data_mock("item_error", simulate_error=True)
        except Exception as e:
            logging.error(f"Erreur capturée dans la démo : {e}")
            metrics.scenarios_processed.labels(status="failed").inc()
            metrics.tests_generated.labels(test_type="e2e", status="failed").inc()

        # Met à jour une jauge.
        metrics.active_connections.labels(service="redis").set(10)
        metrics.cache_hit_rate.set(0.85)
        metrics.active_models.set(2)

        print("\n--- Métriques actuelles (Prometheus format) ---")
        print(generate_latest().decode('utf-8'))

        print("Démonstration terminée. Accédez à http://localhost:8000/metrics pour voir les métriques.")

    asyncio.run(demo())