# src/utils/model_loader.py
"""Chargeur de modèles centralisé et asynchrone pour les modèles Ollama utilisés par Altiora.

Ce module fournit une interface pour gérer le cycle de vie des modèles de langage
(LLMs) hébergés par Ollama. Il permet le préchargement des modèles pour réduire
la latence au démarrage, la vérification de leur état de santé, et la gestion
dynamique des adaptateurs LoRA.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, List

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from configs.config_module import get_settings

logger = logging.getLogger(__name__)


class ModelLoader:
    """Chargeur et gestionnaire asynchrone pour les modèles Ollama.

    Permet de précharger des modèles, de vérifier leur disponibilité et de
    basculer entre différents adaptateurs LoRA.

    Exemple d'utilisation:
    ```python
    async with ModelLoader() as loader:
        await loader.preload(["qwen3:32b-q4_K_M", "starcoder2:15b-q8_0"])
        is_qwen_ready = await loader.health_check("qwen3:32b-q4_K_M")
        print(f"Modèle Qwen3 prêt ? {is_qwen_ready}")
    ```
    """

    def __init__(
            self,
            base_url: Optional[str] = None,
            timeout: int = 30,
            retries: int = 3,
    ):
        """Initialise le chargeur de modèles.

        Args:
            base_url: L'URL de base de l'API Ollama. Si non spécifié, utilise la configuration.
            timeout: Le délai d'attente par défaut pour les requêtes HTTP en secondes.
            retries: Le nombre de tentatives pour les opérations de pull de modèle.
        """
        self.base_url = base_url or get_settings().ollama.url
        self.timeout = timeout
        self.retries = retries
        self.session: Optional[aiohttp.ClientSession] = None
        self._loaded_models: Dict[str, bool] = {} # Garde une trace des modèles chargés en mémoire.

    # ------------------------------------------------------------------
    # Cycle de vie (gestionnaire de contexte asynchrone)
    # ------------------------------------------------------------------
    async def __aenter__(self) -> "ModelLoader":
        """Ouvre la session HTTP lors de l'entrée dans le contexte asynchrone."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Ferme la session HTTP lors de la sortie du contexte asynchrone."""
        if self.session:
            await self.session.close()

    # ------------------------------------------------------------------
    # API Publique
    # ------------------------------------------------------------------
    async def preload(self, models: List[str]) -> Dict[str, bool]:
        """Télécharge (si nécessaire) et charge les modèles en mémoire pour éviter la latence de démarrage à froid.

        Args:
            models: Une liste de noms de modèles Ollama à précharger.

        Returns:
            Un dictionnaire indiquant le succès du préchargement pour chaque modèle.
        """
        results = {}
        for model in models:
            try:
                await self._ensure_model(model) # S'assure que le modèle est disponible localement.
                await self._load_model_into_memory(model) # Force le chargement en RAM.
                results[model] = True
                logger.info("✅ Modèle %s préchargé avec succès.", model)
            except Exception as e:
                logger.error("❌ Échec du préchargement du modèle %s: %s", model, e)
                results[model] = False
        return results

    async def health_check(self, model: str) -> bool:
        """Vérifie l'état de santé d'un modèle Ollama en envoyant une petite requête."

        Args:
            model: Le nom du modèle à vérifier.

        Returns:
            True si le modèle répond, False sinon.
        """
        return await self._call_generate(model, "OK", max_tokens=1)

    async def switch_lora(self, model: str, adapter_path: Optional[Path]) -> bool:
        """Change dynamiquement l'adaptateur LoRA pour un modèle donné.

        Args:
            model: Le nom du modèle Ollama.
            adapter_path: Le chemin vers le fichier de l'adaptateur LoRA. Si None, détache l'adaptateur.

        Returns:
            True si l'opération a réussi, False sinon.
        """
        payload = {
            "model": model,
            "prompt": " ", # Un prompt vide ou minimal.
            "stream": False,
            "options": {"num_predict": 1},
        }
        if adapter_path and adapter_path.exists():
            payload["adapter"] = str(adapter_path) # Ajoute le chemin de l'adaptateur au payload.

        return await self._call_generate(model, payload=payload)

    # ------------------------------------------------------------------
    # Fonctions internes
    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _ensure_model(self, model: str):
        """S'assure que le modèle est disponible localement (le télécharge si nécessaire)."""
        tags = await self._list_local_models()
        if any(model in tag for tag in tags):
            logger.info("Modèle %s déjà disponible localement.", model)
            return  # Le modèle existe déjà localement.
        
        logger.info("⬇️  Téléchargement du modèle %s...", model)
        async with self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model},
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Impossible de télécharger le modèle {model}: {resp.status} - {await resp.text()}")
            # Lire la réponse pour s'assurer que le téléchargement est complet.
            async for chunk in resp.content.iter_any():
                pass # Consomme le flux de données.
            logger.info("Modèle %s téléchargé avec succès.", model)

    async def _load_model_into_memory(self, model: str):
        """Force le chargement d'un modèle dans la RAM d'Ollama en effectuant une petite génération."""
        logger.info("Chargement du modèle %s en mémoire...", model)
        await self._call_generate(model, "OK", max_tokens=1)
        self._loaded_models[model] = True
        logger.info("Modèle %s chargé en mémoire.", model)

    async def _call_generate(
            self, model: str, prompt: str = "", payload: Optional[Dict] = None, max_tokens: int = 1
    ) -> bool:
        """Appel de bas niveau à l'API /api/generate d'Ollama, retournant True en cas de succès."""
        if not self.session:
            raise RuntimeError("ModelLoader n'est pas entré dans un contexte asynchrone (utilisez `async with`).")

        # Construit le payload par défaut si non fourni.
        payload = payload or {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        try:
            async with self.session.post(
                    f"{self.base_url}/api/generate", json=payload
            ) as resp:
                if resp.status == 200:
                    # Lit la réponse pour s'assurer que la requête est complète.
                    await resp.json()
                    return True
                else:
                    logger.warning("Appel à /api/generate pour %s a échoué avec le statut %d: %s", model, resp.status, await resp.text())
                    return False
        except aiohttp.ClientError as e:
            logger.warning("La sonde de santé a échoué pour le modèle %s: %s", model, e)
            return False

    async def _list_local_models(self) -> List[str]:
        """Retourne la liste des tags des modèles disponibles localement dans Ollama."""
        if not self.session:
            raise RuntimeError("Session HTTP non initialisée.")
        async with self.session.get(f"{self.base_url}/api/tags") as resp:
            resp.raise_for_status()
            data = await resp.json()
            return [m["name"] for m in data.get("models", [])]

    # ------------------------------------------------------------------
    # Singleton de commodité
    # ------------------------------------------------------------------
    _instance: Optional["ModelLoader"] = None

    @classmethod
    def get(cls) -> "ModelLoader":
        """Retourne l'instance singleton du ModelLoader."

        Returns:
            L'instance unique de `ModelLoader`.
        """
        if cls._instance is None:
            cls._instance = ModelLoader()
        return cls._instance


# ------------------------------------------------------------------
# Exemple d'utilisation
# ------------------------------------------------------------------
async def example():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Assurez-vous qu'Ollama est en cours d'exécution et accessible.
    # Vous pouvez lancer `ollama serve` dans votre terminal.

    async with ModelLoader() as loader:
        print("\n--- Préchargement des modèles ---")
        # Remplacez par des noms de modèles que vous avez ou que vous voulez télécharger.
        models_to_preload = ["llama2", "mistral"]
        preload_results = await loader.preload(models_to_preload)
        print(f"Résultats du préchargement : {preload_results}")

        print("\n--- Vérification de l'état de santé d'un modèle ---")
        model_to_check = "llama2"
        if model_to_check in preload_results and preload_results[model_to_check]:
            is_ready = await loader.health_check(model_to_check)
            print(f"Modèle '{model_to_check}' prêt ? {is_ready}")
        else:
            print(f"Modèle '{model_to_check}' non préchargé ou échec.")

        print("\n--- Tentative de basculer un adaptateur LoRA (exemple) ---")
        # Ceci est un exemple conceptuel. Le chemin de l'adaptateur doit être valide.
        mock_adapter_path = Path("./models/lora_adapters/my_custom_adapter")
        if not mock_adapter_path.exists():
            mock_adapter_path.mkdir(parents=True, exist_ok=True)
            # Crée un fichier bidon pour simuler l'existence de l'adaptateur.
            (mock_adapter_path / "adapter_config.json").write_text("{}")

        model_with_adapter = "llama2"
        if model_with_adapter in preload_results and preload_results[model_with_adapter]:
            print(f"Tentative de basculer l'adaptateur pour '{model_with_adapter}'...")
            switched = await loader.switch_lora(model_with_adapter, mock_adapter_path)
            print(f"Adaptateur basculé ? {switched}")

            print(f"Tentative de détacher l'adaptateur pour '{model_with_adapter}'...")
            detached = await loader.switch_lora(model_with_adapter, None)
            print(f"Adaptateur détaché ? {detached}")
        else:
            print(f"Modèle '{model_with_adapter}' non disponible pour le test d'adaptateur.")

    asyncio.run(example())