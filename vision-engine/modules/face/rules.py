"""RuleSet: transforma identidade resolvida em eventos de entrada/saída.

Evento é transição de estado, não estado contínuo — "fulano está na
sala" não gera evento a cada frame; só a entrada e a saída geram, cada
uma, um único evento. A saída só é declarada quando o tracker de fato
remove o track (depois da carência de missed_frames), então esta regra
herda de graça a proteção contra oscilação de curta duração.
"""

from __future__ import annotations

from engine.types import Event, Frame, Track


class FaceRules:
    def __init__(self, unknown_label: str = "desconhecido"):
        self._unknown_label = unknown_label
        self._present_track_ids: set[int] = set()
        self._track_identity: dict[int, str] = {}

    def evaluate(self, tracks: list[Track], frame: Frame) -> list[Event]:
        events: list[Event] = []

        for track in tracks:
            if not track.identity_locked or track.track_id in self._present_track_ids:
                continue

            self._present_track_ids.add(track.track_id)
            self._track_identity[track.track_id] = track.identity or self._unknown_label
            events.append(
                Event(
                    type="entrada",
                    track_id=track.track_id,
                    identity=track.identity,
                    score=track.identity_score,
                    bbox=track.bbox,
                    frame=frame.image,
                )
            )

        current_track_ids = {t.track_id for t in tracks}
        gone_ids = self._present_track_ids - current_track_ids
        for track_id in gone_ids:
            self._present_track_ids.discard(track_id)
            identity = self._track_identity.pop(track_id, self._unknown_label)
            events.append(Event(type="saida", track_id=track_id, identity=identity))

        return events
