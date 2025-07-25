# configs/settings_loader.py
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import BaseModel, Field

# ---------- Modèle Pydantic ----------
class UnifiedSettings(BaseModel):
    # Profils
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # Services
    redis_url: str
    ollama_url: str
    ocr_url: str
    alm_url: str
    excel_url: str
    playwright_url: str

    # Autres
    jwt_secret_key: str
    rate_limit_requests: int
    allowed_origins: list[str]

# ---------- Chargeur ----------
def load_settings(config_path: Path = Path("configs/master_config.yaml")) -> UnifiedSettings:
    env = os.getenv("ENVIRONMENT", "development")

    with open(config_path, encoding="utf-8") as f:
        full = yaml.safe_load(f)

    # Fusion : global + profil + surcharge ENV
    profile = full["profiles"].get(env, {})
    merged = {**full, **profile}

    # Remplacement des ${VAR:-default}
    def resolve(value: Any) -> Any:
        if isinstance(value, str):
            return os.path.expandvars(value)
        return value

    def deep_resolve(obj: Dict[str, Any]) -> Dict[str, Any]:
        return {k: deep_resolve(v) if isinstance(v, dict) else resolve(v) for k, v in obj.items()}

    resolved = deep_resolve(merged)
    return UnifiedSettings(**resolved)

# ---------- Singleton ----------
_settings = None

def get_settings():
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings