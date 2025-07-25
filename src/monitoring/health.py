# src/monitoring/health.py
"""Service de vérification de l'état de santé (Health Check) de l'application Altiora.

Ce service expose un point de terminaison `/health` qui fournit un aperçu
rapide de l'état des composants critiques de l'application, tels que la
connexion à Redis et la disponibilité d'Ollama. Il est conçu pour être
utilisé par les systèmes de surveillance externes (ex: Kubernetes, Prometheus).
"""

import json
import logging

from fastapi import FastAPI, Response
import redis.asyncio as redis
import httpx

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Altiora Health Check Service",
    description="Vérifie l'état de santé des composants critiques d'Altiora.",
    version="1.0.0",
)


@app.get("/health")
async def health() -> Response:
    """Point de terminaison principal pour la vérification de l'état de santé.

    Effectue des vérifications sur :
    - La connexion à Redis.
    - La disponibilité du serveur Ollama.

    Returns:
        Une `FastAPI.Response` au format JSON indiquant l'état global et le statut de chaque vérification.
        Le code HTTP est 200 si tout est sain, 503 (Service Unavailable) sinon.
    """
    status_info = {"status": "healthy", "checks": {}}
    http_status_code = 200

    # Vérification de la connexion Redis.
    try:
        # Tente de se connecter à Redis en utilisant l'URL par défaut.
        r = redis.from_url("redis://localhost:6379")
        await r.ping() # Envoie une commande PING pour vérifier la connexion.
        status_info["checks"]["redis"] = "OK"
    except Exception as e:
        status_info["checks"]["redis"] = f"Échec: {str(e)}"
        http_status_code = 503
        logger.error(f"Vérification Redis échouée : {e}")

    # Vérification de la disponibilité d'Ollama.
    async with httpx.AsyncClient(timeout=5) as client: # Timeout de 5 secondes pour la requête HTTP.
        try:
            # Tente d'accéder à l'endpoint de santé d'Ollama.
            resp = await client.get("http://localhost:11434/api/tags") # Utilise /api/tags car /health n'existe pas toujours.
            resp.raise_for_status() # Lève une exception pour les codes d'état HTTP 4xx/5xx.
            status_info["checks"]["ollama"] = "OK"
        except httpx.RequestError as e:
            status_info["checks"]["ollama"] = f"Échec de la requête: {str(e)}"
            http_status_code = 503
            logger.error(f"Vérification Ollama (requête) échouée : {e}")
        except httpx.HTTPStatusError as e:
            status_info["checks"]["ollama"] = f"Échec HTTP: {e.response.status_code} - {e.response.text}"
            http_status_code = 503
            logger.error(f"Vérification Ollama (HTTP) échouée : {e}")

    # Retourne la réponse JSON avec le code d'état approprié.
    return Response(content=json.dumps(status_info, indent=2), status_code=http_status_code, media_type="application/json")


# ------------------------------------------------------------------
# Point d'entrée Uvicorn
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Lancement du service de vérification de santé sur http://0.0.0.0:8000/health")
    uvicorn.run(app, host="0.0.0.0", port=8000)
