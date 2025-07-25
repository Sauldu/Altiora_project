# src/infrastructure/connection_pool.py
"""Module implémentant un pool de connexions asynchrones générique.

Ce module fournit une classe `OllamaConnectionPool` (qui peut être renommée
pour être plus générique) pour gérer un ensemble de connexions réutilisables
vers un service externe (comme Ollama). L'utilisation d'un pool de connexions
permet d'optimiser les performances en réduisant la surcharge liée à l'ouverture
et la fermeture répétées de connexions, et en limitant le nombre de connexions
simultanées.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
import logging

logger = logging.getLogger(__name__)


class OllamaConnectionPool:
    """Pool de connexions pour les interactions avec le service Ollama."

    Gère un ensemble de clients Ollama pré-initialisés pour une réutilisation efficace.
    """

    def __init__(self, host: str, port: int, max_connections: int = 10):
        """Initialise le pool de connexions."

        Args:
            host: L'hôte du service Ollama.
            port: Le port du service Ollama.
            max_connections: Le nombre maximal de connexions à maintenir dans le pool.
        """
        self.host = host
        self.port = port
        self.max_connections = max_connections
        # La queue stocke les clients Ollama disponibles.
        self._pool: asyncio.Queue[Any] = asyncio.Queue(maxsize=max_connections)
        self._initialized = False

    async def initialize(self):
        """Initialise le pool en créant et en pré-remplissant les connexions."

        Cette méthode doit être appelée une fois au démarrage de l'application.
        """
        if self._initialized:
            logger.warning("Le pool de connexions est déjà initialisé.")
            return

        logger.info(f"Initialisation du pool de connexions Ollama avec {self.max_connections} connexions...")
        for i in range(self.max_connections):
            try:
                client = await self._create_client() # Crée un client Ollama (factice pour l'exemple).
                await self._pool.put(client)
                logger.debug(f"Connexion {i+1}/{self.max_connections} ajoutée au pool.")
            except Exception as e:
                logger.error(f"Échec de la création de la connexion {i+1}/{self.max_connections}: {e}")
                # Gérer l'échec de création de connexion (ex: retenter, logguer, lever une exception).
        self._initialized = True
        logger.info("Pool de connexions Ollama initialisé.")

    async def _create_client(self) -> Any:
        """Crée une nouvelle instance de client Ollama (factice pour l'exemple).

        Dans une implémentation réelle, cela créerait une session aiohttp ou un client Ollama.
        """
        # Simule la création d'un client.
        await asyncio.sleep(0.1) # Simule un délai de connexion.
        logger.debug(f"Client Ollama factice créé pour {self.host}:{self.port}")
        return f"OllamaClient({self.host}:{self.port})"

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Any, None]:
        """Acquiert une connexion depuis le pool."

        Utilisation avec `async with`:
        ```python
        async with pool.acquire() as client:
            # Utilise le client ici.
            pass
        ```
        """
        if not self._initialized:
            raise RuntimeError("Le pool de connexions n'a pas été initialisé. Appelez `initialize()` d'abord.")

        client = await self._pool.get() # Récupère un client du pool.
        logger.debug(f"Connexion acquise : {client}. Taille du pool restante : {self._pool.qsize()}")
        try:
            yield client
        finally:
            await self._pool.put(client) # Remet le client dans le pool.
            logger.debug(f"Connexion relâchée : {client}. Taille du pool : {self._pool.qsize()}")

    async def close(self):
        """Ferme toutes les connexions du pool."

        Cette méthode doit être appelée lors de l'arrêt de l'application pour
        libérer toutes les ressources.
        """
        if not self._initialized:
            return
        logger.info("Fermeture du pool de connexions Ollama...")
        while not self._pool.empty():
            client = await self._pool.get_nowait()
            # Dans une implémentation réelle, vous fermeriez la connexion ici.
            logger.debug(f"Fermeture du client : {client}")
        self._initialized = False
        logger.info("Pool de connexions Ollama fermé.")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        pool = OllamaConnectionPool(host="localhost", port=11434, max_connections=3)
        await pool.initialize()

        print("\n--- Utilisation du pool de connexions ---")
        async def use_client(task_id: int):
            async with pool.acquire() as client:
                print(f"Tâche {task_id} : Utilisation du client {client}")
                await asyncio.sleep(0.5) # Simule un travail.
                print(f"Tâche {task_id} : Fin d'utilisation du client {client}")

        # Lance plusieurs tâches qui vont acquérir des connexions du pool.
        tasks = [use_client(i) for i in range(5)]
        await asyncio.gather(*tasks)

        print("\n--- Fermeture du pool ---")
        await pool.close()
        print("Démonstration terminée.")

    asyncio.run(demo())