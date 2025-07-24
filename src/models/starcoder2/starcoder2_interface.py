#!/usr/bin/env python3
"""
StarCoder2-15b-q8_0 via Ollama – Playwright test generator
✅ PyCharm-clean, async-first, circuit-breaker safe
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import aiohttp
import torch
from transformers import BitsAndBytesConfig, AutoModelForCausalLM

from configs.config_module import ModelConfig
from src.core.model_memory_manager import ModelMemoryManager
from src.utils.retry_handler import CircuitBreaker

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Enums & DTO
# ------------------------------------------------------------------
class TestType(Enum):
    E2E = "e2e"
    API = "api"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    COMPONENT = "component"


@dataclass
class PlaywrightTestConfig:
    use_page_object: bool = True
    use_fixtures: bool = True
    include_screenshots: bool = True
    include_videos: bool = False
    browser: str = "chromium"
    timeout: int = 30000
    retry_count: int = 2
    use_data_testid: bool = True
    include_accessibility: bool = True
    include_performance_metrics: bool = False


# ------------------------------------------------------------------
# Interface
# ------------------------------------------------------------------
class StarCoder2OllamaInterface:
    """Async wrapper for StarCoder2-15b-q8_0 via Ollama."""

    def __init__(
            self,
            *,
            config: ModelConfig,
            model_memory_manager: ModelMemoryManager,
            failure_threshold: int = 5,
            recovery_timeout: int = 60,
    ) -> None:
        self.config = config
        self.model_memory_manager = model_memory_manager
        self.model_name = config.name
        self.ollama_host = "http://localhost:11434"  # Assuming Ollama runs locally for now
        self.timeout = config.timeout
        self.use_chat_api = config.api_mode == "chat"
        self.session: Optional[aiohttp.ClientSession] = None
        self.circuit_breaker = CircuitBreaker(failure_threshold, recovery_timeout)

        self.default_params = {
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "repeat_penalty": self.config.repeat_penalty,
            "num_predict": self.config.max_tokens,
            "num_ctx": self.config.num_ctx,
            "seed": self.config.seed,
            "stop": self.config.stop,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            quantization_config=bnb_config,
            device_map="auto",
            torch_dtype=torch.float16
        )
        self.tokenizer = self.model_memory_manager.loaded_models[self.model_name]['tokenizer']
        logger.info("StarCoder2 interface ready with local model.")

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def generate_playwright_test(
            self,
            scenario: Dict[str, Any],
            config: Optional[PlaywrightTestConfig] = None,
            test_type: TestType = TestType.E2E,
    ) -> Dict[str, Any]:
        config = config or PlaywrightTestConfig()

        prompt = self._build_prompt(scenario, config, test_type)
        start_time = asyncio.get_event_loop().time()

        async def _do() -> Dict[str, Any]:
            try:
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    top_k=self.config.top_k,
                    repetition_penalty=self.config.repeat_penalty,
                    do_sample=True if self.config.temperature > 0 else False,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
                raw = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                code = self._extract_code(raw)
                code = self._validate_code(code)

                result = {
                    "code": code,
                    "test_type": test_type.value,
                    "uses_page_object": config.use_page_object,
                    "metadata": {
                        "generation_time": asyncio.get_event_loop().time() - start_time,
                        "model": self.model_name,
                        "scenario_title": scenario.get("titre", "Unknown"),
                        "timestamp": datetime.now().isoformat(),
                        "api_mode": "local_inference",
                    },
                }
                return result
            except Exception as e:
                logger.error(f"Erreur lors de la génération du test Playwright: {e}")
                raise

        return await self.circuit_breaker.call(_do)

    # ------------------------------------------------------------------
    # Code extraction & validation
    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt(
            scenario: Dict[str, Any], config: PlaywrightTestConfig, test_type: TestType
    ) -> str:
        title = scenario.get("titre", "Test").replace(" ", "_").lower()
        objective = scenario.get("objectif", "Verify functionality")
        steps = scenario.get("etapes", [])
        formatted_steps = "\n".join([f"    {i + 1}. {s}" for i, s in enumerate(steps)])

        return f"""
Generate a complete Playwright test in Python.

Scenario: {title}
Objective: {objective}
Steps:
{formatted_steps}
Browser: {config.browser}
Use Page Objects: {config.use_page_object}
```python
# Your code here
"""

    @staticmethod
    def _extract_code(raw: str) -> str:
        # Logique pour extraire le code généré
        start_marker = "```python"
        end_marker = "```"
        start = raw.find(start_marker) + len(start_marker)
        end = raw.find(end_marker, start)
        return raw[start:end].strip()

    @staticmethod
    def _validate_code(code: str) -> str:
        # Logique pour valider le code généré
        # Par exemple, utiliser un linter ou un formatter
        return code
