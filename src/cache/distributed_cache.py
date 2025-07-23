# src/cache/distributed_cache.py
import redis
import pickle
from typing import Optional, Any


class DistributedCache:
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url)
        self.default_ttl = 3600  # 1 heure

    async def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache"""
        value = await self.redis_client.get(key)
        return pickle.loads(value) if value else None

    async def set(self, key: str, value: Any, ttl: int = None):
        """Stocke une valeur dans le cache"""
        ttl = ttl or self.default_ttl
        await self.redis_client.setex(
            key,
            ttl,
            pickle.dumps(value)
        )