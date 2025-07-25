# configs/config_module.py
"""Module de configuration centralisé pour le projet Altiora.

Ce module définit la structure de configuration complète de l'application
en utilisant Pydantic v2. Il permet une gestion unifiée de tous les paramètres,
avec validation, typage fort et chargement depuis les variables d'environnement
ou des valeurs par défaut. Il inclut des sous-modèles pour les différentes
sections de la configuration (authentification, Ollama, Redis, etc.).
"""

import secrets
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

# Importation du gestionnaire de secrets (à adapter si le chemin change).
from src.security.secret_manager import SecretsManager

# Charge les variables d'environnement depuis un fichier .env.
load_dotenv()

# Chemins de base du projet.
BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE_DIR / "configs"


# ---------- Enums utilitaires ----------
class Environment(str, Enum):
    """Environnements d'exécution possibles."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ServiceType(str, Enum):
    """Types de services externes supportés."""
    OLLAMA = "ollama"
    OCR = "ocr"
    ALM = "alm"
    EXCEL = "excel"
    PLAYWRIGHT = "playwright"
    REDIS = "redis"
    DASH = "dash" # Ajouté pour le service Dash


class LogLevel(str, Enum):
    """Niveaux de journalisation standard."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ---------- Sous-modèles Pydantic pour les sections de configuration ----------
class AuthConfig(BaseModel):
    """Configuration spécifique au service d'authentification."""
    jwt_secret_key: str = Field(default_factory=lambda: SecretsManager.generate_secret_key(),
                                description="Clé secrète pour la signature des jetons JWT.")
    jwt_algorithm: str = Field("HS256", description="Algorithme de signature JWT.")
    jwt_expiration_minutes: int = Field(60, description="Durée de validité des jetons JWT en minutes.")
    database_url: str = Field("sqlite:///./auth.db", description="URL de connexion à la base de données d'authentification.")
    host: str = Field("0.0.0.0", description="Hôte sur lequel le service d'authentification écoute.")
    port: int = Field(8005, description="Port sur lequel le service d'authentification écoute.")


class OllamaConfig(BaseModel):
    """Configuration pour l'intégration avec Ollama."""
    host: str = Field("localhost", description="Hôte du serveur Ollama.")
    port: int = Field(11434, description="Port du serveur Ollama.")
    timeout: int = Field(180, description="Délai d'attente pour les requêtes Ollama en secondes.")
    keep_alive: str = Field("30m", description="Durée de maintien des modèles en mémoire par Ollama.")

    @property
    def url(self) -> str:
        """Retourne l'URL complète du serveur Ollama."""
        return f"http://{self.host}:{self.port}"


class ModelConfig(BaseModel):
    """Configuration pour un modèle de langage spécifique (LLM)."""
    name: str = Field(..., description="Nom du modèle (ex: 'qwen3-sfd-analyzer').")
    base_model: str = Field(..., description="Nom du modèle de base dans Ollama (ex: 'qwen3:32b-q4_K_M').")
    role: str = Field(..., description="Rôle ou fonction du modèle dans l'application.")
    api_mode: str = Field("generate", description="Mode d'API Ollama à utiliser ('generate' ou 'chat').")
    timeout: int = Field(120, description="Délai d'attente pour les requêtes à ce modèle.")
    max_tokens: int = Field(4096, description="Nombre maximal de jetons à générer par le modèle.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Contrôle la créativité de la réponse.")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Contrôle la diversité de la réponse.")
    top_k: int = Field(default=40, ge=1, description="Limite le nombre de jetons considérés pour la prédiction.")
    repeat_penalty: float = Field(default=1.1, ge=0.0, description="Pénalise la répétition de jetons.")
    num_ctx: int = Field(8192, description="Taille du contexte en jetons que le modèle peut gérer.")
    seed: Optional[int] = Field(None, description="Graine pour la reproductibilité des générations.")
    stop: List[str] = Field(default_factory=list, description="Liste de séquences d'arrêt pour la génération.")


class ServiceConfig(BaseModel):
    """Configuration pour un microservice externe."""
    name: str = Field(..., description="Nom du service.")
    type: ServiceType = Field(..., description="Type du service (ex: OCR, ALM).")
    host: str = Field("localhost", description="Hôte du service.")
    port: int = Field(..., description="Port du service.")
    timeout: int = Field(60, description="Délai d'attente pour les requêtes au service en secondes.")
    health_check_path: str = Field("/health", description="Chemin de l'endpoint de vérification de santé du service.")
    max_retries: int = Field(3, description="Nombre maximal de tentatives en cas d'échec de requête.")
    enabled: bool = Field(True, description="Indique si le service est activé.")

    @property
    def url(self) -> str:
        """Retourne l'URL complète du service."""
        return f"http://{self.host}:{self.port}"


