"""Janela de depuração: desenha caixas, IDs e identidades sobre o frame.

Existe só para desenvolvimento — nenhum outro componente do motor depende
dela. Rodar com display.enabled: false no config remove a janela sem
afetar detecção, tracking ou eventos em nada.
"""

from __future__ import annotations

import cv2

from engine.types import Frame, Track

_COLOR_KNOWN = (80, 200, 120)  # verde
_COLOR_UNKNOWN = (60, 60, 220)  # vermelho
_COLOR_PENDING = (200, 180, 60)  # azul claro


class Display:
    def __init__(self, window_name: str = "Vision Engine"):
        self._window_name = window_name

    def render(self, frame: Frame, tracks: list[Track]) -> bool:
        """Desenha e mostra o frame. Retorna False quando o usuário pede saída ('q')."""
        image = frame.image.copy()

        for track in tracks:
            if not track.is_confirmed:
                continue

            x1, y1, x2, y2 = (int(v) for v in track.bbox)

            if track.identity is None:
                color = _COLOR_PENDING
                label = f"#{track.track_id} ..."
            elif track.identity == "desconhecido":
                color = _COLOR_UNKNOWN
                label = f"#{track.track_id} desconhecido"
            else:
                color = _COLOR_KNOWN
                label = f"#{track.track_id} {track.identity} ({track.identity_score:.2f})"

            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                image, label, (x1, max(0, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
            )

        cv2.imshow(self._window_name, image)
        key = cv2.waitKey(1) & 0xFF
        return key != ord("q")

    def close(self) -> None:
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass
