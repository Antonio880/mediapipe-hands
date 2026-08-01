"""Fonte de vídeo: câmera IP via RTSP, com reconexão automática.

Câmeras RTSP caem — não é exceção, é rotina: Wi-Fi soletra, a câmera
reinicia sozinha, a rede engasga. Esta fonte nunca propaga a falha para
cima: tenta reconectar indefinidamente e devolve None enquanto não
consegue, deixando o pipeline decidir o que fazer (normalmente: esperar
o próximo frame).
"""

from __future__ import annotations

import itertools
import time
from typing import Optional

import cv2

from engine.sources.base import Source
from engine.types import Frame


class RTSPSource(Source):
    def __init__(self, url: str, reconnect_delay: float = 2.0):
        self._url = url
        self._reconnect_delay = reconnect_delay
        self._frame_ids = itertools.count()
        self._cap: Optional[cv2.VideoCapture] = None
        self._last_reconnect_attempt = 0.0
        self._connect()

    def _connect(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = cv2.VideoCapture(self._url)
        self._last_reconnect_attempt = time.time()

    def read(self) -> Optional[Frame]:
        if self._cap is None or not self._cap.isOpened():
            self._maybe_reconnect()
            return None

        ok, image = self._cap.read()
        if not ok:
            self._maybe_reconnect()
            return None

        return Frame(image=image, frame_id=next(self._frame_ids), timestamp=time.time())

    def _maybe_reconnect(self) -> None:
        if time.time() - self._last_reconnect_attempt >= self._reconnect_delay:
            self._connect()

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
