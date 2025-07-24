# src/core/container.py
import redis.asyncio as redis
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide

from src.core.model_memory_manager import ModelMemoryManager
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface  # uniquement Qwen3 ici
from src.models.starcoder2.starcoder2_interface import StarCoder2OllamaInterface
from configs.settings import get_settings
from src.orchestrator import Orchestrator

class Container(containers.DeclarativeContainer):
    config = providers.Singleton(get_settings)
    model_memory_manager = providers.Singleton(ModelMemoryManager, max_memory_gb=config.provided.model_memory_limit_gb)

    # Services
    redis_client = providers.Singleton(redis.from_url, url=config.provided.redis.url)

    qwen3_service = providers.Factory(
        Qwen3OllamaInterface,
        config=config.provided.ollama.models["qwen3"],
        model_memory_manager=model_memory_manager
    )

    starcoder_service = providers.Factory(
        StarCoder2OllamaInterface,
        config=config.provided.ollama.models["starcoder2"],
        model_memory_manager=model_memory_manager
    )

    orchestrator = providers.Singleton(
        Orchestrator,
        starcoder=starcoder_service,
        redis_client=redis_client,
        config=config,
        model_registry=None  # ou injecter plus tard
    )