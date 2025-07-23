# src/middleware/cache_middleware.py
from fastapi import Request, Response
from infrastructure.redis_config import get_redis_client
from src.utils.compression import compress_data, decompress_data
import time


async def cache_middleware(request: Request, call_next):
    start_time = time.time()
    client = get_redis_client()
    cache_key = f"{request.method}:{request.url.path}"

    # Vérifier si la réponse est dans le cache
    cached_response = client.get(cache_key)
    if cached_response:
        response_data = decompress_data(cached_response)
        response = Response(content=response_data, media_type="application/json")
        response.headers["X-Cache"] = "HIT"
    else:
        response = await call_next(request)
        response.headers["X-Cache"] = "MISS"

        # Stocker la réponse dans le cache
        if response.status_code == 200:
            compressed_data = compress_data(response.body.decode('utf-8'))
            client.set(cache_key, compressed_data, ex=300)  # Cache pendant 5 minutes

    response.headers["X-Response-Time"] = str(time.time() - start_time)
    return response