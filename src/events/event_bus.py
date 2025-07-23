# src/events/event_bus.py
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Callable, Any


@dataclass
class Event:
    """Événement du système"""
    type: str
    payload: Dict[str, Any]
    timestamp: datetime = None
    correlation_id: str = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow()


class EventBus:
    """Bus d'événements asynchrone"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.handlers: Dict[str, List[Callable]] = {}
        self.running = False

    def subscribe(self, event_type: str, handler: Callable):
        """S'abonner à un type d'événement"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)

    async def publish(self, event: Event):
        """Publier un événement"""
        # Publier dans Redis pour distribution
        await self.redis.publish(
            f"events:{event.type}",
            json.dumps({
                "type": event.type,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat(),
                "correlation_id": event.correlation_id
            })
        )

    async def start(self):
        """Démarrer l'écoute des événements"""
        self.running = True
        pubsub = self.redis.pubsub()

        # S'abonner aux patterns d'événements
        await pubsub.psubscribe("events:*")

        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                await self._handle_message(message)

    async def _handle_message(self, message):
        """Traiter un message reçu"""
        try:
            data = json.loads(message["data"])
            event = Event(**data)

            # Appeler les handlers
            if event.type in self.handlers:
                tasks = [
                    handler(event)
                    for handler in self.handlers[event.type]
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Erreur traitement événement: {e}")


# Utilisation
event_bus = EventBus(redis_client)


# S'abonner aux événements
@event_bus.subscribe("sfd.processed")
async def on_sfd_processed(event: Event):
    """Déclencher génération de tests"""
    await test_generator.generate_from_sfd(event.payload["sfd_id"])


@event_bus.subscribe("test.generated")
async def on_test_generated(event: Event):
    """Notifier et sauvegarder"""
    await notification_service.notify(event.payload)
    await storage_service.save_test(event.payload)
