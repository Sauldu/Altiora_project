# src/security/secret_manager.py
"""Gestionnaire de secrets ultra-sécurisé pour l'application Altiora.

Ce module fournit une classe `SecretsManager` qui gère l'accès aux secrets
de l'application de manière sécurisée. Il charge les secrets uniquement
depuis les variables d'environnement, effectue une validation stricte au
démarrage et peut générer des clés aléatoires pour faciliter la configuration.
"""

import os
import secrets
import logging
from typing import Optional, Dict
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

# Charge les variables d'environnement depuis un fichier .env si présent.
# Cela doit être fait au début de l'exécution de l'application.
load_dotenv()


class SecretsManager:
    """Gestionnaire singleton sécurisé pour tous les secrets de l'application.

    Il est recommandé d'accéder aux secrets via cette classe pour garantir
    une gestion cohérente et sécurisée.
    """

    # Liste des secrets requis et leur description pour la documentation.
    REQUIRED_SECRETS: Dict[str, str] = {
        "JWT_SECRET_KEY": "Clé secrète pour la signature des jetons JWT (minimum 32 caractères).",
        "ENCRYPTION_KEY": "Clé de chiffrement Fernet (doit être une clé Fernet valide encodée en base64 URL-safe).",
        "OLLAMA_API_KEY": "Clé API pour l'accès à Ollama (optionnelle, si Ollama nécessite une authentification).",
        "OPENAI_API_KEY": "Clé API OpenAI pour les services de modération ou autres (optionnelle).",
        "AZURE_CONTENT_SAFETY_KEY": "Clé Azure Content Safety pour la modération de contenu (optionnelle).",
    }

    def __init__(self, secrets_dir: Path = Path("secrets")):
        """Initialise le gestionnaire de secrets."

        Args:
            secrets_dir: Le répertoire où les secrets pourraient être stockés (non utilisé directement pour le chargement).
        """
        self.secrets_dir = secrets_dir
        self.secrets_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_secret(cls, key: str, required: bool = True) -> str:
        """Récupère un secret depuis les variables d'environnement."

        Args:
            key: Le nom de la variable d'environnement contenant le secret.
            required: Si True, lève une `ValueError` si le secret est manquant.

        Returns:
            La valeur du secret sous forme de chaîne de caractères.

        Raises:
            ValueError: Si le secret est requis mais non trouvé.
        """
        value = os.getenv(key)
        if required and not value:
            raise ValueError(f"Secret manquant : `{key}`. Description : {cls.REQUIRED_SECRETS.get(key, 'N/A')}")
        return value or ""

    @classmethod
    def validate_secrets(cls) -> None:
        """Effectue une validation stricte de tous les secrets requis au démarrage de l'application."

        Cette méthode vérifie la présence et le format des secrets critiques.

        Raises:
            RuntimeError: Si des erreurs de validation sont trouvées, avec une liste détaillée.
        """
        errors: List[str] = []

        # Validation de la clé secrète JWT.
        try:
            jwt_key = cls.get_secret("JWT_SECRET_KEY")
            if jwt_key and len(jwt_key) < 32:
                errors.append("JWT_SECRET_KEY doit contenir au moins 32 caractères pour être sécurisé.")
        except ValueError as e:
            errors.append(str(e))

        # Validation du format de la clé de chiffrement Fernet.
        try:
            encryption_key = cls.get_secret("ENCRYPTION_KEY")
            if encryption_key:
                try:
                    Fernet(encryption_key.encode())
                except Exception:
                    errors.append("ENCRYPTION_KEY est invalide. Elle doit être une clé Fernet valide (32 octets encodés en base64 URL-safe).")
        except ValueError as e:
            errors.append(str(e))

        if errors:
            raise RuntimeError("Erreurs de validation des secrets détectées :\n" + "\n".join(errors))
        logger.info("✅ Tous les secrets critiques ont été validés avec succès.")

    @classmethod
    def generate_secret_key(cls, length: int = 64) -> str:
        """Génère une clé secrète aléatoire et sécurisée."

        Args:
            length: La longueur du secret en octets (la chaîne résultante sera plus longue).

        Returns:
            Une chaîne de caractères sécurisée.
        """
        return secrets.token_urlsafe(length)

    @classmethod
    def generate_fernet_key(cls) -> str:
        """Génère une clé Fernet valide (32 octets encodés en base64 URL-safe)."

        Returns:
            Une chaîne de caractères représentant une clé Fernet.
        """
        return Fernet.generate_key().decode()

    @classmethod
    def generate_missing_secrets_and_prompt(cls) -> None:
        """Génère automatiquement les secrets manquants et invite l'utilisateur à les ajouter à .env."

        Cette méthode est utile pour la configuration initiale ou le développement.
        Elle ne modifie pas directement le fichier .env, mais affiche les secrets à ajouter.
        """
        logger.info("\n--- Génération des secrets manquants ---")
        generated_count = 0
        for key, description in cls.REQUIRED_SECRETS.items():
            if not os.getenv(key):
                if key == "ENCRYPTION_KEY":
                    value = cls.generate_fernet_key()
                else:
                    value = cls.generate_secret_key()
                logger.info(f"⚠️  Secret généré pour `{key}` : `{value}`")
                logger.info(f"   Description : {description}")
                logger.info(f"   Ajoutez cette ligne à votre fichier `.env` :\n   {key}={value}")
                generated_count += 1
        
        if generated_count > 0:
            logger.info("\n🔒 N'oubliez pas d'ajouter ces lignes à votre fichier `.env` et de le garder hors de votre dépôt Git !")
        else:
            logger.info("✅ Aucun secret manquant à générer. Tous les secrets requis semblent être définis.")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("\n--- Démonstration du SecretsManager ---")

    # Nettoie les variables d'environnement pour une démonstration propre.
    for key in SecretsManager.REQUIRED_SECRETS.keys():
        if key in os.environ:
            del os.environ[key]

    # 1. Génération et affichage des secrets manquants.
    SecretsManager.generate_missing_secrets_and_prompt()

    # 2. Simule la définition de secrets dans l'environnement.
    os.environ["JWT_SECRET_KEY"] = SecretsManager.generate_secret_key()
    os.environ["ENCRYPTION_KEY"] = SecretsManager.generate_fernet_key()
    os.environ["OLLAMA_API_KEY"] = "sk-ollama123"

    print("\n--- Tentative de validation des secrets ---")
    try:
        SecretsManager.validate_secrets()
        print("✅ Validation des secrets réussie après définition.")
    except RuntimeError as e:
        logging.error(f"❌ Erreur de validation des secrets : {e}")

    print("\n--- Récupération d'un secret ---")
    try:
        jwt_secret = SecretsManager.get_secret("JWT_SECRET_KEY")
        print(f"Secret JWT récupéré (partiel) : {jwt_secret[:10]}...")
    except ValueError as e:
        logging.error(f"❌ Erreur lors de la récupération du secret : {e}")

    print("Démonstration du SecretsManager terminée.")
