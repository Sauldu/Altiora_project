# src/core/model_pool.py
from asyncio import Queue
from typing import Any, Callable

from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface


class ModelPool:
    """
    Pool de modèles IA pré-chargés et réutilisables.
    - Réduit le temps de « cold start »
    - Limite les connexions simultanées
    - Facilite le load-balancing interne
    """

    def __init__(
            self,
            factory: Callable[[], Any],
            pool_size: int = 3,
    ) -> None:
        """
        factory : fonction coroutine qui crée et initialise un modèle
        pool_size : nombre de modèles gardés en mémoire
        """
        self._factory = factory
        self._pool: Queue[Any] = Queue(maxsize=pool_size)
        self._pool_size = pool_size
        self._closed = False

    # ------------------------------------------------------------------
    # Initialisation asynchrone
    # ------------------------------------------------------------------

    async def _initialize_pool(self) -> None:
        """Pré-charge les modèles dans la queue."""
        for _ in range(self._pool_size):
            model = await self._factory()
            await self._pool.put(model)

    async def open(self) -> None:
        await self._initialize_pool()

    # ------------------------------------------------------------------
    # Acquisition / restitution
    # ------------------------------------------------------------------

    async def acquire(self) -> Any:
        """Récupère un modèle du pool (bloque si vide)."""
        if self._closed:
            raise RuntimeError("Pool fermé")
        return await self._pool.get()

    async def release(self, model: Any) -> None:
        """Rend le modèle au pool."""
        if self._closed:
            return
        await self._pool.put(model)

    # ------------------------------------------------------------------
    # Context-manager
    # ------------------------------------------------------------------

    async def context(self) -> Any:
        """Utilisation simplifiée via async context manager."""
        model = await self.acquire()
        try:
            yield model
        finally:
            await self.release(model)

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Ferme proprement toutes les instances."""
        self._closed = True
        while not self._pool.empty():
            model = await self._pool.get()
            if hasattr(model, "close"):
                await model.close()

    # ------------------------------------------------------------------
    # Utilitaire rapide
    # ------------------------------------------------------------------

    @classmethod
    async def create_qwen3_pool(
            cls,
            pool_size: int = 3,
            ollama_url: str = "http://localhost:11434",
    ) -> "ModelPool":
        """
        Factory prête à l’emploi pour Qwen3.
        """

        async def _make_qwen3():
            q = Qwen3OllamaInterface(base_url=ollama_url)
            await q.initialize()
            return q

        pool = cls(factory=_make_qwen3, pool_size=pool_size)
        await pool.open()
        return pool
