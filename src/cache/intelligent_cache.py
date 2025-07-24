# src/cache/intelligent_cache.py
from datetime import timedelta
from typing import Any, Callable

from src.cache.distributed_cache import DistributedCache


class IntelligentCache:
    def __init__(self, redis_url: str):
        self.cache = DistributedCache(redis_url)
        self.stats = {"hits": 0, "misses": 0}

    async def get_or_compute(
            self,
            key: str,
            compute_fn: Callable,
            ttl: timedelta = timedelta(hours=1),
            compression: bool = True
    ) -> Any:
        # Tentative de récupération depuis le cache
        cached = await self.cache.get(key)

        if cached:
            self.stats["hits"] += 1
            return cached

        # Calcul et mise en cache
        self.stats["misses"] += 1
        result = await compute_fn()

        # Sérialisation avec compression optionnelle
        await self.cache.set(key, result, ttl=int(ttl.total_seconds()))
        return result

    async def invalidate_pattern(self, pattern: str):
        """Invalider par pattern"""
        await self.cache.invalidate_pattern(pattern)

    @staticmethod
    def make_key(*parts) -> str:
        """Créer une clé de cache"""
        key_str = ":".join(str(p) for p in parts)
        return f"altiora:cache:{key_str}"
