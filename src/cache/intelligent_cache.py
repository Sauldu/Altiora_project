# src/cache/intelligent_cache.py
# src/cache/intelligent_cache.py
import pickle
from datetime import timedelta
from typing import Any, Callable


class IntelligentCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.stats = {"hits": 0, "misses": 0}

    async def get_or_compute(
            self,
            key: str,
            compute_fn: Callable,
            ttl: timedelta = timedelta(hours=1),
            compression: bool = True
    ) -> Any:
        # Tentative de récupération depuis le cache
        cached = await self.redis.get(key)

        if cached:
            self.stats["hits"] += 1
            data = pickle.loads(cached)
            if compression:
                import zlib
                data = pickle.loads(zlib.decompress(data))
            return data

        # Calcul et mise en cache
        self.stats["misses"] += 1
        result = await compute_fn()

        # Sérialisation avec compression optionnelle
        data = pickle.dumps(result)
        if compression and len(data) > 1024:  # Compresser si > 1KB
            import zlib
            data = zlib.compress(data)

        await self.redis.setex(key, int(ttl.total_seconds()), data)
        return result

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
