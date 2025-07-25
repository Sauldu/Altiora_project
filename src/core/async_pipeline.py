# src/core/async_pipeline.py
"""Module pour la gestion de pipelines asynchrones légers.

Ce module fournit une implémentation d'un pipeline asynchrone avec des
fonctionnalités de concurrence configurable, de gestion des erreurs et la
possibilité d'utiliser un processeur de tâches personnalisé.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class AsyncPipeline:
    """Pipeline asynchrone léger avec gestion de la concurrence et des erreurs.

    Permet de soumettre des tâches qui seront traitées par un ensemble de workers
    en parallèle, avec un contrôle sur le nombre de tâches concurrentes.
    """

    def __init__(
            self,
            *,
            max_concurrent: int = 4,
            processor: Callable[[Any], Awaitable[None]] | None = None,
    ) -> None:
        """Initialise le pipeline asynchrone.

        Args:
            max_concurrent: Le nombre maximal de tâches qui peuvent être exécutées
                            simultanément par les workers du pipeline.
            processor: Une fonction asynchrone (`Callable[[Any], Awaitable[None]]`)
                       qui sera appelée pour traiter chaque tâche soumise. Si non
                       fourni, un processeur par défaut qui loggue un avertissement
                       sera utilisé.
        """
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.workers: list[asyncio.Task[None]] = []
        self.max_concurrent = max_concurrent
        self.processor = processor or self._default_processor

    # ------------------------------------------------------------------
    # Cycle de vie du pipeline
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Démarre les coroutines des workers du pipeline.

        Crée un nombre `max_concurrent` de workers qui commenceront à consommer
        les tâches de la queue.
        """
        for idx in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(f"worker-{idx}"))
            self.workers.append(worker)
        logger.info("Démarrage de %d workers de pipeline.", self.max_concurrent)

    async def stop(self) -> None:
        """Annule tous les workers de manière gracieuse et attend leur terminaison.

        Cette méthode doit être appelée pour arrêter proprement le pipeline et
        libérer les ressources.
        """
        for w in self.workers:
            w.cancel()
        # Attend que toutes les tâches soient annulées ou terminées.
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("Pipeline arrêté.")

    async def submit(self, task: Any) -> None:
        """Soumet une tâche au pipeline pour traitement.

        La tâche est placée dans la queue et sera traitée par un worker disponible.

        Args:
            task: La tâche à traiter. Peut être de n'importe quel type.
        """
        await self.queue.put(task)

    # ------------------------------------------------------------------
    # Fonctions internes
    # ------------------------------------------------------------------
    async def _worker(self, name: str) -> None:
        """Boucle principale d'un worker de pipeline.

        Le worker récupère les tâches de la queue, les traite en utilisant
        le `processor` configuré, et marque la tâche comme terminée.
        Gère les annulations et les exceptions.

        Args:
            name: Le nom du worker (pour le logging).
        """
        while True:
            try:
                task = await self.queue.get()
                await self.processor(task)
                self.queue.task_done()
            except asyncio.CancelledError:
                # Le worker a été annulé, il doit s'arrêter.
                break
            except Exception as e:
                # Loggue l'exception mais continue de traiter les autres tâches.
                logger.exception("Le worker %s n'a pas pu traiter la tâche : %s", name, e)
                self.queue.task_done()

    # ------------------------------------------------------------------
    # Processeur par défaut (peut être surchargé)
    # ------------------------------------------------------------------
    @staticmethod
    async def _default_processor(task: Any) -> None:
        """Processeur de tâches par défaut si aucun n'est fourni.

        Ce processeur loggue un avertissement et ne fait rien d'autre,
        indiquant qu'une tâche a été soumise sans gestion spécifique.

        Args:
            task: La tâche qui n'a pas été traitée.
        """
        logger.warning("Aucun processeur personnalisé fourni – tâche ignorée : %s", task)


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def sample_processor(item: int) -> None:
        """Un exemple de processeur de tâches qui simule un travail asynchrone."""
        print(f"Traitement de l'élément : {item}")
        await asyncio.sleep(0.1) # Simule un travail asynchrone.
        if item == 5:
            raise ValueError("Erreur simulée pour l'élément 5")

    async def demo_pipeline():
        logging.basicConfig(level=logging.INFO)
        
        # Crée un pipeline avec 2 workers et notre processeur personnalisé.
        pipeline = AsyncPipeline(max_concurrent=2, processor=sample_processor)
        await pipeline.start()

        print("Soumission des tâches...")
        for i in range(10):
            await pipeline.submit(i)

        # Attend que toutes les tâches soumises soient traitées.
        await pipeline.queue.join()
        print("Toutes les tâches soumises ont été traitées.")

        await pipeline.stop()
        print("Démonstration du pipeline terminée.")

    asyncio.run(demo_pipeline())