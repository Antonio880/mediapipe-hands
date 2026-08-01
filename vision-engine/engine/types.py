"""Contrato de dados do motor de visão computacional.

Este módulo define a fronteira entre o MOTOR (genérico, reaproveitável) e
os MÓDULOS de aplicação (face, contagem de fluxo, EPI, etc). O motor só
conhece estes quatro tipos — nunca importa nada de dentro de modules/.

    Frame       → o que a câmera entregou neste instante
    Detection   → uma caixa que um Detector encontrou num Frame
    Track       → uma Detection que persiste no tempo, com identidade própria
    Event       → uma transição de estado de um Track que merece ser registrada
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class Frame:
    """Um frame capturado de uma fonte de vídeo."""

    image: np.ndarray  # BGR, formato OpenCV
    frame_id: int
    timestamp: float = field(default_factory=time.time)
    source_id: str = "default"


@dataclass
class Detection:
    """Uma detecção bruta produzida por um Detector, num único frame."""

    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2) em pixels
    score: float
    label: str = "object"
    embedding: Optional[np.ndarray] = None  # ex.: vetor facial 512-d
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Track:
    """Uma Detection que persiste ao longo do tempo, com identidade própria.

    O motor cria, atualiza e remove tracks (ver engine.tracking). Os campos
    de identidade (identity, identity_score, identity_locked) começam
    vazios e só são preenchidos por um Enricher de módulo — o motor nunca
    escreve neles.
    """

    track_id: int
    bbox: tuple[float, float, float, float]
    label: str
    last_detection: Optional[Detection] = None
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    missed_frames: int = 0
    hits: int = 0

    identity: Optional[str] = None
    identity_score: float = 0.0
    identity_locked: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_confirmed(self) -> bool:
        """Track só é considerado 'real' após algumas detecções consecutivas.

        Evita que ruído de um único frame vire uma caixa piscando na tela.
        """
        return self.hits >= 3


@dataclass
class Event:
    """Algo que aconteceu e merece ser registrado ou notificado."""

    type: str  # ex.: "entrada", "saida"
    track_id: int
    timestamp: float = field(default_factory=time.time)
    identity: Optional[str] = None
    score: float = 0.0
    bbox: Optional[tuple[float, float, float, float]] = None
    frame: Optional[np.ndarray] = None  # snapshot opcional para sinks de imagem
    data: dict[str, Any] = field(default_factory=dict)
