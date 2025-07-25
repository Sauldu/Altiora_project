# src/core/model_memory_manager.py
"""Gestionnaire de mémoire pour les modèles d'IA, avec déchargement LRU et fallback de quantification.

Ce module fournit une solution pour gérer le chargement et le déchargement des
modèles de langage (LLMs) en mémoire, en particulier sur des systèmes avec des
ressources limitées (comme un CPU). Il implémente une stratégie LRU (Least Recently Used)
pour décharger les modèles les moins utilisés lorsque la limite de mémoire est atteinte,
et peut basculer vers des versions quantifiées des modèles si la mémoire est insuffisante.
"""

import gc
import time
import logging
from typing import Dict, Any

# Importations conditionnelles pour éviter les erreurs si PyTorch n'est pas installé.
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError:
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None
    logging.warning("PyTorch ou Transformers non installés. Le gestionnaire de mémoire des modèles sera limité.")

logger = logging.getLogger(__name__)


class ModelMemoryManager:
    """Gère le chargement, le déchargement et l'accès aux modèles d'IA en mémoire."""

    def __init__(self, max_memory_gb: float = 16.0):
        """Initialise le gestionnaire de mémoire des modèles.

        Args:
            max_memory_gb: La limite maximale de mémoire (en Go) que les modèles peuvent utiliser.
        """
        self.max_memory_gb = max_memory_gb
        self.loaded_models: Dict[str, Dict[str, Any]] = {}
        logger.info(f"Gestionnaire de mémoire des modèles initialisé avec une limite de {max_memory_gb} Go.")

    def can_load_model(self, model_name: str, size_gb: float) -> bool:
        """Vérifie si un modèle peut être chargé sans dépasser la limite de mémoire.

        Args:
            model_name: Le nom du modèle à charger.
            size_gb: La taille estimée du modèle en Go.

        Returns:
            True si le modèle peut être chargé, False sinon.
        """
        current_usage = sum(model_info['size'] for model_info in self.loaded_models.values())
        available_memory = self.max_memory_gb - current_usage
        logger.debug(f"Mémoire disponible : {available_memory:.2f} Go, Taille du modèle : {size_gb:.2f} Go.")
        return size_gb <= available_memory

    async def load_model_with_fallback(self, model_name: str, estimated_size_gb: float) -> Any:
        """Charge un modèle, avec un fallback vers une version quantifiée si la mémoire est insuffisante.

        Args:
            model_name: Le nom du modèle à charger.
            estimated_size_gb: La taille estimée du modèle en Go (version complète).

        Returns:
            L'instance du modèle chargé (complet ou quantifié).

        Raises:
            RuntimeError: Si PyTorch ou Transformers ne sont pas disponibles.
            Exception: Si le chargement du modèle échoue.
        """
        if torch is None or AutoModelForCausalLM is None or AutoTokenizer is None:
            raise RuntimeError("PyTorch ou Transformers ne sont pas installés. Impossible de charger les modèles.")

        # Tente de charger le modèle complet en premier.
        if self.can_load_model(model_name, estimated_size_gb):
            try:
                model = await self._load_full_model(model_name)
                return model
            except Exception as e:
                logger.warning(f"Échec du chargement du modèle complet {model_name}: {e}. Tentative de chargement quantifié.")

        # Si le modèle complet ne peut pas être chargé (mémoire ou autre erreur), tente le quantifié.
        # D'abord, essaie de libérer de la mémoire si nécessaire.
        if not self.can_load_model(model_name, estimated_size_gb * 0.5): # Estime la taille quantifiée à 50%
            await self._evict_least_used_model()

        # Tente de charger la version quantifiée.
        try:
            model = await self._load_quantized_model(model_name)
            return model
        except Exception as e:
            logger.error(f"Échec du chargement du modèle quantifié {model_name}: {e}.")
            raise RuntimeError(f"Impossible de charger le modèle {model_name} (complet ou quantifié).") from e

    async def _evict_least_used_model(self):
        """Décharge le modèle le moins récemment utilisé pour libérer de la mémoire."""
        if not self.loaded_models:
            return

        # Trouve le modèle le moins récemment utilisé (LRU).
        oldest_model_name = min(self.loaded_models, key=lambda k: self.loaded_models[k]['last_used'])
        logger.info(f"Limite de mémoire atteinte. Déchargement du modèle le moins utilisé : {oldest_model_name}")

        # Supprime le modèle du dictionnaire.
        del self.loaded_models[oldest_model_name]

        # Force le nettoyage de la mémoire.
        gc.collect()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()

    async def _load_full_model(self, model_name: str) -> Any:
        """Charge la version complète (non quantifiée) d'un modèle."""
        logger.info(f"Chargement du modèle complet : {model_name}")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto", # Tente d'utiliser le GPU si disponible, sinon CPU.
            torch_dtype=torch.float16 # Utilise float16 pour réduire l'empreinte mémoire.
        )
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model_size = self._get_model_size(model)
        self.loaded_models[model_name] = {
            'model': model,
            'tokenizer': tokenizer,
            'last_used': time.time(),
            'size': model_size
        }
        logger.info(f"Modèle complet {model_name} chargé avec succès ({model_size:.2f} Go).")
        return model

    async def _load_quantized_model(self, model_name: str) -> Any:
        """Charge la version quantifiée (8-bit) d'un modèle."""
        logger.info(f"Chargement du modèle quantifié (8-bit) : {model_name}")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            load_in_8bit=True,  # Active la quantification 8-bit.
            device_map="auto",
            torch_dtype=torch.float16
        )
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model_size = self._get_model_size(model)
        self.loaded_models[model_name] = {
            'model': model,
            'tokenizer': tokenizer,
            'last_used': time.time(),
            'size': model_size
        }
        logger.info(f"Modèle quantifié {model_name} chargé avec succès ({model_size:.2f} Go).")
        return model

    def _get_model_size(self, model: Any) -> float:
        """Estime la taille en Go d'un modèle PyTorch en mémoire."""
        param_size = 0
        for param in model.parameters():
            param_size += param.nelement() * param.element_size()
        buffer_size = 0
        for buffer in model.buffers():
            buffer_size += buffer.nelement() * buffer.element_size()
        return (param_size + buffer_size) / (1024 ** 3)  # Convertit en Go.

    async def get_model(self, model_name: str) -> Any:
        """Récupère un modèle par son nom, le charge si nécessaire.

        Args:
            model_name: Le nom du modèle à récupérer.

        Returns:
            L'instance du modèle.

        Raises:
            RuntimeError: Si PyTorch ou Transformers ne sont pas disponibles.
            Exception: Si le chargement du modèle échoue.
        """
        if model_name in self.loaded_models:
            # Met à jour le temps de dernière utilisation pour la stratégie LRU.
            self.loaded_models[model_name]['last_used'] = time.time()
            return self.loaded_models[model_name]['model']

        # Tente de charger le modèle complet en premier.
        # Note: La taille estimée doit être passée ici pour la vérification initiale.
        # Pour l'exemple, on utilise une taille arbitraire, mais en production, elle viendrait d'une config.
        estimated_size = 10.0 # Exemple: 10 Go pour un modèle complet.
        return await self.load_model_with_fallback(model_name, estimated_size)


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO)
        manager = ModelMemoryManager(max_memory_gb=2.0) # Petite limite pour forcer le déchargement/quantification.

        # Simule le chargement de modèles.
        # Note: Ces noms de modèles doivent exister et être accessibles par AutoModelForCausalLM.
        # Remplacez par de vrais noms de modèles si vous exécutez ce code.
        model_name_1 = "gpt2" # Petit modèle
        model_name_2 = "distilbert-base-uncased" # Autre petit modèle

        print(f"\n--- Tentative de chargement de {model_name_1} ---")
        try:
            model1 = await manager.get_model(model_name_1)
            print(f"Modèle {model_name_1} chargé.")
        except Exception as e:
            print(f"Échec du chargement de {model_name_1}: {e}")

        print(f"\n--- Tentative de chargement de {model_name_2} ---")
        try:
            model2 = await manager.get_model(model_name_2)
            print(f"Modèle {model_name_2} chargé.")
        except Exception as e:
            print(f"Échec du chargement de {model_name_2}: {e}")

        print(f"\n--- Accès à {model_name_1} (met à jour LRU) ---")
        try:
            model1_again = await manager.get_model(model_name_1)
            print(f"Accès à {model_name_1} réussi.")
        except Exception as e:
            print(f"Échec de l'accès à {model_name_1}: {e}")

        # Simule un modèle plus grand qui pourrait nécessiter un déchargement ou une quantification.
        # Remplacez par un nom de modèle plus grand si vous exécutez ce code.
        model_name_3 = "facebook/opt-125m" # Un autre petit modèle pour l'exemple
        print(f"\n--- Tentative de chargement de {model_name_3} (pourrait déclencher LRU/quantification) ---")
        try:
            model3 = await manager.get_model(model_name_3)
            print(f"Modèle {model_name_3} chargé.")
        except Exception as e:
            print(f"Échec du chargement de {model_name_3}: {e}")

    if torch is None:
        print("PyTorch ou Transformers ne sont pas installés. Impossible d'exécuter la démo du gestionnaire de mémoire.")
    else:
        asyncio.run(demo())