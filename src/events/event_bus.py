# src/events/event_bus.py
"""Module implémentant un bus d'événements asynchrone pour la communication inter-composants.

Ce bus d'événements permet aux différents modules de l'application de communiquer
de manière découplée en publiant et en s'abonnant à des événements. Il utilise
une file d'attente asynchrone pour gérer les événements et peut être étendu
pour utiliser des systèmes de messagerie distribués comme Redis Pub/Sub.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Callable, Any, Optional

import redis.asyncio as redis

# Importations factices pour la démonstration. En production, ce seraient de vrais services.
# from src.services.test_generator import TestGenerator
# from src.services.notification_service import NotificationService
# from src.services.storage_service import StorageService

# test_generator = TestGenerator() # Supposons que TestGenerator est une classe
# notification_service = NotificationService() # Supposons que NotificationService est une classe
# storage_service = StorageService() # Supposons que StorageService est une classe


class EventType(Enum):
    """Énumération des types d'événements supportés par le bus."""
    SFD_UPLOADED = "sfd.uploaded"
    ANALYSIS_COMPLETED = "analysis.completed"
    TESTS_GENERATED = "tests.generated"
    PIPELINE_FAILED = "pipeline.failed"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"


@dataclass
class Event:
    """Représente un événement circulant dans le bus."""
    type: EventType
    payload: Dict[str, Any]
    timestamp: datetime
    correlation_id: str # Pour suivre les événements à travers les systèmes.


class EventBus:
    """Bus d'événements asynchrone pour la publication/souscription d'événements."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialise le bus d'événements."

        Args:
            redis_client: Un client Redis asynchrone pour une éventuelle extension
                          vers un bus d'événements distribué (Pub/Sub).
        """
        self._handlers: Dict[EventType, List[Callable]] = {} # Mappe les types d'événements à leurs gestionnaires.
        self._queue: asyncio.Queue = asyncio.Queue() # File d'attente interne pour les événements.
        self._running = False # Indique si le bus est en cours d'exécution.
        self.redis_client = redis_client

    def subscribe(self, event_type: EventType, handler: Callable):
        """Abonne un gestionnaire à un type d'événement spécifique."

        Args:
            event_type: Le type d'événement auquel s'abonner.
            handler: La fonction (ou coroutine) qui sera appelée lorsque l'événement se produit.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event):
        """Publie un événement sur le bus."

        L'événement est placé dans la file d'attente interne pour un traitement asynchrone.

        Args:
            event: L'objet `Event` à publier.
        """
        await self._queue.put(event)

    async def start(self):
        """Démarre le traitement des événements en arrière-plan."

        Cette méthode lance une boucle qui consomme les événements de la file
        d'attente et les distribue aux gestionnaires abonnés.
        """
        self._running = True
        while self._running:
            try:
                # Attend un événement avec un timeout pour permettre un arrêt propre.
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_event(event)
            except asyncio.TimeoutError:
                continue # Continue la boucle si aucun événement n'est disponible.
            except asyncio.CancelledError:
                break # Le bus a été arrêté.
            except Exception as e:
                # Loggue l'erreur mais continue de traiter les autres événements.
                print(f"Erreur lors du traitement d'un événement : {e}")

    async def stop(self):
        """Arrête le bus d'événements et attend la fin du traitement des événements en cours."""
        self._running = False
        # Attend que la file d'attente soit vide.
        await self._queue.join()

    async def _process_event(self, event: Event):
        """Distribue un événement à tous les gestionnaires abonnés."

        Args:
            event: L'objet `Event` à traiter.
        """
        handlers = self._handlers.get(event.type, [])
        # Exécute tous les gestionnaires en parallèle.
        await asyncio.gather(
            *[handler(event) for handler in handlers],
            return_exceptions=True # Permet aux autres gestionnaires de s'exécuter même si l'un échoue.
        )


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Fonctions de gestionnaires factices.
    async def handle_sfd_uploaded(event: Event):
        logging.info(f"[Handler SFD] SFD téléchargée : {event.payload.get('filename')}")
        # Simule une action, ex: déclencher l'analyse.
        # await test_generator.generate_from_sfd(event.payload["sfd_id"])

    async def handle_analysis_completed(event: Event):
        logging.info(f"[Handler Analyse] Analyse terminée pour SFD : {event.payload.get('sfd_id')}")
        # Simule une action, ex: notifier l'utilisateur.
        # await notification_service.notify(event.payload)

    async def handle_pipeline_failed(event: Event):
        logging.error(f"[Handler Échec] Pipeline échoué pour ID : {event.payload.get('pipeline_id')}. Erreur : {event.payload.get('error')}")
        # Simule une action, ex: envoyer une alerte à l'administrateur.

    async def demo():
        print("\n--- Démonstration du EventBus ---")
        bus = EventBus()
        await bus.start() # Démarre le bus d'événements.

        # Abonnements aux événements.
        bus.subscribe(EventType.SFD_UPLOADED, handle_sfd_uploaded)
        bus.subscribe(EventType.ANALYSIS_COMPLETED, handle_analysis_completed)
        bus.subscribe(EventType.PIPELINE_FAILED, handle_pipeline_failed)

        # Publication d'événements.
        print("Publication d'événements...")
        await bus.publish(Event(
            type=EventType.SFD_UPLOADED,
            payload={'sfd_id': 'SFD-001', 'filename': 'spec_v1.pdf'},
            timestamp=datetime.utcnow(),
            correlation_id='corr-123'
        ))

        await bus.publish(Event(
            type=EventType.ANALYSIS_COMPLETED,
            payload={'sfd_id': 'SFD-001', 'scenarios_count': 10},
            timestamp=datetime.utcnow(),
            correlation_id='corr-123'
        ))

        await bus.publish(Event(
            type=EventType.PIPELINE_FAILED,
            payload={'pipeline_id': 'PIPE-001', 'error': 'Étape de génération de code échouée.'},
            timestamp=datetime.utcnow(),
            correlation_id='corr-456'
        ))

        # Donne un peu de temps aux gestionnaires pour traiter les événements.
        await asyncio.sleep(2)

        print("Arrêt du bus d'événements...")
        await bus.stop()
        print("Démonstration terminée.")

    asyncio.run(demo())