class RedisConfig(BaseModel):
    """Configuration pour la connexion Redis."""
    host: str = Field("localhost", description="Hôte du serveur Redis.")
    port: int = Field(6379, description="Port du serveur Redis.")
    db: int = Field(0, description="Numéro de la base de données Redis.")
    password: Optional[str] = Field(None, description="Mot de passe pour la connexion Redis.")
    ssl: bool = Field(False, description="Utiliser SSL/TLS pour la connexion Redis.")
    encrypt_values: bool = Field(True, description="Chiffrer les valeurs stockées dans Redis.")
    ttl_sfd_analysis: int = Field(86400, description="TTL pour les résultats d'analyse SFD en secondes.")
    ttl_generated_tests: int = Field(43200, description="TTL pour les tests générés en secondes.")
    ttl_ocr_results: int = Field(604800, description="TTL pour les résultats OCR en secondes.")
    ttl_model_responses: int = Field(3600, description="TTL pour les réponses des modèles en secondes.")

    @property
    def url(self) -> str:
        """Retourne l'URL de connexion Redis complète."""
        scheme = "rediss" if self.ssl else "redis"
        auth = f":{self.password}@" if self.password else ""
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"


class PipelineConfig(BaseModel):
    """Configuration pour le pipeline d'orchestration des tâches."""
    max_parallel_tests: int = Field(5, description="Nombre maximal de tests à exécuter en parallèle.")
    max_parallel_scenarios: int = Field(10, description="Nombre maximal de scénarios à analyser en parallèle.")
    timeout_sfd_extraction: int = Field(300, description="Délai d'attente pour l'extraction SFD en secondes.")
    timeout_scenario_analysis: int = Field(600, description="Délai d'attente pour l'analyse de scénario en secondes.")
    timeout_test_generation: int = Field(180, description="Délai d'attente pour la génération de tests en secondes.")
    timeout_test_execution: int = Field(900, description="Délai d'attente pour l'exécution de tests en secondes.")
    retry_max_attempts: int = Field(3, description="Nombre maximal de tentatives pour les opérations du pipeline.")
    retry_backoff_factor: float = Field(2.0, description="Facteur de backoff exponentiel pour les retries.")
    retry_max_delay: int = Field(30, description="Délai maximal entre les tentatives de retry en secondes.")
    fallback_enabled: bool = Field(True, description="Activer les stratégies de fallback en cas d'échec.")
    fallback_use_templates: bool = Field(True, description="Utiliser des templates pour le fallback (si applicable).")
    fallback_template_quality: str = Field("basic", description="Qualité des templates de fallback ('basic', 'advanced').")


class LoggingConfig(BaseModel):
    """Configuration pour le système de journalisation (logging)."""
    level: LogLevel = Field(LogLevel.INFO, description="Niveau de journalisation minimal.")
    format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Format des messages de log.")
    file: Optional[Path] = Field(None, description="Chemin du fichier de log. Si None, log sur la console.")
    max_size_mb: int = Field(100, description="Taille maximale du fichier de log avant rotation en Mo.")
    backup_count: int = Field(5, description="Nombre de fichiers de log de sauvegarde à conserver.")

    @field_validator("file", mode="before")
    @classmethod
    def validate_file_path(cls, v: Any) -> Optional[Path]:
        """Valide et convertit le chemin du fichier de log en objet Path."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v)
        if isinstance(v, Path):
            return v
        raise ValueError("Le chemin du fichier de log doit être une chaîne ou un objet Path.")


class SecurityConfig(BaseModel):
    """Configuration des paramètres de sécurité de l'application."""
    enable_auth: bool = Field(False, description="Activer le système d'authentification.")
    jwt_secret_key: Optional[str] = Field(None, description="Clé secrète pour JWT (requise si auth activée).")
    jwt_algorithm: str = Field("HS256", description="Algorithme de signature JWT.")
    jwt_expiration_minutes: int = Field(1440, description="Durée de validité des jetons JWT en minutes.")
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"], description="Liste des origines CORS autorisées.")
    rate_limit_enabled: bool = Field(True, description="Activer la limitation de débit pour les API.")
    rate_limit_requests: int = Field(100, description="Nombre maximal de requêtes autorisées par fenêtre.")
    rate_limit_window_seconds: int = Field(60, description="Fenêtre de temps pour la limitation de débit en secondes.")

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: Optional[str], info: field_validator) -> Optional[str]:
        """Valide que la clé secrète JWT est présente si l'authentification est activée."""
        if info.data.get("enable_auth") and not v:
            raise ValueError("La clé secrète JWT est requise lorsque l'authentification est activée.")
        return v


