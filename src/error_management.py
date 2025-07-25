# src/error_management.py
"""Architecture centralisée de gestion des erreurs, de retry et de disjoncteur pour Altiora.

Ce module fournit un ensemble complet d'outils pour gérer les erreurs de manière
robuste et résiliente dans une application asynchrone. Il inclut des exceptions
personnalisées, un gestionnaire de retry, un disjoncteur (circuit breaker),
un logger d'erreurs chiffré, et un gestionnaire de contexte pour la propagation
des erreurs.
"""

import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Callable, Optional, Type

import aiofiles
from cryptography.fernet import Fernet  # Bibliothèque de chiffrement symétrique.
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Configuration des erreurs
# ------------------------------------------------------------------
ERROR_CONFIG = {
    "max_retries": int(os.getenv("MAX_RETRIES", 3)),
    "backoff_factor": float(os.getenv("BACKOFF_FACTOR", 2.0)),
    "circuit_breaker_timeout": int(os.getenv("CB_TIMEOUT", 60)), # Temps en secondes pendant lequel le disjoncteur reste ouvert.
    "log_file": Path(os.getenv("ERROR_LOG", "logs/errors.jsonl")), # Chemin du fichier de log des erreurs.
    "encryption_key": os.getenv("LOGS_ENCRYPTION_KEY"), # Clé pour chiffrer les logs d'erreurs.
}


# ------------------------------------------------------------------
# Exceptions personnalisées
# ------------------------------------------------------------------
class AltioraError(Exception):
    """Exception de base pour toutes les erreurs spécifiques à Altiora."""
    pass


class ServiceError(AltioraError):
    """Exception levée lorsqu'un service externe rencontre une erreur."

    Utilisée pour les problèmes de communication ou de disponibilité des microservices.
    """
    pass


class ValidationError(AltioraError):
    """Exception levée lorsqu'une validation métier échoue."

    Indique que les données ne sont pas conformes aux règles de l'application.
    """
    pass


# ------------------------------------------------------------------
# Assistant de chiffrement
# ------------------------------------------------------------------
class CryptoHelper:
    """Aide au chiffrement/déchiffrement de dictionnaires en utilisant Fernet."""

    def __init__(self, key: Optional[str] = None):
        """Initialise l'aide au chiffrement."

        Args:
            key: La clé Fernet encodée en base64 URL-safe. Si None, une clé est générée.
        """
        if key:
            self.key = key
        else:
            self.key = Fernet.generate_key().decode() # Génère une clé si non fournie.
            logger.warning("Aucune clé de chiffrement fournie pour les logs. Génération d'une clé temporaire. NE PAS UTILISER EN PRODUCTION.")
        self.fernet = Fernet(self.key.encode() if isinstance(self.key, str) else self.key)

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Chiffre un dictionnaire en JSON puis avec Fernet."

        Args:
            data: Le dictionnaire à chiffrer.

        Returns:
            La chaîne chiffrée.
        """
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode('utf-8')
        return self.fernet.encrypt(payload).decode('utf-8')

    def decrypt_dict(self, token: str) -> Dict[str, Any]:
        """Déchiffre une chaîne chiffrée en un dictionnaire."

        Args:
            token: La chaîne chiffrée.

        Returns:
            Le dictionnaire déchiffré.
        """
        return json.loads(self.fernet.decrypt(token.encode('utf-8')).decode('utf-8'))


# Initialise l'aide au chiffrement avec la clé de configuration.
crypto = CryptoHelper(ERROR_CONFIG["encryption_key"])


# ------------------------------------------------------------------
# Gestionnaire de Retry
# ------------------------------------------------------------------
class RetryHandler:
    """Fournit un décorateur pour appliquer des stratégies de nouvelle tentative aux fonctions asynchrones."""

    @staticmethod
    def with_retry(
            max_attempts: int = ERROR_CONFIG["max_retries"],
            exceptions: tuple[Type[Exception], ...] = (Exception,),
    ) -> Callable:
        """Décorateur pour retenter l'exécution d'une fonction asynchrone en cas d'échec."

        Args:
            max_attempts: Le nombre maximal de tentatives d'exécution.
            exceptions: Un tuple d'exceptions pour lesquelles la fonction doit être retentée.

        Returns:
            Un décorateur qui peut être appliqué à une fonction asynchrone.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            @retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(
                    multiplier=ERROR_CONFIG["backoff_factor"], max=30
                ),
                retry=retry_if_exception_type(exceptions), # Retente si l'exception est du type spécifié.
                reraise=True # Rélève l'exception après toutes les tentatives.
            )
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.warning("Retry pour %s: %s", func.__name__, e)
                    raise

            return wrapper

        return decorator


