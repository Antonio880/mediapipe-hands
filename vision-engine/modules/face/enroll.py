"""UI de cadastro facial — tudo dentro da janela da câmera, sem terminal.

Fluxo: digitar o nome (teclado, direto na janela) → contagem regressiva →
captura de amostras com feedback visual (caixa verde/vermelha, barra de
progresso) → confirmação com botões clicáveis ("cadastrar outra" / "sair").
Cancelamento a qualquer momento com Esc ou o X no canto superior direito.

Uso:
    python -m modules.face.enroll
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from engine.config import load_config
from engine.sources import build_source
from engine.types import Frame
from modules.face.detector import FaceDetector
from modules.face.gallery import Gallery

WINDOW_NAME = "Cadastro facial"
SAMPLES_NEEDED = 20
COUNTDOWN_SECONDS = 3

_ACCENT = (120, 200, 90)  # verde, BGR
_DANGER = (60, 60, 220)  # vermelho, BGR
_NEUTRAL = (90, 90, 90)
_TEXT = (255, 255, 255)
_MUTED = (190, 190, 190)
_OVERLAY_BG = (30, 30, 30)


@dataclass
class Button:
    """Retângulo clicável desenhado sobre o frame."""

    rect: tuple[int, int, int, int]  # x1, y1, x2, y2
    label: str
    color: tuple[int, int, int] = _NEUTRAL

    def contains(self, point: tuple[int, int] | None) -> bool:
        if point is None:
            return False
        x1, y1, x2, y2 = self.rect
        return x1 <= point[0] <= x2 and y1 <= point[1] <= y2

    def draw(self, image: np.ndarray) -> None:
        x1, y1, x2, y2 = self.rect
        cv2.rectangle(image, (x1, y1), (x2, y2), self.color, -1)
        cv2.rectangle(image, (x1, y1), (x2, y2), _TEXT, 1)
        size = cv2.getTextSize(self.label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0]
        tx = x1 + (x2 - x1 - size[0]) // 2
        ty = y1 + (y2 - y1 + size[1]) // 2
        cv2.putText(
            image, self.label, (tx, ty),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, _TEXT, 1, cv2.LINE_AA,
        )


class EnrollUI:
    STATE_NAME = "name"
    STATE_COUNTDOWN = "countdown"
    STATE_CAPTURING = "capturing"
    STATE_DONE = "done"

    def __init__(self) -> None:
        config = load_config("config.yaml")
        face_cfg = config["face"]

        self._source = build_source(config["source"])
        self._detector = FaceDetector(provider=face_cfg["provider"])
        self._gallery = Gallery(directory=face_cfg["gallery_dir"])

        self._state = self.STATE_NAME
        self._name = ""
        self._countdown_start = 0.0
        self._embeddings: list[np.ndarray] = []
        self._status_message = ""
        self._mouse_click: tuple[int, int] | None = None
        self._should_close = False

        cv2.namedWindow(WINDOW_NAME)
        cv2.setMouseCallback(WINDOW_NAME, self._on_mouse)

    def _on_mouse(self, event: int, x: int, y: int, flags: int, param: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self._mouse_click = (x, y)

    def run(self) -> None:
        try:
            while not self._should_close:
                frame = self._source.read()
                if frame is None:
                    time.sleep(0.01)
                    continue

                canvas = frame.image.copy()
                self._draw_close_button(canvas)

                if self._state == self.STATE_NAME:
                    self._step_name(canvas)
                elif self._state == self.STATE_COUNTDOWN:
                    self._step_countdown(canvas)
                elif self._state == self.STATE_CAPTURING:
                    self._step_capturing(canvas, frame)
                elif self._state == self.STATE_DONE:
                    self._step_done(canvas)

                cv2.imshow(WINDOW_NAME, canvas)
                key = cv2.waitKey(1) & 0xFF
                self._handle_key(key)
                self._mouse_click = None
        finally:
            self._source.release()
            cv2.destroyWindow(WINDOW_NAME)

    # ── Botão de fechar, presente em todo estado ────────────────────────

    def _draw_close_button(self, canvas: np.ndarray) -> None:
        h, w = canvas.shape[:2]
        button = Button((w - 34, 8, w - 8, 34), "x", color=_DANGER)
        button.draw(canvas)
        if button.contains(self._mouse_click):
            self._should_close = True

    # ── Estado: digitar o nome ──────────────────────────────────────────

    def _step_name(self, canvas: np.ndarray) -> None:
        h, w = canvas.shape[:2]
        self._darken(canvas)

        cv2.putText(
            canvas, "Nome da pessoa:", (24, h // 2 - 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, _MUTED, 1, cv2.LINE_AA,
        )

        box = (24, h // 2 - 20, w - 24, h // 2 + 20)
        cv2.rectangle(canvas, box[:2], box[2:], _TEXT, 1)
        caret = "_" if int(time.time() * 2) % 2 == 0 else ""
        cv2.putText(
            canvas, self._name + caret, (box[0] + 12, box[3] - 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, _TEXT, 1, cv2.LINE_AA,
        )

        hint = "Digite e pressione Enter para continuar"
        cv2.putText(
            canvas, hint, (24, h // 2 + 50),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, _MUTED, 1, cv2.LINE_AA,
        )

    def _handle_name_key(self, key: int) -> None:
        if key in (13, 10):  # Enter
            if self._name.strip():
                self._countdown_start = time.time()
                self._state = self.STATE_COUNTDOWN
        elif key in (8, 127):  # Backspace
            self._name = self._name[:-1]
        elif 32 <= key <= 126:  # ASCII imprimível
            if len(self._name) < 30:
                self._name += chr(key)

    # ── Estado: contagem regressiva ─────────────────────────────────────

    def _step_countdown(self, canvas: np.ndarray) -> None:
        h, w = canvas.shape[:2]
        remaining = COUNTDOWN_SECONDS - (time.time() - self._countdown_start)

        if remaining <= 0:
            self._embeddings = []
            self._state = self.STATE_CAPTURING
            return

        self._darken(canvas)
        text = str(int(remaining) + 1)
        size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 3, 4)[0]
        cv2.putText(
            canvas, text, ((w - size[0]) // 2, (h + size[1]) // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 3, _ACCENT, 4, cv2.LINE_AA,
        )
        cv2.putText(
            canvas, "Prepare-se, olhe para a câmera", (24, h - 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, _MUTED, 1, cv2.LINE_AA,
        )

    # ── Estado: captura das amostras ────────────────────────────────────

    def _step_capturing(self, canvas: np.ndarray, frame: Frame) -> None:
        h, w = canvas.shape[:2]
        detections = self._detector.detect(frame)

        if len(detections) == 1 and detections[0].embedding is not None:
            self._embeddings.append(detections[0].embedding)
            x1, y1, x2, y2 = (int(v) for v in detections[0].bbox)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), _ACCENT, 2)
            self._status_message = ""
        elif len(detections) > 1:
            self._status_message = "Apenas um rosto por vez"
        elif not detections:
            self._status_message = "Nenhum rosto detectado"

        if self._status_message:
            cv2.putText(
                canvas, self._status_message, (24, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, _DANGER, 2, cv2.LINE_AA,
            )

        progress = len(self._embeddings) / SAMPLES_NEEDED
        bar_y = h - 40
        cv2.rectangle(canvas, (24, bar_y), (w - 24, bar_y + 14), _NEUTRAL, -1)
        cv2.rectangle(
            canvas, (24, bar_y), (24 + int((w - 48) * progress), bar_y + 14),
            _ACCENT, -1,
        )
        cv2.putText(
            canvas, f"{len(self._embeddings)}/{SAMPLES_NEEDED}", (24, bar_y - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, _TEXT, 1, cv2.LINE_AA,
        )

        if len(self._embeddings) >= SAMPLES_NEEDED:
            average = np.mean(np.stack(self._embeddings), axis=0)
            self._gallery.save(self._name.strip(), average)
            self._state = self.STATE_DONE

    # ── Estado: confirmação ──────────────────────────────────────────────

    def _step_done(self, canvas: np.ndarray) -> None:
        h, w = canvas.shape[:2]
        self._darken(canvas)

        message = f"'{self._name.strip()}' cadastrado com sucesso"
        size = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0]
        cv2.putText(
            canvas, message, ((w - size[0]) // 2, h // 2 - 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, _ACCENT, 2, cv2.LINE_AA,
        )

        again_button = Button((w // 2 - 190, h // 2, w // 2 - 10, h // 2 + 40), "Cadastrar outra")
        exit_button = Button((w // 2 + 10, h // 2, w // 2 + 190, h // 2 + 40), "Sair")
        again_button.draw(canvas)
        exit_button.draw(canvas)

        if again_button.contains(self._mouse_click):
            self._name = ""
            self._embeddings = []
            self._status_message = ""
            self._state = self.STATE_NAME
        elif exit_button.contains(self._mouse_click):
            self._should_close = True

    # ── Utilidades ────────────────────────────────────────────────────────

    def _darken(self, canvas: np.ndarray) -> None:
        overlay = np.full_like(canvas, _OVERLAY_BG)
        cv2.addWeighted(overlay, 0.6, canvas, 0.4, 0, dst=canvas)

    def _handle_key(self, key: int) -> None:
        if key == 27:  # Esc
            self._should_close = True
            return
        if self._state == self.STATE_NAME:
            self._handle_name_key(key)


def main() -> None:
    EnrollUI().run()


if __name__ == "__main__":
    main()
