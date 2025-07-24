from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict
import yaml
from pathlib import Path

class OllamaSettings(BaseModel):
    """Configuration Ollama"""
    host: str = "http://localhost:11434"
    timeout: int = 300
    max_retries: int = 3
    models: Dict[str, str] = {
        "qwen3": "qwen3-sfd-analyzer:latest",
        "starcoder2": "starcoder2-playwright:latest"
    }

class RedisSettings(BaseModel):
    """Configuration Redis"""
    url: str = "redis://localhost:6379"
    ttl: int = 3600
    max_connections: int = 50
    password: Optional[str] = None # Ajouté pour la gestion des secrets

class SecuritySettings(BaseModel):
    """Configuration de sécurité"""
    enable_auth: bool = False
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440
    allowed_origins: list[str] = ["*"]
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

class Settings(BaseSettings):
    """Configuration globale"""
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", case_sensitive=False)

    app_name: str = "Altiora"
    debug: bool = False
    environment: str = "development"

    # Chemins
    base_dir: Path = Path(__file__).parent.parent.parent
    data_dir: Path = Field(default=Path(__file__).parent.parent.parent / "data")
    models_dir: Path = Field(default=Path(__file__).parent.parent.parent / "models")
    logs_dir: Path = Field(default=Path(__file__).parent.parent.parent / "logs")
    reports_dir: Path = Field(default=Path(__file__).parent.parent.parent / "reports")
    temp_dir: Path = Field(default=Path(__file__).parent.parent.parent / "temp")

    # Services
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    # Performance
    max_workers: int = 10
    batch_size: int = 50
    model_memory_limit_gb: float = 8.0

    @classmethod
    def from_yaml(cls, path: Path):
        """Charger la configuration depuis un fichier YAML."""
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            return cls(**data)
        except (IOError, OSError, yaml.YAMLError) as e:
            print(f"Error loading configuration from {path}: {e}")
            raise

# Singleton pour les paramètres
_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        # Tente de charger depuis config.yaml, sinon utilise les valeurs par défaut
        config_path = Path(__file__).parent.parent.parent / "configs" / "config.yaml"
        if config_path.exists():
            _settings_instance = Settings.from_yaml(config_path)
        else:
            _settings_instance = Settings()
    return _settings_instance
