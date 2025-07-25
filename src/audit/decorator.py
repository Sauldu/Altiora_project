# src/audit/decorator.py
"""Décorateur pour l'audit des fonctions asynchrones.

Ce module fournit un décorateur `@audit` qui permet d'enregistrer
automatiquement des événements d'audit lorsqu'une fonction est appelée.
Il capture le début de l'exécution, l'acteur (utilisateur), l'action,
et gère les succès ou les échecs de la fonction décorée.
"""

import datetime
import functools
import logging

from pathlib import Path
from src.audit.writer import AsyncAuditWriter
from src.audit.models import AuditEvent

logger = logging.getLogger(__name__)

# Initialise un writer d'audit asynchrone pour écrire les logs dans le répertoire spécifié.
writer = AsyncAuditWriter(Path("logs/audit"))


def audit(action: str):
    """Décorateur pour auditer l'exécution d'une fonction asynchrone.

    Args:
        action: Une chaîne de caractères décrivant l'action auditée (ex: "sfd_upload", "test_gen").

    Returns:
        Un décorateur qui, lorsqu'il est appliqué à une fonction asynchrone,
        enregistre un événement d'audit avant et après son exécution.
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            start_time = datetime.datetime.utcnow() # Horodatage du début de l'action.
            actor = kwargs.get("user_id", "system") # Tente de récupérer l'ID utilisateur, sinon 'system'.
            
            try:
                result = await fn(*args, **kwargs)
                # Enregistre un événement de succès.
                writer.log(AuditEvent(
                    ts=start_time,
                    actor=actor,
                    action=action,
                    meta={"status": "success", "duration_ms": (datetime.datetime.utcnow() - start_time).total_seconds() * 1000}
                ))
                logger.info(f"Audit: Action '{action}' par '{actor}' réussie.")
                return result
            except Exception as exc:
                # Enregistre un événement d'échec avec les détails de l'erreur.
                writer.log(AuditEvent(
                    ts=start_time,
                    actor=actor,
                    action=action,
                    meta={
                        "status": "failure",
                        "error": str(exc),
                        "duration_ms": (datetime.datetime.utcnow() - start_time).total_seconds() * 1000
                    }
                ))
                logger.error(f"Audit: Action '{action}' par '{actor}' a échoué : {exc}")
                raise # Re-lève l'exception pour ne pas masquer l'erreur originale.

        return wrapper

    return decorator


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Démarre le writer d'audit en arrière-plan.
        await writer.start()

        @audit("process_data")
        async def process_data_success(user_id: str, data: str):
            print(f"Traitement des données pour {user_id}: {data}")
            await asyncio.sleep(0.1)
            return {"processed": True, "data": data.upper()}

        @audit("process_data")
        async def process_data_failure(user_id: str, data: str):
            print(f"Tentative de traitement des données pour {user_id}: {data}")
            await asyncio.sleep(0.1)
            raise ValueError("Erreur de traitement simulée")

        print("\n--- Démonstration de l'audit (succès) ---")
        try:
            result = await process_data_success(user_id="alice", data="hello world")
            print(f"Résultat : {result}")
        except Exception as e:
            print(f"Erreur inattendue : {e}")

        print("\n--- Démonstration de l'audit (échec) ---")
        try:
            await process_data_failure(user_id="bob", data="bad data")
        except Exception as e:
            print(f"Erreur capturée : {e}")

        # Attendre que le writer ait eu le temps de flusher.
        print("\nAttente du flush des logs d'audit...")
        await asyncio.sleep(2) # Donne un peu de temps au writer.
        await writer.stop() # Arrête le writer proprement.
        print("Démonstration terminée. Vérifiez le répertoire logs/audit.")

    import asyncio
    asyncio.run(demo())