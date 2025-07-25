"""
Gestionnaire de secrets ultra-sécurisé
- Charge uniquement depuis variables d’environnement
- Validation forte au démarrage
- Zero secret hardcodé
"""

import os
import secrets
from typing import Optional
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()  # Charge .env si présent


class SecretsManager:
    """Singleton sécurisé pour tous les secrets."""

    REQUIRED_SECRETS = {
        "JWT_SECRET_KEY": "Clé secrète JWT (min 32 caractères)",
        "OLLAMA_API_KEY": "Clé API Ollama (optionnelle)",
        "OPENAI_API_KEY": "Clé OpenAI pour modération (optionnelle)",
        "AZURE_CONTENT_SAFETY_KEY": "Clé Azure Content Safety (optionnelle)",
        "ENCRYPTION_KEY": "Clé de chiffrement Fernet (32 bytes base64)",
    }

    @classmethod
    def get_secret(cls, key: str, required: bool = True) -> str:
        """Récupère un secret depuis l’environnement."""
        value = os.getenv(key)
        if required and not value:
            raise ValueError(f"Secret manquant: {key} ({cls.REQUIRED_SECRETS[key]})")
        return value or ""

    @classmethod
    def validate_secrets(cls) -> None:
        """Validation stricte au démarrage de l’application."""
        errors = []

        # Validation JWT
        jwt_key = cls.get_secret("JWT_SECRET_KEY")
        if jwt_key and len(jwt_key) < 32:
            errors.append("JWT_SECRET_KEY doit faire au moins 32 caractères")

        # Validation format Fernet
        encryption_key = cls.get_secret("ENCRYPTION_KEY")
        if encryption_key:
            try:
                Fernet(encryption_key.encode())
            except Exception:
                errors.append("ENCRYPTION_KEY invalide (doit être 32 bytes base64)")

        if errors:
            raise RuntimeError("\n".join(errors))

    @classmethod
    def generate_missing_secrets(cls) -> None:
        """Génère automatiquement les secrets manquants."""
        secrets_to_generate = {
            "JWT_SECRET_KEY": secrets.token_urlsafe(64),
            "ENCRYPTION_KEY": Fernet.generate_key().decode()
        }

        for key, value in secrets_to_generate.items():
            if not os.getenv(key):
                logger.info(f"⚠️  Secret généré automatiquement : {key}")
                logger.info(f"   Ajoutez dans votre .env : {key}={value}")