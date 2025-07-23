# src/orchestrator.py
"""
Orchestrateur interne – ultra-léger, ultra-résilient
"""

import logging
from pathlib import Path
from typing import Dict, Any

import aiofiles
import tenacity
import yaml
from src.config.settings import get_settings

from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.sfd_models import SFDAnalysisRequest
from src.models.test_scenario import TestScenario
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
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration absente : {self.config_path}"
            )
        async with aiofiles.open(self.config_path, "r") as f:
            cfg = yaml.safe_load(await f.read())
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
    ) -> Dict[str, Any]:
        try:
            analysis_result = await self.qwen3.analyze_sfd(sfd_request)
            scenarios = analysis_result.get("scenarios", [])
            if not scenarios:
                logger.warning("Aucun scénario extrait.")
                return {"status": "no_scenarios", "saved_scenarios": []}

            saved = []
            for idx, data in enumerate(scenarios, 1):
                data.setdefault(
                    "id", f"scenario_{idx}_{hash(sfd_request.content) % 10000}"
                )
                try:
                    scenario = TestScenario(**data)
                    await self.scenario_repository.create(scenario)
                    saved.append(scenario.model_dump())
                except Exception as e:
                    logger.error(
                        f"Erreur sauvegarde scénario {data.get('id')}: {e}"
                    )

            return {
                "status": "completed",
                "content": sfd_request.content,
                "metrics": {
                    "scenarios_found": len(scenarios),
                    "tests_generated": len(saved),
                    "file_size": len(
                        sfd_request.content.encode("utf-8")
                    ),
                },
                "analysis_result": analysis_result,
                "saved_scenarios": saved,
            }

        except Exception as e:
            logger.exception("Échec lors du traitement du SFD.")
            raise
