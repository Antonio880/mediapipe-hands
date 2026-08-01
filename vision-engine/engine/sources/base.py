"""Interface que toda fonte de vídeo deve implementar."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from engine.types import Frame


class Source(ABC):
    """Fonte de frames. O motor não sabe se por trás é webcam, RTSP ou arquivo."""

    @abstractmethod
    def read(self) -> Optional[Frame]:
        """Retorna o próximo frame disponível, ou None se nada estiver pronto."""

    @abstractmethod
    def release(self) -> None:
        """Libera os recursos da fonte (câmera, socket, etc)."""