# ---------- Paramètres Principaux (Settings) ----------
class Settings(BaseSettings):
    """Classe de configuration globale de l'application Altiora.

    Cette classe agrège toutes les sous-configurations et gère le chargement
    des variables d'environnement. Elle est conçue comme un singleton.
    """
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT", description="Environnement d'exécution de l'application.")
    debug: bool = Field(default=False, env="DEBUG", description="Active le mode débogage.")

    base_dir: Path = Field(default=BASE_DIR, description="Répertoire de base du projet.")
    data_dir: Path = Field(default=BASE_DIR / "data", description="Répertoire pour les données de l'application.")
    models_dir: Path = Field(default=BASE_DIR / "models", description="Répertoire pour les modèles d'IA.")
    logs_dir: Path = Field(default=BASE_DIR / "logs", description="Répertoire pour les fichiers de log.")
    reports_dir: Path = Field(default=BASE_DIR / "reports", description="Répertoire pour les rapports générés.")
    temp_dir: Path = Field(default=BASE_DIR / "temp", description="Répertoire pour les fichiers temporaires.")
    model_memory_limit_gb: float = Field(default=8.0, env="MODEL_MEMORY_LIMIT_GB", description="Limite de mémoire en Go pour les modèles d'IA.")

    ollama: OllamaConfig = Field(default_factory=OllamaConfig, description="Configuration pour Ollama.")
    redis: RedisConfig = Field(default_factory=RedisConfig, description="Configuration pour Redis.")
    auth: AuthConfig = Field(default_factory=AuthConfig, description="Configuration pour le service d'authentification.")
    models: Dict[str, ModelConfig] = Field(default_factory=dict, description="Dictionnaire des configurations de modèles LLM.")
    services: Dict[ServiceType, ServiceConfig] = Field(default_factory=dict, description="Dictionnaire des configurations de microservices.")
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig, description="Configuration pour le pipeline d'orchestration.")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="Configuration pour le logging.")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Configuration des paramètres de sécurité.")
    secrets: SecretsManager = Field(default_factory=lambda: SecretsManager(BASE_DIR / "secrets"), description="Gestionnaire des secrets de l'application.")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False, # Les noms de variables d'environnement ne sont pas sensibles à la casse.
    }

    def _create_directories(self):
        """Crée les répertoires nécessaires si ils n'existent pas."""
        for attr in ("data_dir", "models_dir", "logs_dir", "reports_dir", "temp_dir"):
            getattr(self, attr).mkdir(parents=True, exist_ok=True)

    def validate_config(self) -> List[str]:
        """Effectue des validations métier supplémentaires sur la configuration."

        Returns:
            Une liste de chaînes de caractères décrivant les erreurs de validation.
        """
        errors = []
        # Exemple de validation : s'assurer que les modèles critiques sont configurés.
        for required_model_name in ["qwen3", "starcoder2"]:
            if required_model_name not in self.models:
                errors.append(f"Le modèle requis '{required_model_name}' n'est pas configuré dans `settings.models`.")
        
        # Exemple de validation : s'assurer que les services critiques sont configurés.
        for required_service_type in [ServiceType.OCR, ServiceType.ALM, ServiceType.PLAYWRIGHT]:
            if required_service_type not in self.services:
                errors.append(f"Le service critique '{required_service_type.value}' n'est pas configuré dans `settings.services`.")

        # Validation spécifique à l'environnement de production.
        if self.environment == Environment.PRODUCTION:
            if not self.redis.password:
                errors.append("Un mot de passe Redis est requis en environnement de production.")
            if self.security.enable_auth and not self.security.jwt_secret_key:
                errors.append("Une clé secrète JWT est requise en production lorsque l'authentification est activée.")
        return errors


# ---------- Singleton ----------
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Retourne l'instance singleton de la configuration globale de l'application."

    Cette fonction garantit qu'une seule instance de `Settings` est créée et utilisée
    dans toute l'application. Elle effectue également une validation initiale.

    Returns:
        L'instance unique de `Settings`.

    Raises:
        RuntimeError: Si la configuration est invalide lors du premier chargement.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
        # Crée les répertoires nécessaires au premier chargement.
        _settings_instance._create_directories()
        errs = _settings_instance.validate_config()
        if errs:
            raise RuntimeError("Erreurs de configuration détectées:\n" + "\n".join(errs))
    return _settings_instance


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("\n--- Chargement de la configuration ---")
    try:
        # Pour la démonstration, on peut simuler des variables d'environnement.
        # os.environ["ENVIRONMENT"] = "production"
        # os.environ["REDIS_PASSWORD"] = "mysecretredispass"
        # os.environ["SECURITY__ENABLE_AUTH"] = "true"
        # os.environ["SECURITY__JWT_SECRET_KEY"] = SecretsManager.generate_secret_key()

        settings = get_settings()
        print("✅ Configuration chargée avec succès.")
        print(settings.model_dump_json(indent=2))

        print("\n--- Accès aux paramètres spécifiques ---")
        print(f"Environnement : {settings.environment}")
        print(f"URL Ollama : {settings.ollama.url}")
        print(f"Port du service Auth : {settings.auth.port}")
        print(f"Chemin des logs : {settings.logs_dir}")

        # Exemple de modification (pour le test, ne pas faire en prod).
        settings.debug = True
        print(f"Mode debug après modification : {settings.debug}")

    except RuntimeError as e:
        logging.error(f"❌ Erreur de configuration au démarrage : {e}")
    except Exception as e:
        logging.error(f"❌ Erreur inattendue : {e}")