# ------------------------------------------------------------------
# Disjoncteur (Circuit Breaker)
# ------------------------------------------------------------------
class CircuitBreaker:
    """Implémente le pattern Circuit Breaker pour protéger contre les cascades d'erreurs."""

    def __init__(
            self,
            failure_threshold: int = 5,
            timeout: int = ERROR_CONFIG["circuit_breaker_timeout"],
    ):
        """Initialise le disjoncteur."

        Args:
            failure_threshold: Nombre d'échecs consécutifs avant que le disjoncteur ne s'ouvre.
            timeout: Durée en secondes pendant laquelle le disjoncteur reste ouvert.
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._failures: Dict[str, int] = {} # Compteur d'échecs par service.
        self._last_failure: Dict[str, datetime] = {} # Horodatage du dernier échec par service.
        self._is_open: Dict[str, bool] = {} # État du disjoncteur par service (ouvert/fermé).

    async def call_with_protection(
            self,
            service_name: str,
            coro: Callable,
            *args,
            **kwargs,
    ) -> Any:
        """Appelle une coroutine avec la protection du disjoncteur."

        Args:
            service_name: Le nom du service à protéger.
            coro: La coroutine à exécuter.
            *args, **kwargs: Arguments à passer à la coroutine.

        Returns:
            Le résultat de la coroutine.

        Raises:
            ServiceError: Si le disjoncteur est ouvert pour ce service.
            Exception: Toute exception levée par la coroutine.
        """
        # Vérifie si le disjoncteur est ouvert.
        if self._is_open.get(service_name, False):
            # Si ouvert, vérifie si le timeout de récupération est passé.
            if (datetime.now() - self._last_failure.get(service_name, datetime.min)) < timedelta(seconds=self.timeout):
                raise ServiceError(f"Disjoncteur ouvert pour le service `{service_name}`. Opération bloquée.")
            # Si le timeout est passé, tente de réinitialiser le disjoncteur (état "semi-ouvert").
            self.reset(service_name)

        try:
            result = await coro(*args, **kwargs)
            self.reset(service_name) # Réinitialise le disjoncteur en cas de succès.
            return result
        except Exception:
            self._record_failure(service_name) # Enregistre l'échec.
            if self._failures.get(service_name, 0) >= self.failure_threshold:
                self._is_open[service_name] = True
                self._last_failure[service_name] = datetime.now()
                logger.error(f"Disjoncteur ouvert pour le service `{service_name}` après {self.failure_threshold} échecs.")
            raise # Rélève l'exception originale.

    def reset(self, service_name: str) -> None:
        """Réinitialise l'état du disjoncteur pour un service donné."""
        self._failures[service_name] = 0
        self._is_open[service_name] = False
        logger.info(f"Disjoncteur réinitialisé pour le service `{service_name}`.")

    def _record_failure(self, service_name: str) -> None:
        """Enregistre un échec pour un service."""
        self._failures[service_name] = self._failures.get(service_name, 0) + 1


# ------------------------------------------------------------------
# Journalisation des Erreurs
# ------------------------------------------------------------------
class ErrorLogger:
    """Gère la journalisation centralisée des erreurs de l'application."""

    def __init__(self, log_file: Path = ERROR_CONFIG["log_file"]) -> None:
        """Initialise le journaliseur d'erreurs."

        Args:
            log_file: Le chemin du fichier où les erreurs seront enregistrées.
        """
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True) # Crée le répertoire si nécessaire.

    async def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Enregistre une erreur dans le fichier de log."

        Args:
            error: L'objet exception à enregistrer.
            context: Un dictionnaire de contexte supplémentaire à inclure dans le log.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {},
            "stack_trace": traceback.format_exc() # Capture la trace complète de la pile.
        }
        try:
            async with aiofiles.open(self.log_file, "a", encoding='utf-8') as f:
                await f.write(crypto.encrypt_dict(entry) + "\n") # Chiffre l'entrée avant de l'écrire.
            logger.error("Erreur logguée : %s", entry["error_message"])
        except (IOError, OSError) as e:
            logger.critical(f"Erreur critique : Impossible d'écrire dans le fichier de log des erreurs {self.log_file}: {e}")


class EncryptedLogger(ErrorLogger):
    """Logger d'erreurs qui chiffre les entrées avant de les écrire sur disque."""
    pass # L'implémentation est déjà dans ErrorLogger avec crypto.


# ------------------------------------------------------------------
# Gestionnaire de Contexte pour les Erreurs
# ------------------------------------------------------------------
class ErrorContext:
    """Gestionnaire de contexte asynchrone pour capturer et logguer les exceptions non gérées."

    Utilisation:
    ```python
    async with ErrorContext("process_sfd", sfd_id="123"):
        # Code potentiellement générateur d'erreurs.
        raise ValueError("Problème lors du parsing.")
    ```
    """
    def __init__(self, operation: str, **kwargs: Any) -> None:
        """Initialise le contexte d'erreur."

        Args:
            operation: Le nom de l'opération en cours (pour le logging).
            **kwargs: Contexte supplémentaire à logguer avec l'erreur.
        """
        self.operation = operation
        self.context = kwargs

    async def __aenter__(self) -> "ErrorContext":
        """Entre dans le bloc `async with`."""
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[Any]) -> bool:
        """Quitte le bloc `async with` et loggue l'exception si elle existe."

        Args:
            exc_type: Le type de l'exception.
            exc_val: L'instance de l'exception.
            exc_tb: La traceback de l'exception.

        Returns:
            True si l'exception a été gérée et ne doit pas être propagée,
            False si l'exception doit être propagée.
        """
        if exc_val:
            # Formate la traceback pour l'inclure dans le log.
            formatted_traceback = "\n".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            logger.error(
                "Exception non gérée dans l'opération '%s'",
                self.operation,
                extra={
                    "context": self.context,
                    "error_type": exc_type.__name__ if exc_type else "UnknownError",
                    "error_message": str(exc_val),
                    "stack_trace": formatted_traceback
                },
            )
            # Ici, vous pouvez ajouter des hooks pour envoyer des alertes à des systèmes de monitoring externes.
            # Exemple: await send_alert_to_sentry(exc_val, self.context)
        return False  # Propagate l'exception pour qu'elle soit gérée plus haut.


# ------------------------------------------------------------------
# Instances globales (singletons)
# ------------------------------------------------------------------
error_logger = EncryptedLogger() # Instance du logger d'erreurs chiffré.
retry_handler = RetryHandler() # Instance du gestionnaire de retry.
circuit_breaker = CircuitBreaker() # Instance du disjoncteur.


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import random

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Définir une clé de chiffrement pour la démo.
    os.environ["LOGS_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

    # --- Démonstration du RetryHandler ---
    print("\n--- Démonstration du RetryHandler ---")
    attempt_count = 0

    @retry_handler.with_retry(max_attempts=3, exceptions=(ValueError,))
    async def flaky_operation_retry(succeed_on_attempt: int):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < succeed_on_attempt:
            logger.info(f"Flaky operation échoue (tentative {attempt_count})...")
            raise ValueError("Échec temporaire")
        logger.info(f"Flaky operation réussie à la tentative {attempt_count} !")
        return "Succès"

    async def run_retry_demo():
        nonlocal attempt_count
        attempt_count = 0
        try:
            result = await flaky_operation_retry(2) # Réussit à la 2ème tentative.
            print(f"Résultat final du retry : {result}")
        except Exception as e:
            print(f"Échec final du retry : {e}")

        attempt_count = 0
        try:
            result = await flaky_operation_retry(4) # Échoue après 3 tentatives.
            print(f"Résultat final du retry : {result}")
        except Exception as e:
            print(f"Échec final du retry (attendu) : {e}")

    asyncio.run(run_retry_demo())

    # --- Démonstration du CircuitBreaker ---
    print("\n--- Démonstration du CircuitBreaker ---")
    service_name = "ExternalAPI"
    call_count = 0

    # Réinitialise le disjoncteur pour la démo.
    circuit_breaker.reset(service_name)

    async def unreliable_service_call():
        nonlocal call_count
        call_count += 1
        if call_count % 3 != 0: # Échoue 2 fois sur 3.
            logger.info(f"Appel au service {service_name} échoue (appel {call_count})...")
            raise ServiceError("Erreur de service externe simulée")
        logger.info(f"Appel au service {service_name} réussi (appel {call_count}) !")
        return "Données reçues"

    async def run_circuit_breaker_demo():
        nonlocal call_count
        call_count = 0
        circuit_breaker.reset(service_name) # S'assure que le disjoncteur est fermé au début.

        for i in range(10):
            print(f"\n--- Itération {i+1} ---")
            try:
                result = await circuit_breaker.call_with_protection(service_name, unreliable_service_call)
                print(f"Résultat : {result}")
            except ServiceError as e:
                print(f"Erreur de service : {e}")
            except Exception as e:
                print(f"Autre erreur : {e}")
            await asyncio.sleep(0.5) # Petite pause entre les appels.

        print("\n--- Tentative après timeout de récupération ---")
        await asyncio.sleep(ERROR_CONFIG["circuit_breaker_timeout"] + 1) # Attend que le disjoncteur se referme.
        try:
            result = await circuit_breaker.call_with_protection(service_name, unreliable_service_call)
            print(f"Résultat après récupération : {result}")
        except Exception as e:
            print(f"Échec après récupération : {e}")

    asyncio.run(run_circuit_breaker_demo())

    # --- Démonstration de ErrorLogger et ErrorContext ---
    print("\n--- Démonstration de ErrorLogger et ErrorContext ---")
    async def demo_error_logging():
        try:
            async with ErrorContext("complex_operation", user_id="test_user", data_id="xyz"):
                logger.info("Début de l'opération complexe.")
                if random.random() < 0.7: # Simule une erreur fréquente.
                    raise ValueError("Erreur simulée lors du traitement des données.")
                logger.info("Opération complexe terminée.")
        except Exception as e:
            print(f"Exception capturée au niveau supérieur : {e}")

    asyncio.run(demo_error_logging())
    print(f"Vérifiez le fichier {ERROR_CONFIG["log_file"]} pour les erreurs logguées (chiffrées)."
          f" Pour les déchiffrer, utilisez `crypto.decrypt_dict()`.")

    # Nettoyage de la variable d'environnement.
    del os.environ["LOGS_ENCRYPTION_KEY"]