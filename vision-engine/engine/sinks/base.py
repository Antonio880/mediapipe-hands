"""Interface que todo sink de eventos deve implementar."""

from __future__ import annotations

from abc import ABC, abstractmethod

from engine.types import Event


class Sink(ABC):
    @abstractmethod
    def handle(self, event: Event) -> None:
        """Processa um evento (gravar, notificar, logar, etc)."""

    def __call__(self, event: Event) -> None:
        self.handle(event)
