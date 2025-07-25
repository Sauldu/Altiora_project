# configs/settings_legacy.py
from functools import lru_cache

from pydantic import BaseSettings


class Settings(BaseSettings):
    # Configuration générale
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Configuration Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_timeout: int = 300
    ollama_keep_alive: str = "10m"

    # Configuration Redis
    redis_url: str = "redis://localhost:6379"
    redis_password: str = ""
    redis_db: int = 0
    redis_ttl_sfd: int = 3600
    redis_ttl_tests: int = 3600
    redis_ttl_ocr: int = 3600
    redis_ttl_model: int = 3600

    # Configuration des services
    ocr_service_host: str = "localhost"
    ocr_service_port: int = 8001
    ocr_service_timeout: int = 30

    alm_service_host: str = "localhost"
    alm_service_port: int = 8002
    alm_service_timeout: int = 30
    alm_api_url: str = ""
    alm_api_key: str = ""

    excel_service_host: str = "localhost"
    excel_service_port: int = 8003
    excel_service_timeout: int = 30

    playwright_service_host: str = "localhost"
    playwright_service_port: int = 8004
    playwright_service_timeout: int = 30
    playwright_workers: int = 4
    playwright_browser: str = "chromium"
    playwright_headed: bool = False
    playwright_screenshot_on_failure: bool = True
    playwright_video_on_failure: bool = True

    # Configuration JWT
    jwt_secret_key: str = "secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Configuration des limites de taux
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # Configuration des répertoires
    data_dir: str = "./data"
    models_dir: str = "./models"
    logs_dir: str = "./logs"
    reports_dir: str = "./reports"
    temp_dir: str = "./temp"
    cache_dir: str = "./cache"

    # Configuration des pipelines
    pipeline_max_parallel_tests: int = 10
    pipeline_max_parallel_scenarios: int = 10
    pipeline_fallback_enabled: bool = True
    pipeline_retry_max_attempts: int = 3
    pipeline_retry_backoff_factor: float = 0.5

    # Configuration Prometheus
    prometheus_enabled: bool = False
    prometheus_port: int = 8000

    # Configuration Dash
    dash_enabled: bool = False
    dash_port: int = 8050

    # Configuration Docker
    compose_project_name: str = "altiora"
    docker_buildkit: int = 1
    compose_docker_cli_build: int = 1

    # Limites de mémoire et CPU
    ollama_memory_limit: str = "2g"
    ollama_cpu_limit: int = 2
    redis_memory_limit: str = "256m"
    ocr_memory_limit: str = "512m"

    # Configuration des services mock
    mock_ocr_service: bool = False
    mock_alm_service: bool = False

    # Utilisation des modèles locaux
    use_local_models: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings():
    return Settings()


# Utilisation
settings = get_settings()
