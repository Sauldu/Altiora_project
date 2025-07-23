"""
Module de configuration centralisé pour le projet Altiora
Gestion unifiée de toutes les configurations avec validation Pydantic v2
"""

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

import redis.asyncio as redis
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from infrastructure.encryption import AltioraEncryption
from security.secret_manager import SecretManager

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "configs"


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


# ------------------------------------------------------------------
# Modèles
# ------------------------------------------------------------------

class OllamaConfig(BaseModel):
    host: str = Field(default="localhost", description="Hôte Ollama")
    port: int = Field(default=11434, description="Port Ollama")
    timeout: int = Field(default=180, description="Timeout (s)")
    keep_alive: str = Field(default="30m", description="Durée keep-alive")

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class ModelConfig(BaseModel):
    name: str = Field(..., description="Nom du modèle")
    base_model: str = Field(..., description="Modèle de base")
    role: str = Field(..., description="Rôle du modèle")
    api_mode: str = Field(default="generate")
    timeout: int = Field(default=120)
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=1)
    repeat_penalty: float = Field(default=1.1, ge=0.0)
    num_ctx: int = Field(default=8192)
    seed: Optional[int] = None
    stop: List[str] = Field(default_factory=list)


class ServiceConfig(BaseModel):
    name: str = Field(..., description="Nom du service")
    type: ServiceType = Field(..., description="Type de service")
    host: str = Field(default="localhost")
    port: int = Field(..., ge=1, le=65535)
    timeout: int = Field(default=60, ge=1)
    health_check_path: str = Field(default="/health")
    max_retries: int = Field(default=3, ge=0)
    enabled: bool = Field(default=True)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        return f"{self.url}{self.health_check_path}"


class RedisConfig(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0, ge=0)
    password: Optional[str] = None
    ssl: bool = Field(default=False)
    encrypt_values: bool = Field(default=True)

    ttl_sfd_analysis: int = Field(default=86400)
    ttl_generated_tests: int = Field(default=43200)
    ttl_ocr_results: int = Field(default=604800)
    ttl_model_responses: int = Field(default=3600)

    @property
    def url(self) -> str:
        scheme = "rediss" if self.ssl else "redis"
        auth = f":{self.password}@" if self.password else ""
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"

    # ---------- Redis async helpers ----------
    @staticmethod
    async def set_encrypted(
            redis_client: redis.Redis, key: str, value: Dict[str, Any], ttl: int
    ) -> None:
        cipher = AltioraEncryption("REDIS_ENCRYPTION_KEY")
        payload = cipher.encrypt_dict(value)
        await redis_client.set(key, payload, ex=ttl)

    @staticmethod
    async def get_encrypted(
            redis_client: redis.Redis, key: str
    ) -> Optional[Dict[str, Any]]:
        raw = await redis_client.get(key)
        if raw:
            cipher = AltioraEncryption("REDIS_ENCRYPTION_KEY")
            return cipher.decrypt_dict(raw)
        return None


class PipelineConfig(BaseModel):
    max_parallel_tests: int = Field(default=5, ge=1)
    max_parallel_scenarios: int = Field(default=10, ge=1)
    timeout_sfd_extraction: int = Field(default=300)
    timeout_scenario_analysis: int = Field(default=600)
    timeout_test_generation: int = Field(default=180)
    timeout_test_execution: int = Field(default=900)
    retry_max_attempts: int = Field(default=3, ge=1)
    retry_backoff_factor: float = Field(default=2.0, ge=1.0)
    retry_max_delay: int = Field(default=30, ge=1)
    fallback_enabled: bool = Field(default=True)
    fallback_use_templates: bool = Field(default=True)
    fallback_template_quality: str = Field(default="basic")


class LoggingConfig(BaseModel):
    level: LogLevel = Field(default=LogLevel.INFO)
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file: Optional[Path] = None
    max_size_mb: int = Field(default=100)
    backup_count: int = Field(default=5)

    @field_validator("file", mode="before")
    @classmethod
    def validate_file_path(cls, v):
        return Path(v) if v and not isinstance(v, Path) else v


class SecurityConfig(BaseModel):
    enable_auth: bool = Field(default=False)
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_minutes: int = Field(default=1440)
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=100)
    rate_limit_window_seconds: int = Field(default=60)

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v, info):
        if info.data.get("enable_auth") and not v:
            raise ValueError("jwt_secret_key required when auth is enabled")
        return v


