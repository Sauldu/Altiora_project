# configs/settings_legacy.py
"""Fichier de configuration hérité (legacy) pour l'application Altiora.

Ce module contient une version précédente de la configuration de l'application,
utilisant `pydantic.BaseSettings` de manière monolithique. Il est conservé
pour des raisons de compatibilité ou de référence historique, mais la
configuration principale est désormais gérée par `configs.config_module.py`.

Il est recommandé d'utiliser `configs.config_module.get_settings()` pour
accéder à la configuration actuelle de l'application.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Paramètres de configuration hérités pour l'application Altiora.

    Ces paramètres sont chargés depuis les variables d'environnement ou un fichier `.env`.
    """
    # Configuration générale
    environment: str = Field("development", description="Environnement d'exécution (development, staging, production).")
    debug: bool = Field(True, description="Active le mode débogage.")
    log_level: str = Field("INFO", description="Niveau de journalisation (INFO, DEBUG, WARNING, ERROR, CRITICAL).")

    # Configuration Ollama
    ollama_host: str = Field("http://localhost:11434", description="URL de l'hôte Ollama.")
    ollama_timeout: int = Field(300, description="Délai d'attente pour les requêtes Ollama en secondes.")
    ollama_keep_alive: str = Field("10m", description="Durée de maintien des modèles en mémoire par Ollama.")

    # Configuration Redis
    redis_url: str = Field("redis://localhost:6379", description="URL de connexion Redis.")
    redis_password: str = Field("", description="Mot de passe pour la connexion Redis.")
    redis_db: int = Field(0, description="Numéro de la base de données Redis.")
    redis_ttl_sfd: int = Field(3600, description="TTL pour les résultats d'analyse SFD en secondes.")
    redis_ttl_tests: int = Field(3600, description="TTL pour les tests générés en secondes.")
    redis_ttl_ocr: int = Field(3600, description="TTL pour les résultats OCR en secondes.")
    redis_ttl_model: int = Field(3600, description="TTL pour les réponses des modèles en secondes.")

    # Configuration des services
    ocr_service_host: str = Field("localhost", description="Hôte du service OCR.")
    ocr_service_port: int = Field(8001, description="Port du service OCR.")
    ocr_service_timeout: int = Field(30, description="Délai d'attente pour le service OCR.")

    alm_service_host: str = Field("localhost", description="Hôte du service ALM.")
    alm_service_port: int = Field(8002, description="Port du service ALM.")
    alm_service_timeout: int = Field(30, description="Délai d'attente pour le service ALM.")
    alm_api_url: str = Field("", description="URL de l'API ALM externe.")
    alm_api_key: str = Field("", description="Clé d'API pour le service ALM.")

    excel_service_host: str = Field("localhost", description="Hôte du service Excel.")
    excel_service_port: int = Field(8003, description="Port du service Excel.")
    excel_service_timeout: int = Field(30, description="Délai d'attente pour le service Excel.")

    playwright_service_host: str = Field("localhost", description="Hôte du service Playwright.")
    playwright_service_port: int = Field(8004, description="Port du service Playwright.")
    playwright_service_timeout: int = Field(30, description="Délai d'attente pour le service Playwright.")
    playwright_workers: int = Field(4, description="Nombre de workers Playwright parallèles.")
    playwright_browser: str = Field("chromium", description="Navigateur par défaut pour Playwright.")
    playwright_headed: bool = Field(False, description="Exécuter Playwright en mode visible.")
    playwright_screenshot_on_failure: bool = Field(True, description="Prendre une capture d'écran en cas d'échec.")
    playwright_video_on_failure: bool = Field(True, description="Enregistrer une vidéo en cas d'échec.")

    # Configuration JWT
    jwt_secret_key: str = Field("secret", description="Clé secrète pour la signature JWT.")
    jwt_algorithm: str = Field("HS256", description="Algorithme de signature JWT.")
    jwt_expiration_minutes: int = Field(60, description="Durée de validité des jetons JWT en minutes.")

    # Configuration des limites de taux
    rate_limit_enabled: bool = Field(False, description="Activer la limitation de débit.")
    rate_limit_requests: int = Field(100, description="Nombre maximal de requêtes par fenêtre.")
    rate_limit_window_seconds: int = Field(60, description="Fenêtre de temps pour la limitation de débit en secondes.")

    # Configuration des répertoires
    data_dir: str = Field("./data", description="Répertoire pour les données.")
    models_dir: str = Field("./models", description="Répertoire pour les modèles.")
    logs_dir: str = Field("./logs", description="Répertoire pour les logs.")
    reports_dir: str = Field("./reports", description="Répertoire pour les rapports.")
    temp_dir: str = Field("./temp", description="Répertoire pour les fichiers temporaires.")
    cache_dir: str = Field("./cache", description="Répertoire pour le cache.")

    # Configuration des pipelines
    pipeline_max_parallel_tests: int = Field(10, description="Nombre maximal de tests parallèles dans le pipeline.")
    pipeline_max_parallel_scenarios: int = Field(10, description="Nombre maximal de scénarios parallèles dans le pipeline.")
    pipeline_fallback_enabled: bool = Field(True, description="Activer le fallback en cas d'échec du pipeline.")
    pipeline_retry_max_attempts: int = Field(3, description="Nombre maximal de tentatives pour les étapes du pipeline.")
    pipeline_retry_backoff_factor: float = Field(0.5, description="Facteur de backoff pour les retries du pipeline.")

    # Configuration Prometheus
    prometheus_enabled: bool = Field(False, description="Activer l'exposition des métriques Prometheus.")
    prometheus_port: int = Field(8000, description="Port pour les métriques Prometheus.")

    # Configuration Dash
    dash_enabled: bool = Field(False, description="Activer le tableau de bord Dash.")
    dash_port: int = Field(8050, description="Port pour le tableau de bord Dash.")

    # Configuration Docker
    compose_project_name: str = Field("altiora", description="Nom du projet Docker Compose.")
    docker_buildkit: int = Field(1, description="Activer Docker BuildKit.")
    compose_docker_cli_build: int = Field(1, description="Utiliser Docker CLI pour la construction.")

    # Limites de mémoire et CPU
    ollama_memory_limit: str = Field("2g", description="Limite de mémoire pour Ollama.")
    ollama_cpu_limit: int = Field(2, description="Limite CPU pour Ollama.")
    redis_memory_limit: str = Field("256m", description="Limite de mémoire pour Redis.")
    ocr_memory_limit: str = Field("512m", description="Limite de mémoire pour le service OCR.")

    # Configuration des services mock
    mock_ocr_service: bool = Field(False, description="Simuler le service OCR.")
    mock_alm_service: bool = Field(False, description="Simuler le service ALM.")

    # Utilisation des modèles locaux
    use_local_models: bool = Field(False, description="Utiliser des modèles locaux au lieu des services externes.")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Retourne l'instance singleton des paramètres de configuration hérités."

    Cette fonction utilise `lru_cache` pour s'assurer que les paramètres ne sont
    chargés qu'une seule fois, même si `get_settings` est appelée plusieurs fois.

    Returns:
        L'instance unique de `Settings`.
    """
    return Settings()


# Instance globale des paramètres pour un accès facile.
settings = get_settings()


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("\n--- Chargement des paramètres hérités ---")
    # Pour la démonstration, on peut définir des variables d'environnement.
    # os.environ["ENVIRONMENT"] = "production"
    # os.environ["REDIS_PASSWORD"] = "my_prod_redis_pass"

    current_settings = get_settings()
    print("✅ Paramètres chargés avec succès.")

    print("\n--- Accès aux paramètres ---")
    print(f"Environnement : {current_settings.environment}")
    print(f"Niveau de log : {current_settings.log_level}")
    print(f"URL Redis : {current_settings.redis_url}")
    print(f"Port du service Playwright : {current_settings.playwright_service_port}")
    print(f"Clé secrète JWT : {current_settings.jwt_secret_key} (masquée si sensible)")

    # Exemple de modification (pour le test, ne pas faire en production).
    current_settings.debug = False
    print(f"Mode debug après modification : {current_settings.debug}")

    # Nettoyage des variables d'environnement si définies pour la démo.
    # if "ENVIRONMENT" in os.environ:
    #     del os.environ["ENVIRONMENT"]
    # if "REDIS_PASSWORD" in os.environ:
    #     del os.environ["REDIS_PASSWORD"]