# configs/validator.py
"""Module de validation de la configuration de l'application Altiora.

Ce module est responsable du chargement et de la validation rigoureuse
de la configuration de l'application à partir d'un fichier YAML (master_config.yaml)
et des variables d'environnement. Il utilise Pydantic pour garantir que
toutes les valeurs sont présentes, correctement typées et formatées.
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import ValidationError

# Importe le modèle Pydantic complet de la configuration.
from configs import config_module

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Charge et valide la configuration complète de l'application."""

    def __init__(self, config_path: Path = Path("configs/master_config.yaml")) -> None:
        """Initialise le validateur de configuration.

        Args:
            config_path: Le chemin vers le fichier de configuration principal (master_config.yaml).
        """
        self.config_path = config_path
        self.errors: List[str] = []

    def load_yaml(self) -> Dict[str, Any]:
        """Charge le contenu du fichier YAML et applique la résolution des variables d'environnement.

        Returns:
            Un dictionnaire contenant la configuration fusionnée et résolue.

        Raises:
            FileNotFoundError: Si le fichier de configuration n'est pas trouvé.
            yaml.YAMLError: Si le fichier YAML est mal formé.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Fichier de configuration introuvable : {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)

        # Détermine l'environnement actuel.
        env = os.getenv("ENVIRONMENT", "development")

        # Fusionne la configuration globale avec le profil spécifique à l'environnement.
        profile_config = raw_config.get("profiles", {}).get(env, {})
        merged_config = {**raw_config, **profile_config}

        # Fonction récursive pour résoudre les variables d'environnement.
        def resolve_env_vars(obj: Any) -> Any:
            if isinstance(obj, str):
                # Utilise os.path.expandvars pour résoudre ${VAR} ou ${VAR:-default_value}.
                return os.path.expandvars(obj)
            if isinstance(obj, dict):
                return {k: resolve_env_vars(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [resolve_env_vars(item) for item in obj]
            return obj

        return resolve_env_vars(merged_config)

    def validate(self) -> config_module.Settings:
        """Valide la configuration complète via le modèle Pydantic `config_module.Settings`.

        Returns:
            L'instance validée de `config_module.Settings`.

        Raises:
            RuntimeError: Si la validation échoue, avec les détails des erreurs.
        """
        data = self.load_yaml()
        try:
            # Tente de créer une instance du modèle Settings, ce qui déclenche la validation Pydantic.
            return config_module.Settings(**data)
        except ValidationError as e:
            # Capture les erreurs de validation Pydantic et les formate pour une meilleure lisibilité.
            self.errors = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in e.errors()
            ]
            raise RuntimeError("Configuration invalide :\n" + "\n".join(self.errors)) from e


# ---------- Hook de démarrage ----------
def validate_on_startup() -> config_module.Settings:
    """Fonction utilitaire à appeler une seule fois au démarrage de l'application.

    Elle charge et valide la configuration, et lève une erreur si la configuration est invalide.

    Returns:
        L'instance validée de `config_module.Settings`.
    """
    validator = ConfigValidator()
    return validator.validate()


# ---------- Utilitaire CLI ----------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("\n--- Validation de la configuration au démarrage ---")
    try:
        # Pour la démonstration, assurez-vous d'avoir un fichier master_config.yaml valide
        # ou simulez-en un.
        # Exemple de simulation d'un fichier master_config.yaml
        # Path("configs/master_config.yaml").write_text("""
        # environment: development
        # ollama:
        #   host: localhost
        #   port: 11434
        # redis:
        #   host: localhost
        #   port: 6379
        #   password: null
        # security:
        #   enable_auth: false
        #   jwt_secret_key: null
        # """)

        cfg = validate_on_startup()
        logger.info("✅ Configuration valide. Application prête à démarrer.")
        # print(cfg.model_dump_json(indent=2)) # Pour afficher la config validée.
    except Exception as e:
        logger.error("❌ Erreur de configuration :", e)
        exit(1)
