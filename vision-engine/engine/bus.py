"""Barramento de eventos: o motor publica, os sinks consomem.

Um sink que lança exceção não pode derrubar os outros nem o pipeline —
por isso cada handler roda isolado dentro de um try/except.
"""

from __future__ import annotations

import logging
from typing import Callable

from engine.types import Event

logger = logging.getLogger("engine.bus")

Handler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: list[Handler] = []

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    def publish(self, events: list[Event]) -> None:
        for event in events:
            for handler in self._handlers:
                try:
                    handler(event)
                except Exception:
                    logger.exception("Sink falhou ao processar evento '%s'", event.type)
