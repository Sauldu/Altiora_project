"""
Module de configuration centralisé pour le projet Altiora
"""
from typing import Dict

from pydantic import BaseSettings


class ServiceConfig(BaseSettings):
    """Configuration d'un service"""
    host: str = "localhost"
    port: int
    timeout: int = 60
    health_check_path: str = "/health"


class Settings(BaseSettings):
    """Configuration principale de l'application"""

    # Environnement
    environment: str = "development"
    debug: bool = True

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_timeout: int = 120

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_ttl_sfd: int = 86400  # 24h
    redis_ttl_tests: int = 43200  # 12h

    # Services
    services: Dict[str, Dict] = {
        "ocr": {"host": "localhost", "port": 8001, "timeout": 60},
        "alm": {"host": "localhost", "port": 8002, "timeout": 120},
        "excel": {"host": "localhost", "port": 8003, "timeout": 60},
        "playwright": {"host": "localhost", "port": 8004, "timeout": 300}
    }

    # Modèles
    qwen3_model: str = "qwen3-sfd-analyzer"
    starcoder2_model: str = "starcoder2-playwright"

    # Chemins
    data_dir: str = "./data"
    models_dir: str = "./models"
    logs_dir: str = "./logs"
    reports_dir: str = "./reports"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Instance singleton
_settings = None


def get_settings() -> Settings:
    """Récupère l'instance unique des settings"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
