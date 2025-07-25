# configs/settings_loader.py
"""Chargeur de paramètres de configuration pour l'application Altiora.

Ce module est responsable du chargement des paramètres de configuration
depuis un fichier YAML (`master_config.yaml`) et de leur fusion avec
les variables d'environnement. Il gère également la résolution des
variables d'environnement imbriquées (`${VAR:-default_value}`).
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field

# ---------- Modèle Pydantic (simplifié pour le chargement initial) ----------
# Ce modèle est une représentation simplifiée des paramètres pour le chargement
# initial. La validation complète est effectuée par `config_module.Settings`.
class UnifiedSettings(BaseModel):
    """Modèle Pydantic simplifié pour le chargement initial des paramètres."""
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # Services (URLs complètes après résolution)
    redis_url: str
    ollama_url: str
    ocr_url: str
    alm_url: str
    excel_url: str
    playwright_url: str
    dash_url: Optional[str] = None # Ajouté pour le service Dash

    # Autres paramètres
    jwt_secret_key: str
    rate_limit_requests: int
    allowed_origins: list[str]


# ---------- Chargeur de Paramètres ----------
def load_settings(config_path: Path = Path("configs/master_config.yaml")) -> UnifiedSettings:
    """Charge les paramètres de configuration depuis un fichier YAML et les variables d'environnement.

    Args:
        config_path: Le chemin vers le fichier de configuration principal (master_config.yaml).

    Returns:
        Une instance de `UnifiedSettings` contenant les paramètres chargés et résolus.

    Raises:
        FileNotFoundError: Si le fichier de configuration n'est pas trouvé.
        yaml.YAMLError: Si le fichier YAML est mal formé.
        ValueError: Si des paramètres critiques sont manquants après résolution.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Le fichier de configuration {config_path} est introuvable.")

    with open(config_path, encoding="utf-8") as f:
        full_config_data = yaml.safe_load(f)

    # Détermine l'environnement actuel (par défaut 'development').
    env = os.getenv("ENVIRONMENT", "development")

    # Fusionne la configuration globale avec le profil spécifique à l'environnement.
    profile_config = full_config_data.get("profiles", {}).get(env, {})
    merged_config = {**full_config_data, **profile_config}

    # Fonction récursive pour résoudre les variables d'environnement imbriquées.
    def resolve_env_vars(obj: Any) -> Any:
        if isinstance(obj, str):
            # Utilise os.path.expandvars pour résoudre ${VAR} ou ${VAR:-default}.
            return os.path.expandvars(obj)
        if isinstance(obj, dict):
            return {k: resolve_env_vars(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve_env_vars(item) for item in obj]
        return obj

    # Applique la résolution des variables d'environnement à toute la configuration.
    resolved_config = resolve_env_vars(merged_config)

    # Crée et retourne l'instance de UnifiedSettings.
    return UnifiedSettings(**resolved_config)


# ---------- Singleton ----------
_settings: Optional[UnifiedSettings] = None


def get_settings() -> UnifiedSettings:
    """Retourne l'instance singleton des paramètres de configuration."

    Cette fonction garantit que les paramètres ne sont chargés qu'une seule fois.

    Returns:
        L'instance unique de `UnifiedSettings`.
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Crée un fichier master_config.yaml factice pour la démonstration.
    temp_config_path = Path("temp_master_config.yaml")
    temp_config_path.write_text("""
# master_config.yaml factice
environment: development
debug: true
log_level: INFO

redis_url: redis://localhost:6379
ollama_url: http://localhost:11434
ocr_url: http://localhost:8001
alm_url: http://localhost:8002
excel_url: http://localhost:8003
playwright_url: http://localhost:8004
dash_url: http://localhost:8050

jwt_secret_key: ${JWT_SECRET_KEY:-default_jwt_secret}
rate_limit_requests: 100
allowed_origins:
  - "*"

profiles:
  production:
    debug: false
    log_level: WARNING
    jwt_secret_key: ${PROD_JWT_SECRET_KEY}
""")

    print("\n--- Démonstration du chargement des paramètres ---")
    try:
        # Simule une variable d'environnement.
        os.environ["PROD_JWT_SECRET_KEY"] = "super_secret_prod_key"

        # Charge les paramètres pour l'environnement de développement.
        print("Chargement pour l'environnement 'development'...")
        settings_dev = load_settings(temp_config_path)
        print(f"Debug (dev) : {settings_dev.debug}")
        print(f"JWT Secret (dev) : {settings_dev.jwt_secret_key}")

        # Charge les paramètres pour l'environnement de production.
        os.environ["ENVIRONMENT"] = "production"
        print("\nChargement pour l'environnement 'production'...")
        settings_prod = load_settings(temp_config_path)
        print(f"Debug (prod) : {settings_prod.debug}")
        print(f"JWT Secret (prod) : {settings_prod.jwt_secret_key}")

    except Exception as e:
        logging.error(f"Erreur lors de la démonstration : {e}")
    finally:
        # Nettoyage.
        temp_config_path.unlink(missing_ok=True)
        if "PROD_JWT_SECRET_KEY" in os.environ:
            del os.environ["PROD_JWT_SECRET_KEY"]
        if "ENVIRONMENT" in os.environ:
            del os.environ["ENVIRONMENT"]
