# src/monitoring/telemetry.py
"""Module pour la configuration et l'initialisation d'OpenTelemetry.

OpenTelemetry est un ensemble d'outils, d'API et de SDKs qui permet de
collecter des données de télémétrie (traces, métriques, logs) de manière
unifiée. Ce module configure les fournisseurs de traces et de métriques
pour l'application Altiora, permettant l'exportation vers des systèmes
de surveillance comme Jaeger (pour les traces) et Prometheus (pour les métriques).
"""

from opentelemetry import trace, metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
import logging

logger = logging.getLogger(__name__)


def setup_telemetry():
    """Initialise les fournisseurs de traces et de métriques OpenTelemetry."

    Returns:
        Un tuple contenant l'instance du `Tracer` et du `Meter` configurés.
    """
    logger.info("Initialisation d'OpenTelemetry...")

    # Configuration des traces.
    # Un `TracerProvider` gère la création des `Tracer`.
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer("altiora") # Récupère une instance de Tracer.

    # Configuration des métriques.
    # Un `MeterProvider` gère la création des `Meter`.
    metrics.set_meter_provider(MeterProvider())
    meter = metrics.get_meter("altiora") # Récupère une instance de Meter.

    # Exemple de métriques personnalisées (à utiliser dans le code de l'application).
    sfd_processed_counter = meter.create_counter(
        "sfd_processed_total",
        description="Nombre total de SFD traitées"
    )

    test_generation_duration_histogram = meter.create_histogram(
        "test_generation_duration_seconds",
        description="Durée de génération des tests"
    )

    logger.info("OpenTelemetry initialisé : Tracer et Meter disponibles.")
    return tracer, meter


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import time
    import random

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Initialise la télémétrie.
    tracer, meter = setup_telemetry()

    # Récupère les instruments de métriques définis.
    sfd_counter = meter.get_instrument("sfd_processed_total")
    test_gen_hist = meter.get_instrument("test_generation_duration_seconds")

    print("\n--- Démonstration de la télémétrie ---")

    # Utilisation du compteur.
    print("Incrémentation du compteur de SFD traitées...")
    sfd_counter.add(1, {"status": "success", "model": "qwen3"})
    sfd_counter.add(1, {"status": "failed", "model": "qwen3"})

    # Utilisation de l'histogramme.
    print("Enregistrement des durées de génération de tests...")
    for _ in range(5):
        duration = random.uniform(0.5, 5.0)
        test_gen_hist.record(duration, {"test_type": "e2e", "browser": "chromium"})
        time.sleep(0.1)

    # Utilisation des traces (nécessite un exportateur configuré, ex: Jaeger).
    print("Création d'une trace simple...")
    with tracer.start_as_current_span("main_operation") as span:
        span.set_attribute("user.id", "demo_user")
        span.add_event("starting_sub_process")
        time.sleep(0.2)
        with tracer.start_as_current_span("sub_operation"):
            time.sleep(0.1)
        span.add_event("sub_process_completed")

    print("\nDonnées de télémétrie générées. Elles seront exportées si un exportateur est configuré.")
    print("Pour visualiser les traces, configurez un exportateur Jaeger (voir tracer.py).")