# src/orchestrator.py
import logging
from datetime import time
from multiprocessing import context
from pathlib import Path
from typing import Dict, Any

import aiofiles
import tenacity
import yaml
from torch.backends.opt_einsum import strategy

from configs.settings_loader import get_settings
from src.core.strategies.strategy_registry import StrategyRegistry
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.sfd_models import SFDAnalysisRequest
from src.repositories.scenario_repository import ScenarioRepository
from src.monitoring.structured_logger import logger

logger = logging.getLogger(__name__)

# Configuration par défaut utilisée si le fichier services.yaml est absent.
# Cela garantit que l'orchestrateur peut démarrer même avec une configuration minimale.
DEFAULT_SERVICES_YAML = """  
services:
  sfd_analysis:
    enabled: true
    timeout: 120
  cache:
    ttl: 3600
"""


class Orchestrator:
    """Orchestre le pipeline de traitement des SFD et la génération de tests.

    Cette classe est le chef d'orchestre de l'application. Elle initialise les
    différents composants (modèles IA, clients, etc.) et coordonne l'exécution
    des tâches complexes comme l'analyse d'une SFD pour en extraire des scénarios
    de test.
    """
    def __init__(
            self,
            starcoder,
            redis_client,
            config,
            model_registry,
    ) -> None:
        """Initialise l'orchestrateur.

        Args:
            starcoder: Client pour le modèle StarCoder2 (génération de code).
            redis_client: Client pour la connexion à Redis (cache).
            config: Objet de configuration global de l'application.
            model_registry: Registre des modèles d'IA disponibles.
        """
        self.starcoder = starcoder
        self.redis_client = redis_client
        self.config = config
        self.model_registry = model_registry
        self.qwen3: Qwen3OllamaInterface | None = None
        self.scenario_repository = ScenarioRepository(
            storage_path=Path("data/scenarios")
        )
        self.config_path = get_settings().base_dir / "configs" / "services.yaml"
        self._services: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialise l'orchestrateur de manière asynchrone.

        Cette méthode charge la configuration des services depuis `services.yaml`.
        Si le fichier n'existe pas, il est créé avec une configuration par défaut.
        Elle initialise également les interfaces des modèles de langage nécessaires.
        """
        try:
            async with aiofiles.open(self.config_path, "r") as f:
                cfg = yaml.safe_load(await f.read())
        except FileNotFoundError:
            logger.warning(
                f"Configuration absente : {self.config_path}. "
                "Création du fichier par défaut."
            )
            # Crée le dossier de configuration s'il n'existe pas.
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            # Écrit la configuration par défaut dans le fichier.
            async with aiofiles.open(self.config_path, "w") as f:
                await f.write(DEFAULT_SERVICES_YAML)
            cfg = yaml.safe_load(DEFAULT_SERVICES_YAML)
        except yaml.YAMLError as e:
            # Lève une exception si le fichier de configuration est mal formé.
            raise ValueError(
                f"Erreur de parsing YAML dans {self.config_path}: {e}"
            ) from e

        self._services = cfg.get("services", {})
        # Initialisation de l'interface pour le modèle Qwen3.
        self.qwen3 = Qwen3OllamaInterface()
        await self.qwen3.initialize()

    async def close(self) -> None:
        """Ferme proprement les connexions et les sessions des modèles."""
        if self.qwen3:
            await self.qwen3.close()

    # Le décorateur `tenacity.retry` permet de relancer automatiquement la méthode
    # en cas d'échec. Ici, il tentera 3 fois avec une attente de 1 seconde
    # entre chaque tentative. C'est utile pour gérer les erreurs réseau temporaires.
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_fixed(1)
    )
    async def process_sfd_to_tests(self, sfd_request: SFDAnalysisRequest) -> Dict[str, Any]:
        """Traite une demande d'analyse de SFD pour générer des tests.

        Args:
            sfd_request: La requête d'analyse contenant l'ID et le contenu de la SFD.

        Returns:
            Un dictionnaire contenant les résultats de l'analyse, notamment les
            scénarios de test extraits.

        Raises:
            Exception: Lève une exception si le traitement échoue après plusieurs tentatives.
        """
        start = time.perf_counter()
        try:
            # L'exécution de la stratégie est le cœur de la logique métier.
            # La stratégie appropriée (par exemple, analyse de SFD) est sélectionnée
            # et exécutée avec le contexte donné.
            result = await strategy.execute(context)
            logger.info(
                "sfd_processed",
                extra={
                    "sfd_id": sfd_request.id,
                    "duration_ms": int((time.perf_counter() - start) * 1000),
                    "model": "qwen3",
                    "scenarios_extracted": len(result.get("scenarios", [])),
                },
            )
            return result
        except Exception as exc:
            logger.error("sfd_failed", extra={"sfd_id": sfd_request.id, "error": str(exc)})
            raise