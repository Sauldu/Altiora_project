"""
Module de configuration centralisé pour le projet Altiora
Gestion unifiée de toutes les configurations avec validation Pydantic v2
"""

import secrets  # ➕ manquant
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from security.secret_manager import SecretManager

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "configs"


# ---------- Enum helpers ----------
class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ServiceType(str, Enum):
    OLLAMA = "ollama"
    OCR = "ocr"
    ALM = "alm"
    EXCEL = "excel"
    PLAYWRIGHT = "playwright"
    REDIS = "redis"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ---------- Pydantic sub-models ----------
class AuthConfig(BaseModel):  # ➕ définition manquante
    jwt_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    database_url: str = Field(default="sqlite:///./auth.db")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8005)


class OllamaConfig(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=11434)
    timeout: int = Field(default=180)
    keep_alive: str = Field(default="30m")

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class ModelConfig(BaseModel):
    name: str
    base_model: str
    role: str
    api_mode: str = "generate"
    timeout: int = 120
    max_tokens: int = 4096
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=1)
    repeat_penalty: float = Field(default=1.1, ge=0.0)
    num_ctx: int = 8192
    seed: Optional[int] = None
    stop: List[str] = Field(default_factory=list)


class ServiceConfig(BaseModel):
    name: str
    type: ServiceType
    host: str = "localhost"
    port: int
    timeout: int = 60
    health_check_path: str = "/health"
    max_retries: int = 3
    enabled: bool = True

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    encrypt_values: bool = True
    ttl_sfd_analysis: int = 86400
    ttl_generated_tests: int = 43200
    ttl_ocr_results: int = 604800
    ttl_model_responses: int = 3600

    @property
    def url(self) -> str:
        scheme = "rediss" if self.ssl else "redis"
        auth = f":{self.password}@" if self.password else ""
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"


class PipelineConfig(BaseModel):
    max_parallel_tests: int = 5
    max_parallel_scenarios: int = 10
    timeout_sfd_extraction: int = 300
    timeout_scenario_analysis: int = 600
    timeout_test_generation: int = 180
    timeout_test_execution: int = 900
    retry_max_attempts: int = 3
    retry_backoff_factor: float = 2.0
    retry_max_delay: int = 30
    fallback_enabled: bool = True
    fallback_use_templates: bool = True
    fallback_template_quality: str = "basic"


class LoggingConfig(BaseModel):
    level: LogLevel = LogLevel.INFO
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[Path] = None
    max_size_mb: int = 100
    backup_count: int = 5

    @field_validator("file", mode="before")
    @classmethod
    def validate_file_path(cls, v):
        return Path(v) if v and not isinstance(v, Path) else v


class SecurityConfig(BaseModel):
    enable_auth: bool = False
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v, info):
        if info.data.get("enable_auth") and not v:
            raise ValueError("jwt_secret_key required when auth is enabled")
        return v


# ---------- Main Settings ----------
class Settings(BaseSettings):
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")

    base_dir: Path = Field(default=BASE_DIR)
    data_dir: Path = Field(default=BASE_DIR / "data")
    models_dir: Path = Field(default=BASE_DIR / "models")
    logs_dir: Path = Field(default=BASE_DIR / "logs")
    reports_dir: Path = Field(default=BASE_DIR / "reports")
    temp_dir: Path = Field(default=BASE_DIR / "temp")
    model_memory_limit_gb: float = Field(default=8.0, env="MODEL_MEMORY_LIMIT_GB")

    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)  # ➕ intégré
    models: Dict[str, ModelConfig] = Field(default_factory=dict)
    services: Dict[ServiceType, ServiceConfig] = Field(default_factory=dict)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    secrets: SecretManager = Field(default_factory=lambda: SecretManager(BASE_DIR / "secrets"))

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    def _create_directories(self):
        for attr in ("data_dir", "models_dir", "logs_dir", "reports_dir", "temp_dir"):
            getattr(self, attr).mkdir(parents=True, exist_ok=True)

    def validate_config(self) -> List[str]:
        errors = []
        for required in ("qwen3", "starcoder2"):
            if required not in self.models:
                errors.append(f"Modèle requis '{required}' non configuré")
        if ServiceType.OCR not in self.services:
            errors.append("Service critique 'ocr' non configuré")
        if self.environment.value == "production":
            if not self.redis.password:
                errors.append("Mot de passe Redis requis en production")
            if not self.security.jwt_secret_key:
                errors.append("JWT secret key requis en production")
        return errors


# ---------- Singleton ----------
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
        errs = _settings_instance.validate_config()
        if errs:
            raise RuntimeError("\n".join(errs))
    return _settings_instance


if __name__ == "__main__":
    cfg = get_settings()
    print(cfg.model_dump_json(indent=2))
