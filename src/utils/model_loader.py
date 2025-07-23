"""
Model Loader – Centralized, async-first loader for Ollama models used by Altiora
- Warm-up and pre-loading
- Health & readiness probes
- Optional LoRA adapter switching
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
    """
    Async loader / manager for Ollama models.
    Usage:
        loader = ModelLoader()
        await loader.preload(["qwen3:32b-q4_K_M", "starcoder2:15b-q8_0"])
    """

    def __init__(
            self,
            base_url: Optional[str] = None,
            timeout: int = 30,
            retries: int = 3,
    ):
        self.base_url = base_url or get_settings().ollama.url
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self._loaded_models: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def preload(self, models: List[str]) -> Dict[str, bool]:
        """
        Pull (if needed) and load models into memory to avoid cold-start latency.
        Returns dict {model_name: success}
        """
        results = {}
        for model in models:
            try:
                await self._ensure_model(model)
                await self._load_model_into_memory(model)
                results[model] = True
                logger.info("✅ Model %s pre-loaded", model)
            except Exception as e:
                logger.error("❌ Failed to preload %s: %s", model, e)
                results[model] = False
        return results

    async def health_check(self, model: str) -> bool:
        """Ping Ollama to verify model is ready."""
        return await self._call_generate(model, "OK", max_tokens=1)

    async def switch_lora(self, model: str, adapter_path: Optional[Path]) -> bool:
        """
        Dynamically switch / detach LoRA adapter.
        If adapter_path is None => detach.
        """
        payload = {
            "model": model,
            "prompt": " ",
            "stream": False,
            "options": {"num_predict": 1},
        }
        if adapter_path and adapter_path.exists():
            payload["adapter"] = str(adapter_path)

        return await self._call_generate(model, payload=payload)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _ensure_model(self, model: str):
        """Pull model if not already local."""
        tags = await self._list_local_models()
        if any(model in tag for tag in tags):
            return  # already exists
        logger.info("⬇️  Pulling model %s ...", model)
        async with self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model},
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Cannot pull {model}: {resp.status}")

    async def _load_model_into_memory(self, model: str):
        """Force load into RAM by tiny generation."""
        await self._call_generate(model, "OK", max_tokens=1)

    async def _call_generate(
            self, model: str, prompt: str = "", payload: Optional[Dict] = None, max_tokens: int = 1
    ) -> bool:
        """Low-level call helper returning True on success."""
        if not self.session:
            raise RuntimeError("ModelLoader not entered (use async with).")

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
                return resp.status == 200
        except aiohttp.ClientError as e:
            logger.warning("Health probe failed for %s: %s", model, e)
            return False

    async def _list_local_models(self) -> List[str]:
        """Return list of locally available model tags."""
        async with self.session.get(f"{self.base_url}/api/tags") as resp:
            data = await resp.json()
            return [m["name"] for m in data.get("models", [])]

    # ------------------------------------------------------------------
    # Convenience singleton
    # ------------------------------------------------------------------
    _instance: Optional["ModelLoader"] = None

    @classmethod
    def get(cls) -> "ModelLoader":
        if cls._instance is None:
            cls._instance = ModelLoader()
        return cls._instance


# ------------------------------------------------------------------
# Example usage
# ------------------------------------------------------------------
async def example():
    async with ModelLoader() as loader:
        await loader.preload(["qwen3:32b-q4_K_M", "starcoder2:15b-q8_0"])
        ok = await loader.health_check("qwen3:32b-q4_K_M")
        print("Model ready?", ok)


if __name__ == "__main__":
    asyncio.run(example())
