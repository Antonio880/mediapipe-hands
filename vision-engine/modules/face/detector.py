"""Detector de rostos via InsightFace, acelerado por CoreML no Apple Silicon.

Implementa o Protocol `Detector` do motor: recebe um Frame, devolve uma
lista de Detection. O motor não sabe (e não precisa saber) que por trás
disso existe uma rede neural — só enxerga bounding boxes e, opcionalmente,
um embedding.
"""

from __future__ import annotations

import logging

from insightface.app import FaceAnalysis

from engine.types import Detection, Frame

logger = logging.getLogger("modules.face.detector")

_PROVIDERS_BY_MODE = {
    "coreml": ["CoreMLExecutionProvider", "CPUExecutionProvider"],
    "cpu": ["CPUExecutionProvider"],
}


class FaceDetector:
    def __init__(self, provider: str = "coreml", det_size: tuple[int, int] = (320, 320)):
        providers = _PROVIDERS_BY_MODE.get(provider, _PROVIDERS_BY_MODE["cpu"])
        self._app = FaceAnalysis(name="buffalo_l", providers=providers)
        self._app.prepare(ctx_id=0, det_size=det_size)
        logger.info("FaceDetector pronto (providers=%s)", providers)

    def detect(self, frame: Frame) -> list[Detection]:
        faces = self._app.get(frame.image)
        detections: list[Detection] = []
        for face in faces:
            x1, y1, x2, y2 = face.bbox
            detections.append(
                Detection(
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    score=float(face.det_score),
                    label="face",
                    embedding=face.normed_embedding,
                    extra={"kps": face.kps},
                )
            )
        return detections
