# src/monitoring/structured_logger.py
"""Module pour la journalisation structurée (JSON) dans l'application Altiora.

Ce module fournit une implémentation d'un logger qui émet des messages au format JSON.
Cela facilite l'analyse et le traitement des logs par des outils externes (ELK Stack,
Splunk, etc.) et permet d'inclure des métadonnées riches avec chaque message.
"""

import logging
import sys
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger  # Nécessite `pip install python-json-logger`


class StructuredLogger:
    """Logger centralisé qui émet des messages au format JSON."

    Utilisation:
    ```python
    from src.monitoring.structured_logger import logger
    logger.info("sfd_processed", extra={"sfd_id": "123", "duration_ms": 450, "model": "qwen3"})
    ```
    """

    def __init__(self, name: str = "altiora") -> None:
        """Initialise le logger structuré."

        Args:
            name: Le nom du logger (par défaut 'altiora').
        """
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.INFO) # Niveau de log par défaut.

        # Configure le handler pour écrire sur la sortie standard (stdout).
        handler = logging.StreamHandler(sys.stdout)
        
        # Configure le formateur JSON pour les messages de log.
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger_name",
                "message": "msg",
            }
        )
        handler.setFormatter(formatter)
        
        # Ajoute le handler au logger et empêche la propagation pour éviter les doublons.
        self._logger.addHandler(handler)
        self._logger.propagate = False

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Enregistre un message d'information."

        Args:
            message: Le message principal du log.
            extra: Un dictionnaire de données supplémentaires à inclure dans le log JSON.
        """
        self._logger.info(message, extra=extra or {})

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Enregistre un message d'erreur."

        Args:
            message: Le message principal du log.
            extra: Un dictionnaire de données supplémentaires à inclure dans le log JSON.
        """
        self._logger.error(message, extra=extra or {})

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Enregistre un message d'avertissement."

        Args:
            message: Le message principal du log.
            extra: Un dictionnaire de données supplémentaires à inclure dans le log JSON.
        """
        self._logger.warning(message, extra=extra or {})

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Enregistre un message de débogage."

        Args:
            message: Le message principal du log.
            extra: Un dictionnaire de données supplémentaires à inclure dans le log JSON.
        """
        self._logger.debug(message, extra=extra or {})

    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Enregistre un message critique."

        Args:
            message: Le message principal du log.
            extra: Un dictionnaire de données supplémentaires à inclure dans le log JSON.
        """
        self._logger.critical(message, extra=extra or {})


# Instance singleton du logger pour une utilisation facile dans toute l'application.
logger = StructuredLogger()


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("\n--- Démonstration du StructuredLogger ---")

    # Exemple de message d'information avec des métadonnées.
    logger.info(
        "sfd_processed",
        extra={
            "sfd_id": "SFD-2023-001",
            "duration_ms": 1250,
            "model_used": "qwen3-sfd-analyzer",
            "scenarios_extracted": 15
        }
    )

    # Exemple de message d'erreur.
    try:
        raise ValueError("Une erreur inattendue est survenue.")
    except ValueError as e:
        logger.error(
            "processing_error",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "component": "orchestrator"
            }
        )

    # Exemple de message d'avertissement.
    logger.warning(
        "cache_miss",
        extra={"key": "user_profile_123", "reason": "expired"}
    )

    print("\nLes messages ci-dessus devraient être affichés au format JSON.")