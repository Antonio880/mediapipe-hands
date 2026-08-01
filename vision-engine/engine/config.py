"""Carregamento de configuração do motor a partir de config.yaml.

Todo comportamento ajustável (fonte de vídeo, limiares de tracking, sinks
ativos, parâmetros do módulo de face) mora em config.yaml — nunca em
constantes espalhadas pelo código. Se o arquivo não existir ou faltar
alguma chave, os DEFAULTS cobrem o buraco.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "source": {
        "type": "webcam",  # webcam | rtsp
        "index": 0,
        "url": None,
        "width": 640,
        "height": 480,
        "fps": 30,
        "reconnect_delay": 2.0,
    },
    "detection": {
        "every_n_frames": 1,
    },
    "tracking": {
        "iou_threshold": 0.3,
        "max_missed_frames": 30,  # ~1s de carência a 30fps
    },
    "display": {
        "enabled": True,
        "window_name": "Vision Engine",
    },
    "sinks": {
        "console": True,
        "sqlite": {"enabled": True, "path": "events.db"},
        "snapshot": {"enabled": True, "dir": "snapshots"},
    },
    "face": {
        "gallery_dir": "gallery",
        "recognition_threshold": 0.45,
        "vote_frames": 8,
        "provider": "coreml",  # coreml (Apple Silicon) | cpu
        "unknown_label": "desconhecido",
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    """Carrega config.yaml e mescla com os defaults.

    Arquivo ausente não é erro — o motor sobe só com os defaults, o que
    facilita testar a infraestrutura sem escrever configuração nenhuma.
    """
    path = Path(path)
    user_config: dict[str, Any] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULTS, user_config)
