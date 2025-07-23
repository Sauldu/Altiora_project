# src/cache/intelligent_cache.py
import hashlib
import pickle
from typing import Optional, Any, Callable
from datetime import datetime, timedelta


class IntelligentCache:
    """Cache avec stratégies intelligentes"""

    def __init__(self, redis_client, default_ttl: int = 3600):
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.stats = CacheStats()

    async def get_or_compute(
            self,
            key: str,
            compute_fn: Callable,
            ttl: Optional[int] = None,
            cache_condition: Optional[Callable] = None
    ) -> Any:
        """Récupérer du cache ou calculer"""
        # Vérifier le cache
        cached = await self.get(key)
        if cached is not None:
            self.stats.hit()
            return cached

        # Calculer la valeur
        self.stats.miss()
        value = await compute_fn()

        # Vérifier si on doit mettre en cache
        if cache_condition is None or cache_condition(value):
            await self.set(key, value, ttl)

        return value

    async def invalidate_pattern(self, pattern: str):
        """Invalider par pattern"""
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=pattern,
                count=100
            )
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break

    @staticmethod
    def make_key(*parts) -> str:
        """Créer une clé de cache"""
        key_str = ":".join(str(p) for p in parts)
        return f"altiora:cache:{key_str}"


# Décorateur de cache
def cached(ttl: int = 3600, key_prefix: str = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Générer la clé
            cache_key = generate_cache_key(
                key_prefix or func.__name__,
                args,
                kwargs
            )

            # Utiliser le cache
            return await self.cache.get_or_compute(
                cache_key,
                lambda: func(self, *args, **kwargs),
                ttl=ttl
            )

        return wrapper

    return decorator