"""Enricher: resolve a identidade de cada track por votação de embeddings.

Rodar reconhecimento facial em todo frame de todo track é desperdício de
CPU — a identidade de uma pessoa não muda quadro a quadro. A estratégia:
acumular embeddings enquanto o track é novo, votar quando atingir
`vote_frames` amostras, travar o resultado (`identity_locked = True`) e
parar de gastar processamento nele.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from engine.types import Frame, Track
from modules.face.gallery import Gallery


class FaceRecognizer:
    def __init__(
        self,
        gallery: Gallery,
        threshold: float = 0.45,
        vote_frames: int = 8,
        unknown_label: str = "desconhecido",
    ):
        self._gallery = gallery
        self._threshold = threshold
        self._vote_frames = vote_frames
        self._unknown_label = unknown_label
        self._votes: dict[int, list[tuple[str | None, float]]] = defaultdict(list)

    def enrich(self, tracks: list[Track], frame: Frame) -> None:
        # Descarta votos de tracks que já saíram de cena antes de completar
        # a votação (ex.: alguém que passou rápido demais). Sem isso, o
        # dicionário cresce sem limite ao longo de uma sessão longa.
        live_ids = {track.track_id for track in tracks}
        for stale_id in list(self._votes.keys()):
            if stale_id not in live_ids:
                self._votes.pop(stale_id, None)

        for track in tracks:
            if track.identity_locked:
                continue

            detection = track.last_detection
            if detection is None or detection.embedding is None:
                continue

            name, score = self._gallery.match(detection.embedding)
            self._votes[track.track_id].append((name, score))

            if len(self._votes[track.track_id]) >= self._vote_frames:
                self._resolve(track)

    def _resolve(self, track: Track) -> None:
        samples = self._votes.pop(track.track_id, [])
        candidates = [
            name for name, score in samples
            if name is not None and score >= self._threshold
        ]

        if not candidates:
            track.identity = self._unknown_label
            track.identity_score = 0.0
        else:
            winner, _ = Counter(candidates).most_common(1)[0]
            winner_scores = [score for name, score in samples if name == winner]
            track.identity = winner
            track.identity_score = sum(winner_scores) / len(winner_scores)

        track.identity_locked = True

    def forget(self, track_id: int) -> None:
        """Descarta votos pendentes de um track morto, para não vazar memória."""
        self._votes.pop(track_id, None)
