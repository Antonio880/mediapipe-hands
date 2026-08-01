"""Tracker por IoU, com carência antes de encerrar um track.

Geometria pura — sem nenhuma dependência de deep learning. Isso é
proposital: o motor precisa continuar funcionando mesmo sem nenhum
detector "inteligente" plugado, então o tracker não pode depender de
nada além de bounding boxes.

Um track só é removido depois de `max_missed_frames` consecutivos sem
nenhuma detecção correspondente. Essa carência é o que evita que, por
exemplo, um rosto virado de perfil por alguns frames vire uma "saída"
seguida de uma "entrada" espúrias.
"""

from __future__ import annotations

import itertools
import time

from engine.types import Detection, Track


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area

    if union <= 0:
        return 0.0
    return inter_area / union


class IoUTracker:
    """Associa Detections a Tracks existentes por sobreposição geométrica.

    Matching guloso (maior IoU primeiro) — suficiente para o volume de
    detecções de uma única câmera. Não é um MOT sofisticado para
    multidão, é o mínimo que resolve o problema real: manter o mesmo
    track_id enquanto a mesma pessoa está em cena.
    """

    def __init__(self, iou_threshold: float = 0.3, max_missed_frames: int = 30):
        self._iou_threshold = iou_threshold
        self._max_missed_frames = max_missed_frames
        self._tracks: dict[int, Track] = {}
        self._id_counter = itertools.count(1)

    @property
    def tracks(self) -> list[Track]:
        return list(self._tracks.values())

    def update(self, detections: list[Detection]) -> list[Track]:
        candidate_pairs: list[tuple[float, int, int]] = []
        for track_id, track in self._tracks.items():
            for det_idx, det in enumerate(detections):
                score = _iou(track.bbox, det.bbox)
                if score >= self._iou_threshold:
                    candidate_pairs.append((score, track_id, det_idx))
        candidate_pairs.sort(key=lambda p: p[0], reverse=True)

        matched_track_ids: set[int] = set()
        matched_det_indices: set[int] = set()
        for score, track_id, det_idx in candidate_pairs:
            if track_id in matched_track_ids or det_idx in matched_det_indices:
                continue
            matched_track_ids.add(track_id)
            matched_det_indices.add(det_idx)

            det = detections[det_idx]
            track = self._tracks[track_id]
            track.bbox = det.bbox
            track.last_detection = det
            track.last_seen = time.time()
            track.missed_frames = 0
            track.hits += 1

        # Detecções sem correspondência viram tracks novos. Entram direto em
        # matched_track_ids: um track recém-criado não pode já nascer com
        # carência, senão ele é penalizado por uma detecção que ele MESMO
        # representa.
        for det_idx, det in enumerate(detections):
            if det_idx in matched_det_indices:
                continue
            track_id = next(self._id_counter)
            self._tracks[track_id] = Track(
                track_id=track_id,
                bbox=det.bbox,
                label=det.label,
                last_detection=det,
                hits=1,
            )
            matched_track_ids.add(track_id)

        # Tracks sem correspondência: soma carência ou remove.
        for track_id in list(self._tracks.keys()):
            if track_id in matched_track_ids:
                continue
            track = self._tracks[track_id]
            track.missed_frames += 1
            if track.missed_frames > self._max_missed_frames:
                del self._tracks[track_id]

        return self.tracks
