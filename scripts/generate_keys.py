#!/usr/bin/env python3
"""
Génère et propose d’enregistrer les secrets dans .env
"""


import os
from pathlib import Path
from src.security.secret_manager import SecretsManager


def main():
    env_file = Path(".env")

    if env_file.exists():
        print("⚠️  .env existe déjà !")
        response = input("Écraser ? [y/N]: ")
        if response.lower() != 'y':
            return

    # Génération des secrets
    secrets = {
        "JWT_SECRET_KEY": SecretsManager.generate_missing_secrets(),
        "ENCRYPTION_KEY": SecretsManager.generate_missing_secrets(),
        "OLLAMA_API_KEY": "",
        "OPENAI_API_KEY": "",
        "AZURE_CONTENT_SAFETY_KEY": ""
    }

    # Écriture sécurisée
    with open(env_file, "w") as f:
        f.write("# Altiora Secrets - NE PAS COMMIT CE FICHIER !\n")
        for key, value in secrets.items():
            f.write(f"{key}={value}\n")

    print(f"✅ Secrets générés dans {env_file}")
    print("🔒 Assurez-vous d’ajouter .env à .gitignore")


if __name__ == "__main__":
    main()