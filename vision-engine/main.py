"""Ponto de entrada: monta o motor com o módulo de reconhecimento facial.

Trocar de vertical (face → contagem de fluxo, EPI, etc.) significa trocar
só o bloco marcado MÓDULO abaixo — source, tracker, pipeline, sinks e
display não mudam uma linha.
"""

from __future__ import annotations

import logging

from engine.bus import EventBus
from engine.config import load_config
from engine.display import Display
from engine.pipeline import Pipeline
from engine.sinks import build_sinks
from engine.sources import build_source
from engine.tracking import IoUTracker

# ── MÓDULO: troque estes imports para mudar de aplicação ──────────────────
from modules.face.detector import FaceDetector
from modules.face.gallery import Gallery
from modules.face.recognizer import FaceRecognizer
from modules.face.rules import FaceRules

# ────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)


def main() -> None:
    config = load_config("config.yaml")

    # ── MOTOR ────────────────────────────────────────────────────────────
    source = build_source(config["source"])
    tracker = IoUTracker(
        iou_threshold=config["tracking"]["iou_threshold"],
        max_missed_frames=config["tracking"]["max_missed_frames"],
    )
    bus = EventBus()
    build_sinks(config["sinks"], bus)
    display = (
        Display(config["display"]["window_name"])
        if config["display"]["enabled"]
        else None
    )
    # ────────────────────────────────────────────────────────────────────

    # ── MÓDULO: face ─────────────────────────────────────────────────────
    face_cfg = config["face"]
    gallery = Gallery(directory=face_cfg["gallery_dir"])
    if gallery.is_empty:
        logging.warning(
            "Galeria vazia — ninguém será reconhecido. Cadastre alguém com: "
            'python -m modules.face.enroll "Nome"'
        )
    detector = FaceDetector(provider=face_cfg["provider"])
    recognizer = FaceRecognizer(
        gallery=gallery,
        threshold=face_cfg["recognition_threshold"],
        vote_frames=face_cfg["vote_frames"],
        unknown_label=face_cfg["unknown_label"],
    )
    ruleset = FaceRules(unknown_label=face_cfg["unknown_label"])
    # ────────────────────────────────────────────────────────────────────

    pipeline = Pipeline(
        source=source,
        detector=detector,
        tracker=tracker,
        enrichers=[recognizer],
        ruleset=ruleset,
        bus=bus,
        display=display,
        detect_every_n_frames=config["detection"]["every_n_frames"],
    )
    pipeline.run()


if __name__ == "__main__":
    main()
