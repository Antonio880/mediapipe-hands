"""CLI de cadastro: grava o rosto de uma pessoa e salva o embedding médio na galeria.

Uso:
    python -m modules.face.enroll "Nome da Pessoa"

Fica de olho na câmera, capta algumas amostras de rosto e salva a média
dos embeddings — não precisa de foto de referência nem dataset pronto.
"""

from __future__ import annotations

import sys
import time

import cv2
import numpy as np

from engine.config import load_config
from engine.sources import build_source
from modules.face.detector import FaceDetector
from modules.face.gallery import Gallery

SAMPLES_NEEDED = 20


def main() -> None:
    if len(sys.argv) < 2:
        print('Uso: python -m modules.face.enroll "Nome da Pessoa"')
        sys.exit(1)

    name = sys.argv[1]
    config = load_config("config.yaml")
    face_cfg = config["face"]

    source = build_source(config["source"])
    detector = FaceDetector(provider=face_cfg.get("provider", "coreml"))
    gallery = Gallery(directory=face_cfg.get("gallery_dir", "gallery"))

    print(f"Cadastrando '{name}'. Olhe para a câmera e vire o rosto levemente.")
    print(f"Coletando {SAMPLES_NEEDED} amostras... (Ctrl+C ou 'q' para cancelar)")

    embeddings: list[np.ndarray] = []

    try:
        while len(embeddings) < SAMPLES_NEEDED:
            frame = source.read()
            if frame is None:
                time.sleep(0.01)
                continue

            detections = detector.detect(frame)
            preview = frame.image.copy()

            if len(detections) == 1 and detections[0].embedding is not None:
                embeddings.append(detections[0].embedding)
                x1, y1, x2, y2 = (int(v) for v in detections[0].bbox)
                cv2.rectangle(preview, (x1, y1), (x2, y2), (80, 200, 120), 2)
                print(f"  amostra {len(embeddings)}/{SAMPLES_NEEDED}")
            elif len(detections) > 1:
                cv2.putText(
                    preview, "Apenas um rosto por vez", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (60, 60, 220), 2,
                )

            cv2.putText(
                preview, f"{len(embeddings)}/{SAMPLES_NEEDED}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
            )
            cv2.imshow("Cadastro", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("Cancelado.")
                sys.exit(1)

    except KeyboardInterrupt:
        print("\nCancelado.")
        sys.exit(1)
    finally:
        source.release()
        cv2.destroyAllWindows()

    average_embedding = np.mean(np.stack(embeddings), axis=0)
    gallery.save(name, average_embedding)
    print(f"'{name}' cadastrado com sucesso em {face_cfg.get('gallery_dir', 'gallery')}/{name}/")


if __name__ == "__main__":
    main()