# ------------------------------------------------------------------
# Settings principale
# ------------------------------------------------------------------

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
    models: Dict[str, ModelConfig] = Field(default_factory=dict)
    services: Dict[ServiceType, ServiceConfig] = Field(default_factory=dict)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    secrets: SecretManager = Field(default_factory=lambda: SecretManager(BASE_DIR / 'secrets'))

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.secrets = SecretManager(self.base_dir / "secrets")
        self._load_secrets_into_config()
        self._load_from_yaml()
        self._create_directories()
        self._apply_environment_overrides()

    def _load_secrets_into_config(self):
        """Charge les secrets dans les objets de configuration Pydantic."""
        self.security.jwt_secret_key = self.secrets.get_secret("JWT_SECRET_KEY")
        self.redis.password = self.secrets.get_secret("REDIS_PASSWORD")

    # ---------- YAML ----------
    def _load_from_yaml(self):
        services_file = CONFIG_DIR / "services.yaml"
        if services_file.exists():
            data = yaml.safe_load(services_file.read_text())
            if "ollama" in data:
                self.ollama = OllamaConfig(**data["ollama"])
            if "redis" in data:
                self.redis = RedisConfig(**data["redis"])
            for name, cfg in data.get("services", {}).items():
                self.services[ServiceType(cfg.get("type", name))] = ServiceConfig(**cfg)

        models_file = CONFIG_DIR / "models_config.yaml"
        if models_file.exists():
            models_data = yaml.safe_load(models_file.read_text())
            for name, cfg in models_data.get("models", {}).items():
                model_cfg = cfg.copy()
                if "name" in model_cfg:
                    del model_cfg["name"]
                self.models[name] = ModelConfig(name=name, **model_cfg)

    # ---------- Helpers ----------
    def _create_directories(self):
        for attr in ["data_dir", "models_dir", "logs_dir", "reports_dir", "temp_dir"]:
            getattr(self, attr).mkdir(parents=True, exist_ok=True)

    def _apply_environment_overrides(self):
        if self.environment == Environment.PRODUCTION:
            self.debug = False
            self.logging.level = LogLevel.WARNING
            self.security.enable_auth = True
            self.pipeline.fallback_enabled = False
        elif self.environment == Environment.DEVELOPMENT:
            self.debug = True
            self.logging.level = LogLevel.DEBUG
            self.security.enable_auth = False
        elif self.environment == Environment.TEST:
            self.debug = True
            for svc in self.services.values():
                svc.port += 10000

    # ---------- Public API ----------
    def get_service_config(self, service_type: ServiceType) -> Optional[ServiceConfig]:
        return self.services.get(service_type)

    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        return self.models.get(model_name)

    def get_redis_ttl(self, cache_type: str) -> int:
        ttl_map = {
            "sfd_analysis": self.redis.ttl_sfd_analysis,
            "generated_tests": self.redis.ttl_generated_tests,
            "ocr_results": self.redis.ttl_ocr_results,
            "model_responses": self.redis.ttl_model_responses,
        }
        return ttl_map.get(cache_type, 3600)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment": self.environment.value,
            "debug": self.debug,
            "ollama": self.ollama.model_dump(),
            "redis": self.redis.model_dump(exclude={"password"}),
            "models": {k: v.model_dump() for k, v in self.models.items()},
            "services": {k.value: v.model_dump() for k, v in self.services.items()},
            "pipeline": self.pipeline.model_dump(),
            "logging": self.logging.model_dump(),
            "security": self.security.model_dump(exclude={"jwt_secret_key"}),
        }

    def validate_config(self) -> List[str]:
        errors = []
        if "qwen3" not in self.models:
            errors.append("Modèle requis 'qwen3' non configuré")
        if "starcoder2" not in self.models:
            errors.append("Modèle requis 'starcoder2' non configuré")
        if ServiceType.OCR not in self.services:
            errors.append("Service critique 'ocr' non configuré")
        if self.environment == Environment.PRODUCTION:
            if not self.redis.password:
                errors.append("Mot de passe Redis requis en production")
            if not self.security.jwt_secret_key:
                errors.append("JWT secret key requis en production")
        return errors


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
        errs = _settings_instance.validate_config()
        if errs:
            print("⚠️ Erreurs de configuration détectées:")
            for e in errs:
                print(f"  - {e}")
    return _settings_instance


# ------------------------------------------------------------------
# Extras
# ------------------------------------------------------------------

def save_config_to_yaml(settings: Settings, output_path: Path):
    output_path.write_text(yaml.dump(settings.to_dict(), allow_unicode=True))


def merge_config_files(*files: Path) -> Dict[str, Any]:
    merged = {}
    for fp in files:
        if fp.exists():
            _deep_merge(merged, yaml.safe_load(fp.read_text()) or {})
    return merged


def _deep_merge(base: Dict, update: Dict) -> Dict:
    for k, v in update.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


if __name__ == "__main__":
    cfg = get_settings()
    print(cfg.to_dict())
