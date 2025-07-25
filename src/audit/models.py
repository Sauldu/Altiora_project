# src/audit/models.py
"""Modèles de données pour les événements d'audit.

Ce module définit la structure des événements d'audit qui sont enregistrés
par le système. Il utilise `dataclasses` pour une définition claire et concise
des champs de chaque événement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Dict, Any, Optional


@dataclass(slots=True)
class AuditEvent:
    """Représente un événement d'audit enregistré dans le système.

    Attributes:
        ts: Horodatage de l'événement (UTC).
        actor: L'identifiant de l'entité qui a initié l'action (ex: ID utilisateur, 'system').
        action: Le type d'action effectuée (ex: 'sfd_upload', 'test_gen', 'admin_command', 'pii_detected').
        resource: L'identifiant de la ressource affectée par l'action (optionnel).
        meta: Un dictionnaire de métadonnées supplémentaires spécifiques à l'événement (optionnel).
    """
    ts: datetime
    actor: str
    action: Literal["sfd_upload", "test_gen", "admin_command", "pii_detected", "login", "logout", "user_create", "user_update", "error"]
    resource: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Création d'un événement d'audit simple.
    event1 = AuditEvent(
        ts=datetime.utcnow(),
        actor="user_123",
        action="sfd_upload",
        resource="document_abc.pdf",
        meta={"file_size_kb": 512, "upload_ip": "192.168.1.1"}
    )
    print(f"Événement 1 : {event1}")

    # Création d'un événement d'erreur.
    event2 = AuditEvent(
        ts=datetime.utcnow(),
        actor="system",
        action="error",
        meta={
            "error_type": "FileNotFoundError",
            "message": "Fichier introuvable lors du traitement",
            "path": "/tmp/non_existent_file.txt"
        }
    )
    print(f"Événement 2 : {event2}")

    # Accès aux attributs.
    print(f"Action de l'événement 1 : {event1.action}")
    if event1.meta:
        print(f"Taille du fichier de l'événement 1 : {event1.meta.get('file_size_kb')} KB")