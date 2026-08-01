"""Fontes de vídeo suportadas pelo motor."""

from __future__ import annotations

from typing import Any

from engine.sources.base import Source
from engine.sources.rtsp import RTSPSource
from engine.sources.webcam import WebcamSource

__all__ = ["Source", "WebcamSource", "RTSPSource", "build_source"]


def build_source(cfg: dict[str, Any]) -> Source:
    """Fábrica: cria a Source certa a partir da seção `source` de config.yaml."""
    source_type = cfg.get("type", "webcam")

    if source_type == "webcam":
        return WebcamSource(
            index=cfg.get("index", 0),
            width=cfg.get("width", 640),
            height=cfg.get("height", 480),
            fps=cfg.get("fps", 30),
        )

    if source_type == "rtsp":
        url = cfg.get("url")
        if not url:
            raise ValueError(
                "source.type é 'rtsp' mas source.url não foi definido em config.yaml."
            )
        return RTSPSource(url=url, reconnect_delay=cfg.get("reconnect_delay", 2.0))

    raise ValueError(f"source.type desconhecido: '{source_type}' (use 'webcam' ou 'rtsp').")
