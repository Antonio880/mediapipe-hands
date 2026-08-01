"""Fonte de vídeo: webcam local via OpenCV."""

from __future__ import annotations

import itertools
import time
from typing import Optional

import cv2

from engine.sources.base import Source
from engine.types import Frame


class WebcamSource(Source):
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        self._cap = cv2.VideoCapture(index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)
        self._frame_ids = itertools.count()

        if not self._cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir a webcam (índice {index}).")

    def read(self) -> Optional[Frame]:
        ok, image = self._cap.read()
        if not ok:
            return None
        return Frame(image=image, frame_id=next(self._frame_ids), timestamp=time.time())

    def release(self) -> None:
        self._cap.release()
