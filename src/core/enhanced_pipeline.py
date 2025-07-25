# src/core/enhanced_pipeline.py
"""Module pour la construction de pipelines asynchrones améliorés.

Ce module fournit une classe `AsyncPipeline` qui permet de chaîner des
étapes de traitement asynchrones avec une gestion de la mise en tampon
(buffering) entre les étapes. Cela aide à optimiser le flux de données
et la concurrence dans les workflows complexes.
"""

import asyncio
import logging
from typing import AsyncIterator, TypeVar, Callable, List

logger = logging.getLogger(__name__)

T = TypeVar('T') # Type générique pour les éléments transitant dans le pipeline.


class AsyncPipeline:
    """Construit et exécute un pipeline de traitement asynchrone avec des étapes chaînées."""

    def __init__(self, max_buffer_size: int = 100):
        """Initialise le pipeline asynchrone.

        Args:
            max_buffer_size: La taille maximale des files d'attente (queues) entre les étapes.
                             Cela contrôle la quantité de données qui peuvent être mises en tampon
                             entre les étapes, affectant la consommation de mémoire et le débit.
        """
        self.max_buffer_size = max_buffer_size
        self.stages: List[Callable] = []

    def add_stage(self, func: Callable) -> 'AsyncPipeline':
        """Ajoute une étape (fonction asynchrone) au pipeline.

        Chaque étape est une fonction qui prend un élément en entrée et retourne
        un élément (ou un itérable d'éléments) en sortie.

        Args:
            func: La fonction asynchrone à ajouter comme étape du pipeline.

        Returns:
            L'instance du pipeline pour permettre le chaînage des appels.
        """
        self.stages.append(func)
        return self

    async def _stage_worker(self, stage_func: Callable, input_queue: asyncio.Queue, output_queue: asyncio.Queue):
        """Worker pour une étape individuelle du pipeline.

        Consomme les éléments de `input_queue`, les traite avec `stage_func`,
        et place les résultats dans `output_queue`.
        """
        while True:
            item = await input_queue.get()
            if item is None: # Signal de fin.
                await output_queue.put(None)
                input_queue.task_done()
                break
            try:
                result = await stage_func(item)
                if isinstance(result, AsyncIterator):
                    async for res_item in result:
                        await output_queue.put(res_item)
                else:
                    await output_queue.put(result)
            except Exception as e:
                logger.error(f"Erreur dans l'étape du pipeline : {e}", exc_info=True)
                # Gérer l'erreur : propager, ignorer, etc.
                # Pour l'instant, on propage le None pour signaler un problème.
                await output_queue.put(None)
            finally:
                input_queue.task_done()

    async def process(self, items: AsyncIterator[T]) -> AsyncIterator[T]:
        """Traite un flux d'éléments à travers le pipeline.

        Args:
            items: Un itérateur asynchrone d'éléments à traiter.

        Yields:
            Les éléments traités par le pipeline.
        """
        # Crée une file d'attente pour chaque étape + une pour l'entrée et une pour la sortie.
        queues = [asyncio.Queue(maxsize=self.max_buffer_size)
                  for _ in range(len(self.stages) + 1)]

        # Crée et démarre les workers pour chaque étape du pipeline.
        workers = []
        for i, stage in enumerate(self.stages):
            worker = asyncio.create_task(
                self._stage_worker(stage, queues[i], queues[i + 1])
            )
            workers.append(worker)

        # Alimente la première queue avec les éléments d'entrée.
        async for item in items:
            await queues[0].put(item)

        # Signale la fin de l'entrée à la première queue.
        await queues[0].put(None)

        # Récupère les résultats de la dernière queue.
        while True:
            result = await queues[-1].get()
            if result is None: # Signal de fin de traitement.
                break
            yield result

        # Attend que tous les workers aient terminé leur traitement.
        await asyncio.gather(*workers)


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def generate_numbers(count: int) -> AsyncIterator[int]:
        """Générateur asynchrone de nombres."""
        for i in range(count):
            await asyncio.sleep(0.01) # Simule un travail.
            yield i

    async def double_number(num: int) -> int:
        """Étape 1: Double un nombre."""
        await asyncio.sleep(0.02)
        return num * 2

    async def add_ten(num: int) -> int:
        """Étape 2: Ajoute dix à un nombre."""
        await asyncio.sleep(0.015)
        return num + 10

    async def filter_even(num: int) -> AsyncIterator[int]:
        """Étape 3: Filtre les nombres pairs."""
        await asyncio.sleep(0.005)
        if num % 2 == 0:
            yield num

    async def demo_enhanced_pipeline():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        
        print("\n--- Démonstration du Pipeline Amélioré ---")
        pipeline = AsyncPipeline(max_buffer_size=5)
        pipeline.add_stage(double_number)
        pipeline.add_stage(add_ten)
        pipeline.add_stage(filter_even)

        print("Traitement des nombres de 0 à 9...")
        processed_count = 0
        async for result in pipeline.process(generate_numbers(10)):
            print(f"Résultat final : {result}")
            processed_count += 1
        
        print(f"\nTotal des résultats traités : {processed_count}")
        print("Démonstration du pipeline amélioré terminée.")

    asyncio.run(demo_enhanced_pipeline())