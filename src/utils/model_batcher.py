# src/utils/model_batcher.py
from typing import List, Dict, Any, Callable, Optional
import asyncio
from collections import defaultdict


class ModelBatcher:
    def __init__(self, model_fn: Callable, batch_size: int = 32, timeout: float = 0.1):
        self.model_fn = model_fn
        self.batch_size = batch_size
        self.timeout = timeout
        self._pending: List[Dict[str, Any]] = []
        self._results: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._timer: Optional[asyncio.Task] = None

    async def add_request(self, request_id: str, data: Any) -> Any:
        future = asyncio.Future()

        async with self._lock:
            self._pending.append({"id": request_id, "data": data})
            self._results[request_id] = future

            # Déclencher le batch si plein
            if len(self._pending) >= self.batch_size:
                await self._process_batch()
            # Sinon, démarrer un timer
            elif self._timer is None:
                self._timer = asyncio.create_task(self._timeout_batch())

        return await future

    async def _process_batch(self):
        if not self._pending:
            return

        # Extraire le batch actuel
        batch = self._pending[:]
        self._pending.clear()

        # Traiter le batch
        try:
            results = await self.model_fn([item["data"] for item in batch])

            # Distribuer les résultats
            for item, result in zip(batch, results):
                self._results[item["id"]].set_result(result)
        except Exception as e:
            # Propager l'erreur à toutes les requêtes du batch
            for item in batch:
                self._results[item["id"]].set_exception(e)
        finally:
            # Nettoyer
            for item in batch:
                self._results.pop(item["id"], None)