"""Galeria de identidades: embeddings de referência salvos em disco.

Cada pessoa cadastrada vira uma pasta em gallery_dir/<nome>/embedding.npy
— o vetor médio das amostras capturadas no cadastro (ver enroll.py). Sem
banco de dados, sem serviço externo: é só numpy no disco.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger("modules.face.gallery")


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class Gallery:
    def __init__(self, directory: str = "gallery"):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._embeddings: dict[str, np.ndarray] = {}
        self.reload()

    def reload(self) -> None:
        self._embeddings.clear()
        for person_dir in sorted(self._dir.iterdir()):
            embedding_path = person_dir / "embedding.npy"
            if person_dir.is_dir() and embedding_path.exists():
                self._embeddings[person_dir.name] = np.load(embedding_path)
        logger.info(
            "Galeria carregada: %d pessoa(s) — %s",
            len(self._embeddings), list(self._embeddings.keys()),
        )

    def save(self, name: str, embedding: np.ndarray) -> None:
        person_dir = self._dir / name
        person_dir.mkdir(parents=True, exist_ok=True)
        np.save(person_dir / "embedding.npy", embedding)
        self._embeddings[name] = embedding

    def match(self, embedding: np.ndarray) -> tuple[str | None, float]:
        """Retorna (nome, score) do melhor casamento, ou (None, 0.0) se a galeria estiver vazia."""
        best_name: str | None = None
        best_score = 0.0
        for name, ref in self._embeddings.items():
            score = _cosine_similarity(embedding, ref)
            if score > best_score:
                best_score = score
                best_name = name
        return best_name, best_score

    @property
    def is_empty(self) -> bool:
        return len(self._embeddings) == 0
