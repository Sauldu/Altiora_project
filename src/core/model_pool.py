# src/core/model_pool.py
"""Module implémentant un pool de modèles d'IA pré-chargés et réutilisables.

Ce pool vise à optimiser les performances en réduisant le temps de "cold start"
des modèles, en limitant les connexions simultanées et en facilitant le
load-balancing interne. Il est particulièrement utile pour les modèles de langage
qui peuvent être coûteux à initialiser.
"""

from asyncio import Queue
from typing import Any, Callable, TypeVar, Generic

from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface

T = TypeVar('T') # Type générique pour les modèles dans le pool.


class ModelPool(Generic[T]):
    """Pool de modèles IA pré-chargés et réutilisables.

    Permet de gérer un ensemble d'instances de modèles, de les pré-initialiser
    et de les réutiliser pour optimiser les performances et la gestion des ressources.
    """

    def __init__(
            self,
            factory: Callable[[], T],
            pool_size: int = 3,
    ) -> None:
        """Initialise le pool de modèles.

        Args:
            factory: Une fonction asynchrone (coroutine) qui, lorsqu'elle est appelée,
                     crée et initialise une nouvelle instance du modèle.
            pool_size: Le nombre d d'instances de modèles à maintenir dans le pool.
        """
        self._factory = factory
        self._pool: Queue[T] = Queue(maxsize=pool_size)
        self._pool_size = pool_size
        self._closed = False

    # ------------------------------------------------------------------
    # Initialisation asynchrone du pool
    # ------------------------------------------------------------------

    async def _initialize_pool(self) -> None:
        """Pré-charge les modèles dans la queue du pool."""
        for _ in range(self._pool_size):
            model = await self._factory()
            await self._pool.put(model)

    async def open(self) -> None:
        """Ouvre le pool et initialise les modèles. Doit être appelé avant d'utiliser le pool."""
        await self._initialize_pool()

    # ------------------------------------------------------------------
    # Acquisition et restitution des modèles
    # ------------------------------------------------------------------

    async def acquire(self) -> T:
        """Récupère une instance de modèle du pool.

        Bloque l'exécution si le pool est vide jusqu'à ce qu'un modèle soit disponible.

        Returns:
            Une instance du modèle prête à l'emploi.

        Raises:
            RuntimeError: Si le pool est fermé.
        """
        if self._closed:
            raise RuntimeError("Le pool est fermé et ne peut plus fournir de modèles.")
        return await self._pool.get()

    async def release(self, model: T) -> None:
        """Remet une instance de modèle dans le pool après utilisation.

        Args:
            model: L'instance du modèle à remettre dans le pool.
        """
        if self._closed:
            # Si le pool est fermé, ne remet pas le modèle, il sera nettoyé à l'arrêt.
            return
        await self._pool.put(model)

    # ------------------------------------------------------------------
    # Gestionnaire de contexte asynchrone
    # ------------------------------------------------------------------

    async def context(self) -> T:
        """Permet d'utiliser le pool avec la syntaxe `async with`.

        Exemple:
        ```python
        async with my_model_pool.context() as model:
            # Utilise le modèle ici.
            pass
        ```
        """
        model = await self.acquire()
        try:
            yield model
        finally:
            await self.release(model)

    # ------------------------------------------------------------------
    # Fermeture du pool
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Ferme proprement toutes les instances de modèles dans le pool.

        Appelle la méthode `close()` sur chaque modèle si elle existe.
        """
        self._closed = True
        while not self._pool.empty():
            model = await self._pool.get()
            if hasattr(model, "close") and callable(getattr(model, "close")):
                await model.close()

    # ------------------------------------------------------------------
    # Fabrique utilitaire pour Qwen3
    # ------------------------------------------------------------------

    @classmethod
    async def create_qwen3_pool(
            cls,
            pool_size: int = 3,
            ollama_url: str = "http://localhost:11434",
    ) -> "ModelPool[Qwen3OllamaInterface]":
        """Fabrique prête à l'emploi pour créer un pool de modèles Qwen3.

        Args:
            pool_size: Le nombre d'instances Qwen3 à maintenir dans le pool.
            ollama_url: L'URL de l'instance Ollama à laquelle Qwen3 doit se connecter.

        Returns:
            Une instance de `ModelPool` configurée pour Qwen3.
        """
        async def _make_qwen3():
            q = Qwen3OllamaInterface(base_url=ollama_url)
            await q.initialize()
            return q

        pool = cls(factory=_make_qwen3, pool_size=pool_size)
        await pool.open()
        return pool


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    class MockModel:
        """Modèle factice pour la démonstration du pool."""
        def __init__(self, name: str):
            self.name = name
            self.initialized = False
            logging.info(f"MockModel {self.name} créé.")

        async def initialize(self):
            await asyncio.sleep(0.1) # Simule l'initialisation.
            self.initialized = True
            logging.info(f"MockModel {self.name} initialisé.")

        async def process(self, data: str) -> str:
            if not self.initialized:
                raise RuntimeError(f"MockModel {self.name} non initialisé.")
            await asyncio.sleep(0.05) # Simule le traitement.
            return f"MockModel {self.name} a traité : {data}"

        async def close(self):
            logging.info(f"MockModel {self.name} fermé.")

    async def mock_model_factory():
        """Fabrique asynchrone pour les MockModels."""
        model = MockModel(f"model-{uuid.uuid4().hex[:4]}")
        await model.initialize()
        return model

    async def demo_model_pool():
        print("\n--- Démonstration du ModelPool ---")
        pool = ModelPool(factory=mock_model_factory, pool_size=2)
        await pool.open()

        print("Acquisition et utilisation de modèles...")
        async with pool.context() as m1:
            print(await m1.process("donnée 1"))
        
        async with pool.context() as m2:
            print(await m2.process("donnée 2"))

        async with pool.context() as m3:
            print(await m3.process("donnée 3")) # Réutilise un modèle du pool.

        print("Fermeture du pool...")
        await pool.close()
        print("Démonstration terminée.")

    asyncio.run(demo_model_pool())