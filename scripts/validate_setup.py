#!/usr/bin/env python3
"""Script de validation complet pour l'environnement de développement Altiora.

Ce script vérifie que tous les composants critiques de l'environnement sont
correctement installés et configurés. Il est conçu pour être exécuté après
l'installation initiale ou pour diagnostiquer des problèmes d'environnement.

Les vérifications incluent :
- La cohérence entre les modèles Ollama configurés et ceux réellement installés.
- La présence et la version des dépendances Python critiques (PyTorch, etc.).
"""
import sys
import subprocess
import logging
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class SetupValidator:
    """Valide l'installation complète d'Altiora."""

    def __init__(self):
        """Initialise le validateur."""
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_models(self):
        """Vérifie la cohérence des modèles Ollama."""
        logger.info("🔍 Vérification des modèles Ollama...")
        try:
            # Charge la configuration des modèles depuis le fichier YAML.
            models_config_path = Path("configs/models.yaml")
            if not models_config_path.exists():
                self.errors.append(f"Le fichier de configuration des modèles `{models_config_path}` est introuvable.")
                return

            models_config = yaml.safe_load(models_config_path.read_text())
            required_models = [conf['ollama_tag'] for conf in models_config.get("models", {}).values()]

            # Récupère la liste des modèles installés via la commande Ollama.
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            installed_models = result.stdout

            # Compare les modèles requis et installés.
            for model_tag in required_models:
                if model_tag not in installed_models:
                    self.errors.append(
                        f"Modèle manquant : `{model_tag}` n'est pas installé dans Ollama. "
                        f"Exécutez `ollama pull {model_tag}`."
                    )
                else:
                    logger.info(f"  - ✅ Modèle `{model_tag}` trouvé.")

        except FileNotFoundError:
            self.errors.append("La commande `ollama` n'a pas été trouvée. Assurez-vous qu'Ollama est installé et dans le PATH.")
        except (subprocess.CalledProcessError, yaml.YAMLError, KeyError) as e:
            self.errors.append(f"Une erreur est survenue lors de la validation des modèles : {e}")

    def validate_dependencies(self):
        """Vérifie la présence et la version des dépendances Python critiques."""
        logger.info("\n🔍 Vérification des dépendances Python...")
        try:
            import torch
            logger.info(f"  - ✅ PyTorch version {torch.__version__} trouvé.")
            if not torch.__version__.startswith("2."):
                self.warnings.append(
                    f"La version de PyTorch ({torch.__version__}) n'est pas la version 2.x recommandée."
                )

            import transformers
            logger.info(f"  - ✅ Transformers version {transformers.__version__} trouvé.")

            import peft
            logger.info(f"  - ✅ PEFT version {peft.__version__} trouvé.")

        except ImportError as e:
            self.errors.append(f"Dépendance Python manquante : {e}. Exécutez `pip install -r requirements.txt`.")

    def run(self) -> bool:
        """Exécute toutes les validations et affiche un résumé.

        Returns:
            True si aucune erreur n'a été trouvée, False sinon.
        """
        self.validate_models()
        self.validate_dependencies()

        print("\n" + "-"*50)
        if self.errors:
            logger.error("❌ DES ERREURS CRITIQUES ONT ÉTÉ TROUVÉES :")
            for error in self.errors:
                logger.error(f"  - {error}")

        if self.warnings:
            logger.warning("\n⚠️  AVERTISSEMENTS :")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        if not self.errors and not self.warnings:
            logger.info("✅ L'environnement semble correctement configuré !")
        
        return not self.errors


if __name__ == "__main__":
    validator = SetupValidator()
    logger.info("Lancement de la validation de l'environnement Altiora...")
    if not validator.run():
        logger.error("\nValidation échouée. Veuillez corriger les erreurs ci-dessus.")
        sys.exit(1)
    else:
        logger.info("\nValidation réussie.")
