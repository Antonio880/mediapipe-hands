"""Sink que salva um recorte (crop) da imagem quando o evento traz um frame anexado."""

from __future__ import annotations

from pathlib import Path

import cv2

from engine.sinks.base import Sink
from engine.types import Event


class SnapshotSink(Sink):
    def __init__(self, directory: str = "snapshots"):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def handle(self, event: Event) -> None:
        if event.frame is None:
            return

        image = event.frame
        if event.bbox is not None:
            x1, y1, x2, y2 = (max(0, int(v)) for v in event.bbox)
            crop = image[y1:y2, x1:x2]
            if crop.size > 0:
                image = crop

        who = event.identity or "desconhecido"
        filename = f"{event.type}_{who}_{int(event.timestamp)}.jpg"
        cv2.imwrite(str(self._dir / filename), image)
