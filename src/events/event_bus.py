# src/events/event_bus.py
import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Callable, Any

import redis.asyncio as redis

# Placeholder imports for now
from src.services.test_generator import TestGenerator
from src.services.notification_service import NotificationService
from src.services.storage_service import StorageService

test_generator = TestGenerator() # Assuming TestGenerator is a class
notification_service = NotificationService() # Assuming NotificationService is a class
storage_service = StorageService() # Assuming StorageService is a class


class EventType(Enum):
    SFD_UPLOADED = "sfd.uploaded"
    ANALYSIS_COMPLETED = "analysis.completed"
    TESTS_GENERATED = "tests.generated"
    PIPELINE_FAILED = "pipeline.failed"


@dataclass
class Event:
    type: EventType
    payload: Dict[str, Any]
    timestamp: datetime
    correlation_id: str


class EventBus:
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    def subscribe(self, event_type: EventType, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event):
        await self._queue.put(event)

    async def start(self):
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_event(event)
            except asyncio.TimeoutError:
                continue

    async def _process_event(self, event: Event):
        handlers = self._handlers.get(event.type, [])
        await asyncio.gather(
            *[handler(event) for handler in handlers],
            return_exceptions=True
        )


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
