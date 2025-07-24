# src/cache/intelligent_cache.py
import asyncio
import time
from datetime import timedelta
from typing import Any, Callable, Dict, Optional

import numpy as np
from sklearn.linear_model import SGDRegressor  # ~50 Ko en RAM

from src.cache.distributed_cache import DistributedCache


class TTLModel:
    """
    Modèle ultra-léger (SGDRegressor) pour prédire le TTL optimal.
    Features : taille, temps depuis dernier accès, nombre d’accès, heure de la journée.
    """

    def __init__(self) -> None:
        self.model = SGDRegressor(learning_rate="constant", eta0=0.01)
        self.is_fitted = False

    def _features(self, meta: Dict[str, Any]) -> np.ndarray:
        return np.array(
            [
                meta.get("size", 0),
                meta.get("age", 0),
                meta.get("hits", 0),
                time.localtime().tm_hour,
            ],
            dtype=float,
        ).reshape(1, -1)

    def predict_ttl(self, meta: Dict[str, Any]) -> int:
        """Retourne TTL en secondes (borne entre 60 et 86 400)."""
        if not self.is_fitted:
            return 3600  # fallback
        secs = max(60, int(self.model.predict(self._features(meta))[0]))
        return min(secs, 86400)

    def partial_fit(self, meta: Dict[str, Any], actual_ttl: int) -> None:
        """Mise à jour incrémentale après expiration réelle."""
        X = self._features(meta)
        y = np.array([actual_ttl])
        self.model.partial_fit(X, y)
        self.is_fitted = True


class IntelligentCache:
    """
    Cache distribué avec TTL prédit par ML et invalidation intelligente.
    """

    def __init__(self, redis_url: str) -> None:
        self.cache = DistributedCache(redis_url)
        self.ttl_model = TTLModel()
        self.stats: Dict[str, Any] = {"hits": 0, "misses": 0, "model_updates": 0}

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        *,
        ttl: Optional[int] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Récupère depuis le cache ou calcule.
        Le TTL est prédit par défaut si non fourni.
        """
        cached = await self.cache.get(key)
        if cached:
            self.stats["hits"] += 1
            return cached

        self.stats["misses"] += 1
        value = await compute_fn()

        if ttl is None:
            # Prédiction TTL
            meta = meta or {}
            meta.update(size=len(str(value)), age=0, hits=0)
            ttl = self.ttl_model.predict_ttl(meta)

        await self.cache.set(key, value, ttl=ttl)

        # Stockage des métadonnées pour apprentissage
        await self._store_meta(key, meta or {}, ttl)
        return value

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalide toutes les clés correspondant au pattern."""
        # Implémentation via SCAN + DEL
        cur = b"0"
        while cur:
            cur, keys = await self.cache.redis_client.scan(
                cur, match=pattern, count=100
            )
            if keys:
                await self.cache.redis_client.delete(*keys)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(*parts: str) -> str:
        return f"altiora:cache:{':'.join(str(p) for p in parts)}"

    async def _store_meta(self, key: str, meta: Dict[str, Any], ttl: int) -> None:
        """Sauvegarde les métadonnées dans Redis (clé avec suffixe _meta)."""
        meta_key = f"{key}:meta"
        meta.update(ttl=ttl, stored_at=int(time.time()))
        await self.cache.redis_client.setex(
            meta_key, ttl, str(meta).encode()
        )

    async def _load_meta(self, key: str) -> Dict[str, Any]:
        """Charge les métadonnées depuis Redis."""
        raw = await self.cache.redis_client.get(f"{key}:meta")
        if raw:
            return eval(raw.decode())  # Safe car contrôlé
        return {}

    # ------------------------------------------------------------------
    # Boucle d'apprentissage asynchrone
    # ------------------------------------------------------------------

    async def feedback_loop(self) -> None:
        """
        Tâche de fond qui observe les expirations réelles
        et met à jour le modèle.
        """
        while True:
            await asyncio.sleep(300)  # toutes les 5 minutes
            cursor = b"0"
            while cursor:
                cursor, keys = await self.cache.redis_client.scan(
                    cursor, match="*:meta", count=100
                )
                for meta_key in keys:
                    key = meta_key.decode().replace(":meta", "")
                    meta = await self._load_meta(key)
                    if not meta:
                        continue

                    # Si la clé principale a disparu → expiration réelle
                    if not await self.cache.redis_client.exists(key):
                        actual_ttl = int(time.time()) - meta.get("stored_at", 0)
                        self.ttl_model.partial_fit(meta, actual_ttl)
                        self.stats["model_updates"] += 1
                        await self.cache.redis_client.delete(meta_key)