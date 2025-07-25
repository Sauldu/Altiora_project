# src/audit/ring_buffer.py
"""Implémentation d'un tampon circulaire (ring buffer) pour les événements d'audit.

Ce module fournit une structure de données de type tampon circulaire qui stocke
un nombre fixe d'événements d'audit. Lorsque le tampon est plein, les nouveaux
événements écrasent les plus anciens. Cela est utile pour collecter des logs
en mémoire avant de les écrire par lots sur disque, réduisant ainsi la charge
E/S et la latence.
"""

import json
from collections import deque
from dataclasses import asdict
from typing import List

from src.audit.models import AuditEvent


class RingBuffer:
    """Un tampon circulaire pour stocker un nombre limité d'événements d'audit en mémoire."""

    def __init__(self, size: int = 10_000):
        """Initialise le tampon circulaire.

        Args:
            size: La taille maximale du tampon (nombre d'événements).
        """
        self._buf: deque[str] = deque(maxlen=size) # Utilise `deque` avec `maxlen` pour la fonctionnalité de tampon circulaire.

    def push(self, event: AuditEvent) -> None:
        """Ajoute un événement d'audit au tampon.

        L'événement est converti en chaîne JSON avant d'être stocké.
        Si le tampon est plein, l'événement le plus ancien est automatiquement supprimé.

        Args:
            event: L'objet `AuditEvent` à ajouter.
        """
        # Convertit l'objet AuditEvent en JSON string pour le stockage.
        self._buf.append(json.dumps(asdict(event), default=str))

    def flush(self) -> List[str]:
        """Vide le contenu du tampon et le retourne sous forme de liste de chaînes JSON.

        Après l'appel, le tampon est vidé.

        Returns:
            Une liste de chaînes JSON, chaque chaîne représentant un événement d'audit.
        """
        out = list(self._buf) # Copie le contenu du deque dans une liste.
        self._buf.clear() # Vide le deque.
        return out


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    from datetime import datetime
    import time

    print("\n--- Démonstration du RingBuffer ---")
    buffer_size = 5
    buffer = RingBuffer(size=buffer_size)

    # Ajout d'événements jusqu'à remplir le tampon.
    for i in range(buffer_size):
        event = AuditEvent(
            ts=datetime.utcnow(),
            actor=f"user_{i}",
            action="test_action",
            meta={"value": i}
        )
        buffer.push(event)
        print(f"Ajouté événement {i}. Taille du tampon : {len(buffer._buf)}")

    print("\n--- Tampon plein, ajout d'un nouvel événement (écrase le plus ancien) ---")
    event_new = AuditEvent(
        ts=datetime.utcnow(),
        actor="user_new",
        action="new_action",
        meta={"value": 99}
    )
    buffer.push(event_new)
    print(f"Ajouté événement 99. Taille du tampon : {len(buffer._buf)}")

    print("\n--- Contenu du tampon après ajout (le premier événement devrait être parti) ---")
    for item in buffer._buf:
        print(json.loads(item).get("meta", {}).get("value"))

    print("\n--- Vidage du tampon (flush) ---")
    flushed_events = buffer.flush()
    print(f"Nombre d'événements vidés : {len(flushed_events)}")
    print(f"Tampon après vidage : {len(buffer._buf)}")

    print("\n--- Contenu des événements vidés ---")
    for event_str in flushed_events:
        event_dict = json.loads(event_str)
        print(f"Action: {event_dict['action']}, Acteur: {event_dict['actor']}, Valeur: {event_dict['meta'].get('value')}")

    print("Démonstration du RingBuffer terminée.")