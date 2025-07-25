# src/config.py
"""Module de configuration centralisé pour le projet Altiora (version simplifiée).

Ce module définit la structure de configuration de base de l'application
en utilisant Pydantic. Il est conçu pour être un singleton, assurant
qu'une seule instance des paramètres est utilisée dans toute l'application.
"""

from typing import Dict

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ServiceConfig(BaseModel):
    """Configuration d'un service externe."""
    host: str = Field("localhost", description="Hôte du service.")
    port: int = Field(..., description="Port du service.")
    timeout: int = Field(60, description="Délai d'attente pour les requêtes au service en secondes.")
    health_check_path: str = Field("/health", description="Chemin de l'endpoint de vérification de santé du service.")


class Settings(BaseSettings):
    """Configuration principale de l'application Altiora."""

    # Environnement
    environment: str = Field("development", description="Environnement d'exécution (development, production, etc.).")
    debug: bool = Field(True, description="Active le mode débogage.")

    # Ollama
    ollama_host: str = Field("http://localhost:11434", description="URL de l'hôte Ollama.")
    ollama_timeout: int = Field(120, description="Délai d'attente pour les requêtes Ollama.")

    # Redis
    redis_url: str = Field("redis://localhost:6379", description="URL de connexion Redis.")
    redis_ttl_sfd: int = Field(86400, description="TTL pour les résultats d'analyse SFD (24h).")
    redis_ttl_tests: int = Field(43200, description="TTL pour les tests générés (12h).")

    # Services (dictionnaire de configurations de services).
    services: Dict[str, ServiceConfig] = Field(
        default_factory=lambda: {
            "ocr": ServiceConfig(host="localhost", port=8001, timeout=60),
            "alm": ServiceConfig(host="localhost", port=8002, timeout=120),
            "excel": ServiceConfig(host="localhost", port=8003, timeout=60),
            "playwright": ServiceConfig(host="localhost", port=8004, timeout=300)
        },
        description="Configurations des microservices externes."
    )

    # Modèles de langage (LLMs).
    qwen3_model: str = Field("qwen3-sfd-analyzer", description="Nom du modèle Qwen3 pour l'analyse SFD.")
    starcoder2_model: str = Field("starcoder2-playwright", description="Nom du modèle StarCoder2 pour la génération de tests.")

    # Chemins des répertoires.
    data_dir: str = Field("./data", description="Répertoire pour les données de l'application.")
    models_dir: str = Field("./models", description="Répertoire pour les modèles d'IA.")
    logs_dir: str = Field("./logs", description="Répertoire pour les fichiers de log.")
    reports_dir: str = Field("./reports", description="Répertoire pour les rapports générés.")

    class Config:
        env_file = ".env" # Charge les variables d'environnement depuis le fichier .env.
        case_sensitive = False # Les noms de variables d'environnement ne sont pas sensibles à la casse.


# Instance singleton pour la configuration.
_settings: Settings | None = None


def get_settings() -> Settings:
    """Récupère l'instance unique des paramètres de configuration."

    Cette fonction garantit que les paramètres ne sont chargés qu'une seule fois.

    Returns:
        L'instance unique de `Settings`.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("\n--- Chargement des paramètres ---")
    # Pour la démonstration, vous pouvez définir des variables d'environnement.
    # os.environ["ENVIRONMENT"] = "production"
    # os.environ["OLLAMA_HOST"] = "http://my-ollama-server:11434"

    settings = get_settings()
    print("✅ Paramètres chargés avec succès.")

    print("\n--- Accès aux paramètres ---")
    print(f"Environnement : {settings.environment}")
    print(f"Hôte Ollama : {settings.ollama_host}")
    print(f"URL Redis : {settings.redis_url}")
    print(f"Port du service OCR : {settings.services['ocr'].port}")
    print(f"Modèle Qwen3 : {settings.qwen3_model}")
    print(f"Répertoire des logs : {settings.logs_dir}")

    # Exemple de modification (pour le test, ne pas faire en production).
    settings.debug = False
    print(f"Mode debug après modification : {settings.debug}")

    # Nettoyage des variables d'environnement si définies pour la démo.
    # if "ENVIRONMENT" in os.environ:
    #     del os.environ["ENVIRONMENT"]
    # if "OLLAMA_HOST" in os.environ:
    #     del os.environ["OLLAMA_HOST"]