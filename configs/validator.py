# src/config/validator.py
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, ValidationError, Field, validator
from pydantic_settings import BaseSettings

from configs import config_module  # charge le modèle Pydantic complet


class ConfigValidator:
    """
    Charge et valide master_config.yaml + surcharge via variables d’environnement.
    Leve une ValidationError si une valeur est manquante ou mal formatée.
    """

    def __init__(self, config_path: Path = Path("configs/master_config.yaml")) -> None:
        self.config_path = config_path
        self.errors: List[str] = []

    def load_yaml(self) -> Dict[str, Any]:
        """
        Charge le YAML et applique la résolution ${VAR:-default}.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Fichier de configuration introuvable : {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        env = os.getenv("ENVIRONMENT", "development")
        profile = raw["profiles"].get(env, {})
        merged = {**raw, **profile}

        # Remplacement des variables ${...}
        def resolve(obj: Any) -> Any:
            if isinstance(obj, str):
                return os.path.expandvars(obj)
            if isinstance(obj, dict):
                return {k: resolve(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [resolve(item) for item in obj]
            return obj

        return resolve(merged)

    def validate(self) -> config_module.Settings:
        """
        Valide la configuration complète via Pydantic.
        Retourne l'instance validée ou lève ValidationError.
        """
        data = self.load_yaml()
        try:
            return config_module.Settings(**data)
        except ValidationError as e:
            self.errors = [f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()]
            raise RuntimeError("Configuration invalide :\n" + "\n".join(self.errors)) from e


# ---------- Hook de démarrage ----------
def validate_on_startup() -> config_module.Settings:
    """
    À appeler une seule fois au démarrage de l'application.
    """
    validator = ConfigValidator()
    return validator.validate()


# ---------- CLI utilitaire ----------
if __name__ == "__main__":
    try:
        cfg = validate_on_startup()
        logger.info("✅ Configuration valide.")
    except Exception as e:
        print("❌ Erreur de configuration :", e)
        exit(1)