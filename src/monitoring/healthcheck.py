# src/monitoring/healthcheck.py
"""Service de vérification de l'état de santé (Health Check) pour les composants critiques d'Altiora.

Ce module fournit un point de terminaison `/health` qui agrège l'état de
santé de plusieurs services et dépendances clés de l'application, tels que
Redis, Ollama et d'autres microservices internes. Il est conçu pour être
utilisé par les systèmes de surveillance externes pour évaluer la disponibilité
globale de l'application.
"""

import json
import logging

from fastapi import FastAPI, Response
import aioredis
import httpx # Pour vérifier Ollama et d'autres services HTTP.

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Altiora Healthcheck Service",
    description="Vérifie l'état de santé des dépendances clés d'Altiora.",
    version="1.0.0",
)


async def check_redis() -> bool:
    """Vérifie la connectivité et l'état de santé du serveur Redis."

    Returns:
        True si Redis est accessible et répond, False sinon.
    """
    try:
        # Utilise l'URL par défaut pour Redis, à adapter si nécessaire.
        redis_client = aioredis.from_url("redis://localhost:6379")
        await redis_client.ping()
        await redis_client.close() # Ferme la connexion après le ping.
        logger.debug("Vérification Redis : OK")
        return True
    except aioredis.exceptions.ConnectionError as e:
        logger.warning(f"Vérification Redis : Échec de la connexion - {e}")
        return False
    except Exception as e:
        logger.error(f"Vérification Redis : Erreur inattendue - {e}")
        return False


async def check_ollama() -> bool:
    """Vérifie la disponibilité du serveur Ollama."

    Returns:
        True si Ollama est accessible, False sinon.
    """
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            # Tente d'accéder à un endpoint simple d'Ollama pour vérifier sa disponibilité.
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status() # Lève une exception pour les codes d'état HTTP 4xx/5xx.
            logger.debug("Vérification Ollama : OK")
            return True
    except httpx.RequestError as e:
        logger.warning(f"Vérification Ollama : Échec de la requête - {e}")
        return False
    except httpx.HTTPStatusError as e:
        logger.warning(f"Vérification Ollama : Échec HTTP - {e.response.status_code}")
        return False
    except Exception as e:
        logger.error(f"Vérification Ollama : Erreur inattendue - {e}")
        return False


async def check_services() -> bool:
    """Vérifie l'état de santé des autres microservices internes d'Altiora."

    Cette fonction est un placeholder. Dans une implémentation réelle, elle
    ferait des appels aux endpoints `/health` de chaque microservice (ALM, OCR, etc.).

    Returns:
        True si tous les services sont sains, False sinon.
    """
    # TODO: Implémenter la logique de vérification des autres microservices.
    # Exemple: faire des requêtes HTTP à http://localhost:8001/health (OCR), etc.
    logger.warning("Vérification des services : Logique non implémentée, retourne True par défaut.")
    return True


@app.get("/health")
async def health_check() -> Response:
    """Point de terminaison principal pour la vérification de l'état de santé complète de l'application."

    Effectue des vérifications sur Redis, Ollama et d'autres services.

    Returns:
        Une `FastAPI.Response` au format JSON indiquant l'état global et le statut
        de chaque vérification. Le code HTTP est 200 si tout est sain, 503 sinon.
    """
    checks = {
        "redis": await check_redis(),
        "ollama": await check_ollama(),
        "services": await check_services() # Placeholder pour d'autres services.
    }

    if all(checks.values()):
        status_code = 200
        status_message = "healthy"
    else:
        status_code = 503
        status_message = "unhealthy"

    response_content = {"status": status_message, "checks": {k: ("OK" if v else "FAILED") for k, v in checks.items()}}
    return Response(
        content=json.dumps(response_content, indent=2),
        status_code=status_code,
        media_type="application/json"
    )


# ------------------------------------------------------------------
# Point d'entrée Uvicorn
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Lancement du service de healthcheck sur http://0.0.0.0:8000/health")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
