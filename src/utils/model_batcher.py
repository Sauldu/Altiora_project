# src/utils/model_batcher.py
"""Module pour le traitement par lots (batching) des requêtes de modèles d'IA.

Ce module permet de regrouper plusieurs requêtes individuelles destinées à un
modèle d'IA en un seul appel par lots. Cela peut améliorer significativement
la performance et l'efficacité des modèles, en particulier pour les LLM,
en réduisant la surcharge par requête et en optimisant l'utilisation du matériel.
"""

import asyncio
from collections import defaultdict
from typing import List, Dict, Any, Callable, Optional, TypeVar

T = TypeVar('T') # Type de l'entrée individuelle.
R = TypeVar('R') # Type de la sortie individuelle.


class ModelBatcher:
    """Regroupe les requêtes individuelles en lots pour une exécution plus efficace par un modèle."""

    def __init__(self, model_fn: Callable[[List[T]], asyncio.Awaitable[List[R]]], batch_size: int = 32, timeout: float = 0.1):
        """Initialise le processeur de lots.

        Args:
            model_fn: La fonction asynchrone du modèle qui prend une liste d'entrées
                      et retourne une liste de sorties.
            batch_size: La taille maximale du lot. Une fois ce nombre de requêtes atteint,
                        le lot est traité immédiatement.
            timeout: Le délai maximal en secondes avant de traiter un lot, même s'il n'est
                     pas plein. Permet de ne pas attendre indéfiniment les requêtes.
        """
        self.model_fn = model_fn
        self.batch_size = batch_size
        self.timeout = timeout
        self._pending: List[Dict[str, Any]] = [] # Liste des requêtes en attente.
        self._results: Dict[str, asyncio.Future] = {} # Futures pour stocker les résultats de chaque requête.
        self._lock = asyncio.Lock() # Verrou pour protéger l'accès aux listes partagées.
        self._timer: Optional[asyncio.Task] = None # Tâche pour le timer de traitement de lot.

    async def add_request(self, request_id: str, data: T) -> R:
        """Ajoute une requête individuelle au lot en attente.

        Args:
            request_id: Un identifiant unique pour cette requête.
            data: Les données d'entrée pour le modèle.

        Returns:
            Le résultat du traitement du modèle pour cette requête.
        """
        future = asyncio.Future() # Crée un Future pour retourner le résultat de cette requête.

        async with self._lock:
            self._pending.append({"id": request_id, "data": data})
            self._results[request_id] = future

            # Déclenche le traitement du lot si la taille maximale est atteinte.
            if len(self._pending) >= self.batch_size:
                if self._timer: # Annule le timer s'il est actif.
                    self._timer.cancel()
                    self._timer = None
                asyncio.create_task(self._process_batch())
            # Sinon, démarre un timer pour traiter le lot après un délai.
            elif self._timer is None or self._timer.done():
                self._timer = asyncio.create_task(self._timeout_batch())

        return await future

    async def _process_batch(self):
        """Traite le lot de requêtes en attente."""
        async with self._lock:
            if not self._pending:
                return

            # Récupère les requêtes du lot actuel et vide la liste d'attente.
            batch = self._pending[:]
            self._pending.clear()

            # Annule le timer s'il est actif.
            if self._timer:
                self._timer.cancel()
                self._timer = None

        # Exécute la fonction du modèle avec le lot de données.
        try:
            results = await self.model_fn([item["data"] for item in batch])

            # Distribue les résultats à chaque Future correspondant.
            for item, result in zip(batch, results):
                if not self._results[item["id"]].done():
                    self._results[item["id"]].set_result(result)
        except Exception as e:
            # Propagage l'erreur à toutes les requêtes du lot.
            for item in batch:
                if not self._results[item["id"]].done():
                    self._results[item["id"]].set_exception(e)
        finally:
            # Nettoie les Futures du dictionnaire.
            async with self._lock:
                for item in batch:
                    self._results.pop(item["id"], None)

    async def _timeout_batch(self):
        """Tâche asynchrone qui déclenche le traitement du lot après un timeout."""
        try:
            await asyncio.sleep(self.timeout)
            async with self._lock:
                if self._pending: # Vérifie qu'il y a encore des requêtes en attente.
                    asyncio.create_task(self._process_batch())
        except asyncio.CancelledError:
            pass # Le timer a été annulé car un nouveau lot a été déclenché.


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    import uuid

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def mock_model_inference(inputs: List[str]) -> List[str]:
        """Fonction de modèle factice qui simule une inférence par lots."""
        logging.info(f"[MockModel] Traitement d'un lot de {len(inputs)} requêtes.")
        await asyncio.sleep(0.5) # Simule le temps d'inférence.
        return [f"Processed: {x}" for x in inputs]

    async def demo_batcher():
        print("\n--- Démonstration du ModelBatcher ---")
        batcher = ModelBatcher(mock_model_inference, batch_size=3, timeout=0.2)

        tasks = []
        for i in range(10):
            request_id = str(uuid.uuid4())
            tasks.append(batcher.add_request(request_id, f"item_{i}"))
            await asyncio.sleep(0.05) # Simule l'arrivée des requêtes.

        print("Attente des résultats...")
        results = await asyncio.gather(*tasks)
        for i, res in enumerate(results):
            print(f"Résultat pour item_{i} : {res}")

        print("Démonstration terminée.")

    asyncio.run(demo_batcher())