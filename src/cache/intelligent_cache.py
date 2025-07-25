# src/cache/intelligent_cache.py
import asyncio
import pickle
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set

import aiofiles
import numpy as np
from sklearn.linear_model import SGDRegressor

from src.cache.distributed_cache import DistributedCache


class TTLModel:
    def __init__(self) -> None:
        self.model = SGDRegressor(learning_rate="constant", eta0=0.01)
        self.is_fitted = False

    @staticmethod
    def _features(meta: Dict[str, Any]) -> np.ndarray:
        return np.array([
            meta.get("size", 0),
            meta.get("age", 0),
            meta.get("hits", 0),
            time.localtime().tm_hour,
        ], dtype=float).reshape(1, -1)

    def predict_ttl(self, meta: Dict[str, Any]) -> int:
        if not self.is_fitted:
            return 3600
        secs = max(60, int(self.model.predict(self._features(meta))[0]))
        return min(secs, 86400)

    def partial_fit(self, meta: Dict[str, Any], actual_ttl: int) -> None:
        X = self._features(meta)
        y = np.array([actual_ttl])
        self.model.partial_fit(X, y)
        self.is_fitted = True


class IntelligentCache:
    """
    Cache hiérarchique :
        L1 : RAM (dict)
        L2 : Redis
        L3 : Disque local
    Avec pré-chargement et invalidation intelligente.
    """

    def __init__(
            self,
            redis_url: str,
            disk_cache_dir: Path = Path("./cache/l3"),
            max_ram_items: int = 1000,
    ) -> None:
        self.l1: Dict[str, Any] = {}  # RAM
        self.l1_lock = asyncio.Lock()
        self.l2 = DistributedCache(redis_url)  # Redis
        self.l3_dir = disk_cache_dir
        self.l3_dir.mkdir(parents=True, exist_ok=True)
        self.max_ram_items = max_ram_items
        self.ttl_model = TTLModel()
        self.stats = {"l1_hit": 0, "l2_hit": 0, "l3_hit": 0, "miss": 0, "preload": 0}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_compute(
            self,
            key: str,
            compute_fn: Callable[[], Any],
            *,
            ttl: Optional[int] = None,
            preload: bool = False,
    ) -> Any:
        if preload:
            asyncio.create_task(self._preload_patterns([key]))

        # L1
        async with self.l1_lock:
            if key in self.l1:
                self.stats["l1_hit"] += 1
                return self.l1[key]

        # L2
        val = await self.l2.get(key)
        if val is not None:
            self.stats["l2_hit"] += 1
            await self._promote_to_l1(key, val)
            return val

        # L3
        val = await self._l3_get(key)
        if val is not None:
            self.stats["l3_hit"] += 1
            await self.l2.set(key, val, ttl=ttl or 3600)
            await self._promote_to_l1(key, val)
            return val

        # Compute + remplir tous les niveaux
        self.stats["miss"] += 1
        val = await compute_fn()
        await self._store_all_levels(key, val, ttl)
        return val

    async def invalidate(self, pattern: str) -> None:
        """
        Invalidation globale : L1, L2 (Redis pattern), L3.
        """
        async with self.l1_lock:
            for k in list(self.l1.keys()):
                if pattern in k:
                    del self.l1[k]

        await self.l2.invalidate_pattern(pattern)

        # Suppression fichiers L3
        for path in self.l3_dir.glob(f"*{pattern}*"):
            path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Pré-chargement
    # ------------------------------------------------------------------

    async def preload_keys(self, keys: Set[str]) -> None:
        """
        Charge en arrière-plan les clés les plus fréquentes dans L1.
        """
        for k in keys:
            if await self.l2.redis_client.exists(k):
                val = await self.l2.get(k)
                if val:
                    await self._promote_to_l1(k, val)
                    self.stats["preload"] += 1

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _promote_to_l1(self, key: str, value: Any) -> None:
        async with self.l1_lock:
            if len(self.l1) >= self.max_ram_items:
                # Simple LRU : pop first
                self.l1.pop(next(iter(self.l1)))
            self.l1[key] = value

    async def _store_all_levels(self, key: str, value: Any, ttl: Optional[int]) -> None:
        meta = {"size": len(pickle.dumps(value)), "age": 0, "hits": 0}
        ttl = ttl or self.ttl_model.predict_ttl(meta)

        # L1
        await self._promote_to_l1(key, value)
        # L2
        await self.l2.set(key, value, ttl=ttl)
        # L3
        await self._l3_set(key, value)

    async def _l3_get(self, key: str) -> Any:
        path = self.l3_dir / f"{key}.pkl"
        if not path.exists():
            return None
        async with aiofiles.open(path, "rb") as f:
            return pickle.loads(await f.read())

    async def _l3_set(self, key: str, value: Any) -> None:
        path = self.l3_dir / f"{key}.pkl"
        async with aiofiles.open(path, "wb") as f:
            await f.write(pickle.dumps(value))

    # ------------------------------------------------------------------
    # Feedback loop (non bloquant)
    # ------------------------------------------------------------------

    async def feedback_loop(self) -> None:
        """Collecte les métriques pour ajuster les TTL."""
        while True:
            await asyncio.sleep(300)
            # Ici tu peux loguer ou ajuster le modèle
            print("📊 Cache stats:", self.stats)

# ---------- CLI optionnel ----------
if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Pré-chargement du cache intelligent")
    parser.add_argument("action", choices=["preload"], help="Action à exécuter")
    parser.add_argument("--keys", nargs="+", required=True, help="Clés à pré-charger")
    parser.add_argument("--redis", default="redis://localhost:6379", help="URL Redis")

    args = parser.parse_args()

    async def cli():
        cache = IntelligentCache(args.redis)
        await cache.preload_keys(set(args.keys))
        logger.info("✅ Pré-chargement terminé.")

    asyncio.run(cli())