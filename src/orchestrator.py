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

# Configuration par défaut si le fichier n’existe pas
DEFAULT_SERVICES_YAML = """
services:
  sfd_analysis:
    enabled: true
    timeout: 120
  cache:
    ttl: 3600
"""


class Orchestrator:
    def __init__(
            self,
            starcoder,
            redis_client,
            config,
            model_registry,
    ) -> None:
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
        """
        Initialise l’orchestrateur :
        - charge ou crée le fichier services.yaml
        - initialise les dépendances
        """
        try:
            async with aiofiles.open(self.config_path, "r") as f:
                cfg = yaml.safe_load(await f.read())
        except FileNotFoundError:
            logger.warning(
                f"Configuration absente : {self.config_path}. "
                "Création du fichier par défaut."
            )
            # Créer le dossier configs s’il n’existe pas
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            # Écriture de la configuration par défaut
            async with aiofiles.open(self.config_path, "w") as f:
                await f.write(DEFAULT_SERVICES_YAML)
            cfg = yaml.safe_load(DEFAULT_SERVICES_YAML)
        except yaml.YAMLError as e:
            raise ValueError(
                f"Erreur de parsing YAML dans {self.config_path}: {e}"
            ) from e

        self._services = cfg.get("services", {})
        self.qwen3 = Qwen3OllamaInterface()
        await self.qwen3.initialize()

    async def close(self) -> None:
        if self.qwen3:
            await self.qwen3.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_fixed(1)
    )
    async def process_sfd_to_tests(self, sfd_request: SFDAnalysisRequest) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
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
