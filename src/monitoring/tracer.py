# src/monitoring/tracer.py
"""Module pour la configuration et l'initialisation du traçage distribué avec OpenTelemetry.

Ce module configure le `TracerProvider` d'OpenTelemetry et intègre des
exportateurs (comme Jaeger) pour envoyer les traces collectées. Il fournit
également des fonctions pour instrumenter automatiquement les applications
FastAPI, les clients Redis et HTTPX, permettant une visibilité complète
des flux de requêtes à travers les microservices.
"""

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import logging

logger = logging.getLogger(__name__)


def setup_tracing(app=None, service_name: str = "altiora"):
    """Initialise le traçage distribué avec OpenTelemetry.

    Args:
        app: L'instance de l'application FastAPI à instrumenter (optionnel).
        service_name: Le nom du service qui génère les traces.

    Returns:
        L'instance du `Tracer` configuré.
    """
    logger.info(f"Initialisation du traçage OpenTelemetry pour le service : {service_name}...")

    # 1. Configuration du TracerProvider.
    # Un `TracerProvider` gère la création des `Tracer`.
    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    # 2. Configuration de l'exportateur Jaeger.
    # Les traces seront envoyées à un agent Jaeger (généralement sur localhost:6831).
    jaeger_exporter = JaegerExporter(
        agent_host_name="localhost",
        agent_port=6831,
    )
    # Un `BatchSpanProcessor` envoie les spans par lots pour optimiser les performances.
    provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

    # 3. Instrumentation automatique des bibliothèques.
    # Cela permet de collecter automatiquement les traces pour les opérations
    # effectuées par ces bibliothèques sans modification du code.
    if app:
        # Instrumente l'application FastAPI pour tracer les requêtes entrantes.
        FastAPIInstrumentor.instrument_app(app)
        logger.info("Instrumentation FastAPI activée.")
    
    # Instrumente le client Redis pour tracer les interactions avec Redis.
    RedisInstrumentor().instrument()
    logger.info("Instrumentation Redis activée.")

    # Instrumente le client HTTPX pour tracer les requêtes HTTP sortantes.
    HTTPXClientInstrumentor().instrument()
    logger.info("Instrumentation HTTPX activée.")

    logger.info("Traçage OpenTelemetry configuré avec succès.")
    return trace.get_tracer(service_name)


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import time
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Crée une application FastAPI factice pour la démonstration.
    demo_app = FastAPI()

    # Initialise le traçage pour cette application.
    tracer = setup_tracing(app=demo_app, service_name="demo-service")

    @demo_app.get("/hello")
    async def hello_world():
        with tracer.start_as_current_span("hello_operation") as span:
            span.set_attribute("custom.attribute", "value")
            time.sleep(0.05) # Simule un travail.
            return {"message": "Hello, World!"}

    @demo_app.get("/chain")
    async def chain_call():
        with tracer.start_as_current_span("chain_operation"):
            # Simule un appel HTTP interne.
            async with httpx.AsyncClient() as client:
                await client.get("http://localhost:8000/hello") # Appel à l'endpoint /hello de cette même app.
            return {"message": "Chained call completed"}

    async def run_demo_client():
        print("\n--- Lancement du client de démonstration ---")
        # Utilise TestClient pour simuler des requêtes HTTP.
        client = TestClient(demo_app)

        print("Appel à /hello...")
        response = client.get("/hello")
        print(f"Réponse /hello : {response.json()}")

        print("Appel à /chain...")
        response = client.get("/chain")
        print(f"Réponse /chain : {response.json()}")

        print("\nLes traces devraient être visibles dans votre interface Jaeger (http://localhost:16686).")

    # Lance le serveur Uvicorn en arrière-plan pour la démo.
    # Note: Pour une vraie démo, vous auriez besoin d'un agent Jaeger en cours d'exécution.
    import uvicorn
    config = uvicorn.Config(demo_app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    
    async def run_server_and_client():
        server_task = asyncio.create_task(server.serve())
        await asyncio.sleep(1) # Donne le temps au serveur de démarrer.
        await run_demo_client()
        server_task.cancel()

    asyncio.run(run_server_and_client())
