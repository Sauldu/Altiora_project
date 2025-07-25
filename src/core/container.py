# src/core/container.py
"""Conteneur de dépendances pour l'application Altiora.

Ce module utilise la bibliothèque `dependency_injector` pour gérer les
dépendances de l'application. Il centralise la création et la configuration
des objets (services, gestionnaires, modèles) et permet leur injection
facile dans d'autres parties du code, favorisant ainsi le découplage
et la testabilité.
"""

import redis.asyncio as redis
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide

from src.core.model_memory_manager import ModelMemoryManager
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.starcoder2.starcoder2_interface import StarCoder2OllamaInterface
from configs.config_module import get_settings
from src.orchestrator import Orchestrator


class Container(containers.DeclarativeContainer):
    """Conteneur de dépendances pour l'application Altiora."

    Définit et configure les services et composants de l'application
    qui seront injectés là où ils sont nécessaires.
    """

    # Configuration de l'application, chargée comme un singleton.
    # `get_settings` est une fonction qui retourne l'instance unique des paramètres.
    config = providers.Singleton(get_settings)

    # Gestionnaire de mémoire des modèles, configuré avec la limite de mémoire du système.
    model_memory_manager = providers.Singleton(
        ModelMemoryManager,
        max_memory_gb=config.provided.model_memory_limit_gb
    )

    # Client Redis asynchrone, configuré avec l'URL de Redis des paramètres.
    redis_client = providers.Singleton(
        redis.from_url,
        url=config.provided.redis.url,
        password=config.provided.redis.password, # Ajout du mot de passe Redis.
        decode_responses=True # Décode automatiquement les réponses en UTF-8.
    )

    # Service Qwen3, créé comme une fabrique (nouvelle instance à chaque injection).
    # Il est configuré avec les paramètres spécifiques à Qwen3 et le gestionnaire de mémoire.
    qwen3_service = providers.Factory(
        Qwen3OllamaInterface,
        # Assurez-vous que `config.provided.models["qwen3"]` est un objet ModelConfig.
        config=config.provided.models["qwen3"],
        model_memory_manager=model_memory_manager
    )

    # Service StarCoder2, créé comme une fabrique.
    # Il est configuré avec les paramètres spécifiques à StarCoder2 et le gestionnaire de mémoire.
    starcoder_service = providers.Factory(
        StarCoder2OllamaInterface,
        # Assurez-vous que `config.provided.models["starcoder2"]` est un objet ModelConfig.
        config=config.provided.models["starcoder2"],
        model_memory_manager=model_memory_manager
    )

    # Orchestrateur principal, créé comme un singleton.
    # Il reçoit les services StarCoder et Redis, ainsi que la configuration globale.
    orchestrator = providers.Singleton(
        Orchestrator,
        starcoder=starcoder_service,
        redis_client=redis_client,
        config=config,
        model_registry=None  # Le registre des modèles peut être injecté ici si nécessaire.
    )


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Crée une instance du conteneur.
    container = Container()

    # Pour la démonstration, nous devons simuler une configuration minimale.
    # En temps normal, la configuration serait chargée via `config.from_yaml` ou des variables d'environnement.
    # Ici, nous allons mocker `get_settings` pour fournir une configuration factice.
    class MockOllamaModelConfig(BaseModel):
        name: str = "mock-model"
        temperature: float = 0.7
        top_p: float = 0.9
        top_k: int = 40
        repeat_penalty: float = 1.1
        max_tokens: int = 512
        num_ctx: int = 4096
        seed: Optional[int] = None
        stop: List[str] = Field(default_factory=list)
        api_mode: str = "generate"

    class MockRedisConfig(BaseModel):
        url: str = "redis://localhost:6379"
        password: Optional[str] = None
        max_connections: int = 10

    class MockSettings(BaseModel):
        model_memory_limit_gb: float = 8.0
        ollama: Any = MockOllamaModelConfig()
        redis: Any = MockRedisConfig()
        models: Dict[str, Any] = {
            "qwen3": MockOllamaModelConfig(name="qwen3-sfd-analyzer"),
            "starcoder2": MockOllamaModelConfig(name="starcoder2-playwright")
        }

    # Patch la fonction get_settings pour qu'elle retourne notre configuration factice.
    with patch('configs.config_module.get_settings', return_value=MockSettings()):
        # Réinitialise le conteneur pour qu'il utilise la nouvelle configuration.
        container = Container()
        container.wire(modules=[__name__]) # Re-câble les dépendances.

        print("\n--- Récupération des dépendances via le conteneur ---")
        # Récupère l'orchestrateur (qui est un singleton).
        orchestrator_instance = container.orchestrator()
        print(f"Instance Orchestrator : {orchestrator_instance}")

        # Récupère le service Qwen3 (qui est une nouvelle instance à chaque injection).
        qwen3_service_instance_1 = container.qwen3_service()
        print(f"Instance Qwen3 Service 1 : {qwen3_service_instance_1}")

        qwen3_service_instance_2 = container.qwen3_service()
        print(f"Instance Qwen3 Service 2 : {qwen3_service_instance_2}")

        assert orchestrator_instance is container.orchestrator(), "L'orchestrateur devrait être un singleton."
        assert qwen3_service_instance_1 is not qwen3_service_instance_2, "Le service Qwen3 devrait être une nouvelle instance à chaque fois."

        print("Démonstration du conteneur de dépendances terminée.")

        # Nettoyage des ressources (fermeture des clients Redis, etc.).
        # En production, cela serait géré par le lifespan de l'application FastAPI.
        # await container.redis_client().close()
        # await qwen3_service_instance_1.close()
        # await starcoder_service_instance_1.close()
