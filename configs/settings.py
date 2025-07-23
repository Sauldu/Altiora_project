# src/config/settings.py
import yaml
from pydantic import BaseSettings, ValidationError

class Settings(BaseSettings):
    environment: str
    debug: bool
    log_level: str
    ollama_host: str
    ollama_timeout: int
    ollama_keep_alive: str
    qwen3_model: str
    starcoder2_model: str
    redis_url: str
    redis_password: str
    redis_db: int
    redis_ttl_sfd: int
    redis_ttl_tests: int
    redis_ttl_ocr: int
    redis_ttl_model: int
    ocr_service_host: str
    ocr_service_port: int
    ocr_service_timeout: int
    doctoplus_config: str
    alm_service_host: str
    alm_service_port: int
    alm_service_timeout: int
    alm_api_url: str
    alm_api_key: str
    excel_service_host: str
    excel_service_port: int
    excel_service_timeout: int
    playwright_service_host: str
    playwright_service_port: int
    playwright_service_timeout: int
    playwright_workers: int
    playwright_browser: str
    playwright_headed: bool
    playwright_screenshot_on_failure: bool
    playwright_video_on_failure: bool
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expiration_minutes: int
    rate_limit_enabled: bool
    rate_limit_requests: int
    rate_limit_window_seconds: int
    allowed_origins: list
    data_dir: str
    models_dir: str
    logs_dir: str
    reports_dir: str
    temp_dir: str
    cache_dir: str
    pipeline_max_parallel_tests: int
    pipeline_max_parallel_scenarios: int
    pipeline_fallback_enabled: bool
    pipeline_retry_max_attempts: int
    pipeline_retry_backoff_factor: float
    prometheus_enabled: bool
    prometheus_port: int
    dash_enabled: bool
    dash_port: int
    compose_project_name: str
    docker_buildkit: int
    compose_docker_cli_build: int
    ollama_memory_limit: str
    ollama_cpu_limit: int
    redis_memory_limit: str
    ocr_memory_limit: str
    mock_ocr_service: bool
    mock_alm_service: bool
    use_local_models: bool

    def __init__(self):
        with open("configs/env-example-complete.yaml", "r") as f:
            config = yaml.safe_load(f)
        try:
            super().__init__(**config)
        except ValidationError as e:
            print(e.json())
            raise

# Utilisation
settings = Settings()