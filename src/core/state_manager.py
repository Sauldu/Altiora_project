"""
StateManager – Gestionnaire d’état centralisé
Responsabilités :
- Sessions utilisateur
- Cache inter-services
- Progression des pipelines
- Persistance temporaire
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from pathlib import Path

import redis.asyncio as redis
from src.infrastructure.redis_config import get_redis_client


class StateManager:
    """Singleton léger pour l’état global de l’application"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis: Optional[redis.Redis] = None
        self.local_cache: Dict[str, Any] = {}
        self.temp_dir = Path("temp/state")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        """Connexion Redis ou fallback mémoire"""
        try:
            self.redis = await get_redis_client()
        except Exception as e:
            self.redis = None
            print(f"⚠️ Redis non disponible : {e}")

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def create_session(self, user_id: str, metadata: Dict[str, Any]) -> str:
        """Crée une session unique avec TTL 24h"""
        session_id = f"{user_id}_{uuid.uuid4().hex[:8]}"
        data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata,
        }
        if self.redis:
            await self.redis.setex(f"session:{session_id}", 86400, json.dumps(data))
        else:
            self.local_cache[f"session:{session_id}"] = data
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une session"""
        if self.redis:
            raw = await self.redis.get(f"session:{session_id}")
            return json.loads(raw) if raw else None
        return self.local_cache.get(f"session:{session_id}")

    # ------------------------------------------------------------------
    # Progression pipeline
    # ------------------------------------------------------------------

    async def set_pipeline_progress(self, session_id: str, step: str, progress: float) -> None:
        """Met à jour la progression d’un pipeline"""
        key = f"progress:{session_id}"
        data = {"step": step, "progress": progress, "updated_at": datetime.utcnow().isoformat()}
        if self.redis:
            await self.redis.hset(key, step, json.dumps(data))
        else:
            self.local_cache.setdefault(key, {})[step] = data

    async def get_pipeline_progress(self, session_id: str) -> Dict[str, Dict[str, Any]]:
        """Récupère toute la progression"""
        key = f"progress:{session_id}"
        if self.redis:
            raw = await self.redis.hgetall(key)
            return {k: json.loads(v) for k, v in raw.items()}
        return self.local_cache.get(key, {})

    # ------------------------------------------------------------------
    # Cache temporaire
    # ------------------------------------------------------------------

    async def cache_set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Cache court-terme (TTL en secondes)"""
        if self.redis:
            await self.redis.setex(f"cache:{key}", ttl, json.dumps(value))
        else:
            self.local_cache[f"cache:{key}"] = {"value": value, "expires": datetime.utcnow() + timedelta(seconds=ttl)}

    async def cache_get(self, key: str) -> Optional[Any]:
        """Récupère du cache"""
        if self.redis:
            raw = await self.redis.get(f"cache:{key}")
            return json.loads(raw) if raw else None
        item = self.local_cache.get(f"cache:{key}")
        if item and item["expires"] > datetime.utcnow():
            return item["value"]
        self.local_cache.pop(f"cache:{key}", None)
        return None

    # ------------------------------------------------------------------
    # Nettoyage
    # ------------------------------------------------------------------

    async def cleanup_expired(self) -> None:
        """Purge les sessions expirées (si Redis down)"""
        now = datetime.utcnow()
        expired = [k for k, v in self.local_cache.items() if isinstance(v, dict) and v.get("expires", now) < now]
        for k in expired:
            self.local_cache.pop(k, None)

    async def close(self) -> None:
        if self.redis:
            await self.redis.aclose()


# ------------------------------------------------------------------
# Singleton global
# ------------------------------------------------------------------

_state_manager = None
_state_lock = asyncio.Lock()

async def get_state_manager():
    global _state_manager
    if _state_manager is None:
        async with _state_lock:
            if _state_manager is None:  # Double-check pattern
                _state_manager = StateManager()
                await _state_manager.initialize()
    return _state_manager