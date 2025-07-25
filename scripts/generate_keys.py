#!/usr/bin/env python3
"""Script pour générer les secrets nécessaires et les enregistrer dans un fichier .env.

Ce script facilite la configuration initiale d'un nouvel environnement en générant
automatiquement les clés cryptographiques requises (pour JWT, chiffrement, etc.).
Il propose de créer ou d'écraser un fichier `.env` à la racine du projet avec
les clés générées et des placeholders pour les clés d'API externes.

Utilisation :
    python -m scripts.generate_keys
"""

import os
import logging
from pathlib import Path

# Assurez-vous que le chemin du projet est dans sys.path pour l'import
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.security.secret_manager import SecretsManager

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    """Fonction principale du script."""
    env_file = Path(".env")

    # Vérifie si le fichier .env existe déjà et demande confirmation pour l'écraser.
    if env_file.exists():
        logger.warning(f"⚠️  Le fichier `{env_file}` existe déjà !")
        response = input("Voulez-vous l'écraser avec de nouvelles clés ? [y/N]: ")
        if response.lower() != 'y':
            logger.info("Opération annulée.")
            return

    # Génération des secrets nécessaires.
    secrets = {
        "JWT_SECRET_KEY": SecretsManager.generate_secret_key(),
        "ENCRYPTION_KEY": SecretsManager.generate_secret_key(),
        "ALM_API_KEY": "",
        "OPENAI_API_KEY": "",
        "AZURE_CONTENT_SAFETY_KEY": ""
    }

    # Écriture sécurisée dans le fichier .env.
    try:
        with open(env_file, "w", encoding='utf-8') as f:
            f.write("# Fichier de secrets pour le projet Altiora\n")
            f.write("# ATTENTION : NE PAS COMMIT CE FICHIER DANS GIT !\n\n")
            for key, value in secrets.items():
                f.write(f"{key}={value}\n")

        logger.info(f"✅ Les secrets ont été générés avec succès dans `{env_file}`.")
        logger.info("🔒 N'oubliez pas de remplir les valeurs vides pour les clés d'API externes.")
        logger.info("🔒 Assurez-vous que le fichier `.env` est bien listé dans votre `.gitignore`.")
    except (IOError, OSError) as e:
        logger.error(f"❌ Erreur lors de l'écriture dans le fichier .env : {e}")


if __name__ == "__main__":
    main()
