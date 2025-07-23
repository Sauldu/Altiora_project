from src.config.settings import get_settings   # en haut du fichier

class Orchestrator:
    def __init__(
        self,
        starcoder,
        redis_client,
        config,
        model_registry,
    ) -> None:
        ...
        self.config_path = get_settings().base_dir / "configs" / "services.yaml"