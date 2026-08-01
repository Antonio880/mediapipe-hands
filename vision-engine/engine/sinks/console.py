"""Sink mais simples possível: imprime o evento no terminal."""

from __future__ import annotations

import time

from engine.sinks.base import Sink
from engine.types import Event


class ConsoleSink(Sink):
    def handle(self, event: Event) -> None:
        ts = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
        who = event.identity or "desconhecido"
        print(
            f"[{ts}] {event.type.upper():10s} "
            f"track={event.track_id} identity={who} score={event.score:.2f}"
        )
