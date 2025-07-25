# src/middleware/cache_middleware.py
"""Middleware de cache pour les requêtes HTTP.

Ce middleware intercepte les requêtes HTTP et tente de servir les réponses
depuis un cache Redis. Si la réponse n'est pas en cache, la requête est
transmise à l'application, et la réponse est ensuite stockée dans Redis
pour les requêtes futures. Il utilise la compression pour optimiser
l'espace de stockage dans Redis.
"""

import time
import logging

from fastapi import Request, Response
from src.infrastructure.redis_config import get_redis_client
from src.utils.compression import compress_data, decompress_data

logger = logging.getLogger(__name__)


async def cache_middleware(request: Request, call_next):
    """Middleware de cache pour les requêtes FastAPI."

    Args:
        request: L'objet `Request` de FastAPI.
        call_next: La fonction pour passer la requête au prochain middleware ou à l'endpoint.

    Returns:
        L'objet `Response` de FastAPI, potentiellement servi depuis le cache.
    """
    start_time = time.time()
    redis_client = await get_redis_client()
    
    # Génère une clé de cache unique basée sur la méthode et l'URL de la requête.
    cache_key = f"cache:{request.method}:{request.url.path}"

    # Tente de récupérer la réponse depuis le cache Redis.
    cached_response = await redis_client.get(cache_key)
    
    if cached_response:
        try:
            # Si la réponse est en cache, la décompresse et la décode.
            response_data = decompress_data(cached_response)
            response = Response(content=response_data, media_type="application/json")
            response.headers["X-Cache"] = "HIT"
            logger.info(f"Cache HIT pour {request.url.path}")
        except Exception as e:
            logger.error(f"Erreur lors de la lecture/décompression du cache pour {request.url.path}: {e}")
            # En cas d'erreur de cache, on passe à l'application.
            response = await call_next(request)
            response.headers["X-Cache"] = "MISS_ERROR"
    else:
        # Si la réponse n'est pas en cache, passe la requête à l'application.
        response = await call_next(request)
        response.headers["X-Cache"] = "MISS"
        logger.info(f"Cache MISS pour {request.url.path}")

        # Si la réponse est un succès (200 OK), la stocke dans le cache.
        if response.status_code == 200:
            # Lit le corps de la réponse pour le mettre en cache.
            # Note: response.body est un bytes, il faut le décoder pour le compresser en string.
            response_body = response.body.decode('utf-8')
            compressed_data = compress_data(response_body)
            # Stocke dans Redis avec une expiration de 5 minutes (300 secondes).
            await redis_client.setex(cache_key, 300, compressed_data)
            logger.info(f"Réponse pour {request.url.path} mise en cache.")

    # Ajoute un en-tête pour le temps de réponse.
    response.headers["X-Response-Time"] = str(time.time() - start_time)
    return response


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import uvicorn

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    app = FastAPI()

    # Applique le middleware de cache.
    app.middleware("http")(cache_middleware)

    @app.get("/items/{item_id}")
    async def read_item(item_id: int):
        """Endpoint de démonstration qui simule un travail long."""
        logger.info(f"Traitement de la requête pour item_id: {item_id} (non mis en cache)...")
        await asyncio.sleep(1) # Simule un travail long.
        return {"item_id": item_id, "data": "Données générées", "timestamp": datetime.datetime.now().isoformat()}

    async def run_demo_client():
        print("\n--- Lancement du client de démonstration ---")
        client = TestClient(app)

        print("Premier appel à /items/1 (devrait être MISS)...")
        response1 = client.get("/items/1")
        print(f"Statut: {response1.status_code}, Cache: {response1.headers.get('X-Cache')}, Temps: {response1.headers.get('X-Response-Time')[:5]}s")

        print("\nDeuxième appel à /items/1 (devrait être HIT)...")
        response2 = client.get("/items/1")
        print(f"Statut: {response2.status_code}, Cache: {response2.headers.get('X-Cache')}, Temps: {response2.headers.get('X-Response-Time')[:5]}s")

        print("\nTroisième appel à /items/2 (nouvelle clé, devrait être MISS)...")
        response3 = client.get("/items/2")
        print(f"Statut: {response3.status_code}, Cache: {response3.headers.get('X-Cache')}, Temps: {response3.headers.get('X-Response-Time')[:5]}s")

        print("\nAttente de 6 secondes pour l'expiration du cache...")
        await asyncio.sleep(6)

        print("\nQuatrième appel à /items/1 (après expiration, devrait être MISS)...")
        response4 = client.get("/items/1")
        print(f"Statut: {response4.status_code}, Cache: {response4.headers.get('X-Cache')}, Temps: {response4.headers.get('X-Response-Time')[:5]}s")

        print("Démonstration du cache middleware terminée.")

    # Lance le serveur Uvicorn en arrière-plan pour la démo.
    # Assurez-vous qu'un serveur Redis est en cours d'exécution sur localhost:6379.
    async def run_server_and_client():
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        await asyncio.sleep(1) # Donne le temps au serveur de démarrer.
        await run_demo_client()
        server_task.cancel()

    asyncio.run(run_server_and_client())