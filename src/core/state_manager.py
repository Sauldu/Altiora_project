"""
StateManager – gestionnaire d’état centralisé basé sur Redis
- Pipeline progress
- Session state
- Cache court terme
- Fallback mémoire si Redis est down
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis.asyncio as redis


class StateManager:
    """Singleton-like state manager with Redis & memory fallback"""

    def __init__(self, redis_url: str, *, ttl: int = 3600) -> None:
        self._redis_url: str = redis_url
        self._ttl: int = ttl
        self._redis: Optional[redis.Redis] = None
        self._memory_cache: Dict[str, Any] = {}  # fallback

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Connect or fallback to memory"""
        try:
            self._redis = await redis.from_url(
                self._redis_url, decode_responses=True
            )
            await self._redis.ping()  # health check
        except Exception as exc:
            self._redis = None
            logger.info(f"⚠️  Redis unavailable – using memory fallback: {exc}")

    async def close(self) -> None:
        """Graceful shutdown"""
        if self._redis:
            await self._redis.aclose()

    # ------------------------------------------------------------------
    # Pipeline progress
    # ------------------------------------------------------------------

    async def set_pipeline_progress(
            self, session_id: str, step: str, progress: float
    ) -> None:
        key = f"pipeline:{session_id}:{step}"
        value = {"progress": progress, "updated": datetime.utcnow().isoformat()}
        await self._set(key, value)

    async def get_pipeline_progress(self, session_id: str) -> Dict[str, Any]:
        pattern = f"pipeline:{session_id}:*"
        if self._redis:
            keys = await self._redis.keys(pattern)
            data = await asyncio.gather(*[self._get(k) for k in keys])
            return {k.split(":", 2)[-1]: v for k, v in zip(keys, data) if v}
        # fallback
        return {
            k.split(":", 2)[-1]: v
            for k, v in self._memory_cache.items()
            if k.startswith(pattern)
        }

    # ------------------------------------------------------------------
    # Session state
    # ------------------------------------------------------------------

    async def set_session(self, session_id: str, data: Dict[str, Any]) -> None:
        key = f"session:{session_id}"
        await self._set(key, data)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        key = f"session:{session_id}"
        return await self._get(key)

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    async def _set(self, key: str, value: Any) -> None:
        if self._redis:
            await self._redis.setex(key, self._ttl, json.dumps(value))
        else:
            self._memory_cache[key] = {
                "data": value,
                "expires": datetime.utcnow() + timedelta(seconds=self._ttl),
            }

    async def _get(self, key: str) -> Optional[Dict[str, Any]]:
        if self._redis:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None

        # memory fallback
        item = self._memory_cache.get(key)
        if item and item.get("expires", datetime.min) > datetime.utcnow():
            return item["data"]
        self._memory_cache.pop(key, None)
        return None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health(self) -> bool:
        """Return True if Redis is up, False otherwise"""
        if not self._redis:
            return False
        try:
            return await self._redis.ping()
        except Exception:
            return False


# ------------------------------------------------------------------
# Singleton helper
# ------------------------------------------------------------------

_state_manager: Optional[StateManager] = None


async def get_state_manager(redis_url: str = "redis://localhost:6379") -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager(redis_url)
        await _state_manager.initialize()
    return _state_manager
