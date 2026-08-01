"""Sinks disponíveis e fábrica que os conecta ao EventBus a partir do config."""

from __future__ import annotations

from typing import Any

from engine.bus import EventBus
from engine.sinks.base import Sink
from engine.sinks.console import ConsoleSink
from engine.sinks.snapshot import SnapshotSink
from engine.sinks.sqlite import SQLiteSink

__all__ = ["Sink", "ConsoleSink", "SQLiteSink", "SnapshotSink", "build_sinks"]


def build_sinks(cfg: dict[str, Any], bus: EventBus) -> list[Sink]:
    """Lê a seção `sinks` de config.yaml, instancia e inscreve cada sink ativo."""
    active: list[Sink] = []

    if cfg.get("console", True):
        active.append(ConsoleSink())

    sqlite_cfg = cfg.get("sqlite", {})
    if sqlite_cfg.get("enabled", True):
        active.append(SQLiteSink(path=sqlite_cfg.get("path", "events.db")))

    snapshot_cfg = cfg.get("snapshot", {})
    if snapshot_cfg.get("enabled", True):
        active.append(SnapshotSink(directory=snapshot_cfg.get("dir", "snapshots")))

    for sink in active:
        bus.subscribe(sink)

    return active
