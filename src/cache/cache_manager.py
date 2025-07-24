# src/cache/cache_manager.py
import hashlib
import json
from typing import Callable
from typing import Optional, Any, Dict


class CacheManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.default_ttl = 3600

    @staticmethod
    def create_key(prefix: str, params: Dict[str, Any]) -> str:
        """Create a deterministic cache key"""
        param_str = json.dumps(params, sort_keys=True)
        hash_digest = hashlib.md5(param_str.encode()).hexdigest()
        return f"{prefix}:{hash_digest}"

    async def get_or_compute(
            self,
            key: str,
            compute_func: Callable,
            ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or compute and store"""
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)

        result = await compute_func()
        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(result)
        )
        return result
