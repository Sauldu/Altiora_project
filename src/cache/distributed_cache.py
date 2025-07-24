# src/cache/distributed_cache.py
import redis
import pickle
import zlib
from typing import Optional, Any

class DistributedCache:
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url)
        self.default_ttl = 3600  # 1 heure
        self.stats = {"hits": 0, "misses": 0}

    async def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache"""
        value = await self.redis_client.get(key)
        if value:
            self.stats["hits"] += 1
            return pickle.loads(zlib.decompress(value))
        self.stats["misses"] += 1
        return None

    async def set(self, key: str, value: Any, ttl: int = None):
        """Stocke une valeur dans le cache"""
        ttl = ttl or self.default_ttl
        compressed_value = zlib.compress(pickle.dumps(value))
        await self.redis_client.setex(
            key,
            ttl,
            compressed_value
        )