# src/orchestrator.py
import logging
from pathlib import Path
from typing import Dict, Any

import aiofiles
import tenacity
import yaml

from configs.settings import get_settings
from src.core.strategies.strategy_registry import StrategyRegistry
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.sfd_models import SFDAnalysisRequest
from src.repositories.scenario_repository import ScenarioRepository

logger = logging.getLogger(__name__)


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
        try:
            async with aiofiles.open(self.config_path, "r") as f:
                cfg = yaml.safe_load(await f.read())
        except yaml.YAMLError as e:
            raise ValueError(f"Erreur de parsing YAML dans {self.config_path}: {e}") from e
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Configuration absente : {self.config_path}"
            )
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
    async def process_sfd_to_tests(
            self, sfd_request: SFDAnalysisRequest
    ) -> Dict[str, Any] | None:
        """Process SFD with proper error handling"""
        try:
            if len(sfd_request.content) > 1_000_000:  # 1MB limit
                raise ValueError("SFD content too large")

            context = {"sfd_request": sfd_request}

            strategy_cls = StrategyRegistry.get("sfd_analysis")
            if not strategy_cls:
                raise ValueError("Stratégie 'sfd_analysis' non enregistrée")

            strategy = strategy_cls(self.qwen3)
            result = await strategy.execute(context)
            return result

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing SFD: {e}")
            return None
