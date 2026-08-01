"""Orquestra o ciclo: captura → detecção → tracking → regras → eventos → display.

Regra de ouro do motor: a captura roda numa thread separada e nunca
enfileira. Se a inferência está mais lenta que a câmera, o frame velho é
descartado — o motor sempre trabalha com o frame mais recente possível e
nunca acumula atraso.

Detector, Enricher e RuleSet são Protocols: qualquer módulo de aplicação
(face, contagem de fluxo, EPI) os implementa e é injetado aqui. Nenhum
deles é importado por este arquivo — é assim que o motor permanece
genérico. Sem detector nenhum plugado, o pipeline continua rodando
normalmente: abre a fonte, mostra a janela (se habilitada), só não gera
tracks nem eventos.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Optional, Protocol

from engine.bus import EventBus
from engine.display import Display
from engine.sources.base import Source
from engine.tracking import IoUTracker
from engine.types import Detection, Event, Frame, Track

logger = logging.getLogger("engine.pipeline")


class Detector(Protocol):
    def detect(self, frame: Frame) -> list[Detection]: ...


class Enricher(Protocol):
    """Recebe os tracks depois do tracking e pode preenchê-los (ex.: identidade)."""

    def enrich(self, tracks: list[Track], frame: Frame) -> None: ...


class RuleSet(Protocol):
    def evaluate(self, tracks: list[Track], frame: Frame) -> list[Event]: ...


class Pipeline:
    def __init__(
        self,
        source: Source,
        detector: Optional[Detector] = None,
        tracker: Optional[IoUTracker] = None,
        enrichers: Optional[list[Enricher]] = None,
        ruleset: Optional[RuleSet] = None,
        bus: Optional[EventBus] = None,
        display: Optional[Display] = None,
        detect_every_n_frames: int = 1,
    ):
        self._source = source
        self._detector = detector
        self._tracker = tracker or IoUTracker()
        self._enrichers = enrichers or []
        self._ruleset = ruleset
        self._bus = bus or EventBus()
        self._display = display
        self._detect_every_n_frames = max(1, detect_every_n_frames)

        self._frame_slot: queue.Queue = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self._frame_counter = 0

    def _capture_loop(self) -> None:
        while not self._stop_event.is_set():
            frame = self._source.read()
            if frame is None:
                time.sleep(0.01)
                continue

            # Fila de tamanho 1: descarta o frame antigo em vez de acumular atraso.
            if self._frame_slot.full():
                try:
                    self._frame_slot.get_nowait()
                except queue.Empty:
                    pass
            self._frame_slot.put(frame)

    def run(self) -> None:
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        logger.info("Pipeline iniciado. Ctrl+C para encerrar.")
        try:
            while not self._stop_event.is_set():
                try:
                    frame = self._frame_slot.get(timeout=0.5)
                except queue.Empty:
                    continue

                tracks = self._process_frame(frame)

                if self._display is not None:
                    keep_going = self._display.render(frame, tracks)
                    if not keep_going:
                        break
        except KeyboardInterrupt:
            logger.info("Encerrado pelo usuário (Ctrl+C).")
        finally:
            self.stop()

    def _process_frame(self, frame: Frame) -> list[Track]:
        self._frame_counter += 1

        # Detecção é throttled por config; nos frames pulados, o tracker
        # NÃO é atualizado com lista vazia (isso o faria pensar que todos
        # os tracks sumiram) — simplesmente reaproveita o estado atual.
        should_detect = (
            self._detector is None
            or self._frame_counter % self._detect_every_n_frames == 0
        )

        if should_detect:
            detections = self._detector.detect(frame) if self._detector else []
            tracks = self._tracker.update(detections)
        else:
            tracks = self._tracker.tracks

        for enricher in self._enrichers:
            enricher.enrich(tracks, frame)

        if self._ruleset is not None:
            events = self._ruleset.evaluate(tracks, frame)
            if events:
                self._bus.publish(events)

        return tracks

    def stop(self) -> None:
        self._stop_event.set()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=1.0)
        self._source.release()
        if self._display is not None:
            self._display.close()
        logger.info("Pipeline encerrado, recursos liberados.")
