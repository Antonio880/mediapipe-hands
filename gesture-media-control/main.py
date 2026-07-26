#!/usr/bin/env python3
"""
Gesture Media Control
=====================
Controla mídia e volume do sistema via gestos de mão usando webcam + MediaPipe.
Roda silenciosamente no terminal, sem abrir janelas gráficas.

Instalação:
    pip install opencv-python mediapipe pynput

Execução normal:
    python main.py

Execução em background (Windows):
    start /B pythonw main.py

Execução em background (Linux/macOS):
    nohup python main.py &

Encerrar: Ctrl+C no terminal (ou fechar o processo se em background)

────────────────────────────────────────────────────────────────
Gestos suportados:
  • Mão na zona SUPERIOR (top 28% do frame) → Volume Up  🔊
  • Mão na zona INFERIOR (bottom 28% do frame) → Volume Down 🔉
  • Mão aberta por 1 segundo → Play/Pause ⏯
  • Deslizar para DIREITA → Próxima faixa ⏭
  • Deslizar para ESQUERDA → Faixa anterior ⏮
────────────────────────────────────────────────────────────────
"""

import cv2
import mediapipe as mp
import time
import sys
from collections import deque
from pynput.keyboard import Key, Controller

# ── Configurações ──────────────────────────────────────────────────────────────
CAMERA_INDEX    = 0       # Índice da webcam (tente 1 se a câmera padrão não funcionar)
FRAME_WIDTH     = 320     # Resolução baixa para economizar CPU
FRAME_HEIGHT    = 240
TARGET_FPS      = 15      # FPS limitado para reduzir carga

DETECTION_CONF  = 0.7     # Confiança mínima de detecção da mão
TRACKING_CONF   = 0.5     # Confiança mínima de rastreamento

GESTURE_COOLDOWN  = 1.5   # Segundos entre ações de gesto (play/pause, swipe)
VOLUME_COOLDOWN   = 0.25  # Segundos entre teclas de volume
OPEN_HAND_HOLD    = 1.0   # Segundos segurando mão aberta para disparar Play/Pause
SWIPE_THRESHOLD   = 0.18  # Delta X normalizado para detectar swipe
SWIPE_WINDOW_SEC  = 0.5   # Janela de tempo (s) para medir o swipe
VOLUME_ZONE       = 0.28  # Fração do frame (top/bottom) que ativa volume

# ── Inicialização ──────────────────────────────────────────────────────────────
keyboard = Controller()

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=DETECTION_CONF,
    min_tracking_confidence=TRACKING_CONF,
)

cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
cap.set(cv2.CAP_PROP_FPS,          TARGET_FPS)

if not cap.isOpened():
    print(f"[ERRO] Não foi possível abrir a webcam (índice {CAMERA_INDEX}).")
    print("       Verifique se a câmera está conectada ou altere CAMERA_INDEX.")
    sys.exit(1)

print("╔══════════════════════════════════════════╗")
print("║      Gesture Media Control  v1.0         ║")
print("╠══════════════════════════════════════════╣")
print("║  Mão CIMA    → Volume Up   🔊            ║")
print("║  Mão BAIXO   → Volume Down 🔉            ║")
print("║  Mão aberta  → Play/Pause  ⏯  (1s)      ║")
print("║  Swipe →     → Próxima     ⏭            ║")
print("║  Swipe ←     → Anterior    ⏮            ║")
print("║  Ctrl+C      → Encerrar                  ║")
print("╚══════════════════════════════════════════╝")

# ── Estado ─────────────────────────────────────────────────────────────────────
last_gesture_time = 0.0
last_volume_time  = 0.0
open_hand_start   = None          # Timestamp de quando a mão foi aberta
wrist_x_history   = deque()       # (timestamp, x_normalizado)

# Índices MediaPipe das pontas e articulações intermediárias dos dedos
FINGER_TIPS = [8, 12, 16, 20]    # Indicador, Médio, Anelar, Mínimo
FINGER_PIPS = [6, 10, 14, 18]

# ── Funções auxiliares ─────────────────────────────────────────────────────────

def count_extended_fingers(lm) -> int:
    """Conta quantos dedos (exceto polegar) estão estendidos."""
    count = 0
    for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
        # Dedo estendido: ponta (tip) está acima da articulação PIP (Y menor = mais alto)
        if lm[tip].y < lm[pip].y:
            count += 1
    return count

def is_open_hand(lm) -> bool:
    """Retorna True se pelo menos 4 dedos estão estendidos (mão aberta)."""
    return count_extended_fingers(lm) >= 4

def send_key(key, label: str):
    """Pressiona e solta uma tecla de mídia e imprime no terminal."""
    keyboard.press(key)
    keyboard.release(key)
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {label}")

# ── Loop principal ─────────────────────────────────────────────────────────────

frame_interval = 1.0 / TARGET_FPS  # Controle manual de FPS

try:
    while True:
        loop_start = time.time()

        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        # Converte BGR → RGB (MediaPipe espera RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results   = hands.process(frame_rgb)
        now       = time.time()

        # Sem mão detectada: reseta estado
        if not results.multi_hand_landmarks:
            open_hand_start = None
            wrist_x_history.clear()
            # Aguarda o próximo frame
            elapsed = time.time() - loop_start
            time.sleep(max(0.0, frame_interval - elapsed))
            continue

        # Pega os landmarks da primeira mão detectada
        lm    = results.multi_hand_landmarks[0].landmark
        wrist = lm[0]  # Landmark 0 = pulso
        wx    = wrist.x   # X normalizado [0.0, 1.0]
        wy    = wrist.y   # Y normalizado [0.0, 1.0] (0 = topo, 1 = base)

        # ── 1. Controle de Volume por Zona ────────────────────────────────────
        # Só dispara com mão FECHADA (≤1 dedo estendido) para não conflitar com Play/Pause
        hand_is_open = is_open_hand(lm)
        if not hand_is_open and now - last_volume_time > VOLUME_COOLDOWN:
            if wy < VOLUME_ZONE:
                send_key(Key.media_volume_up, "Volume UP  🔊")
                last_volume_time = now
            elif wy > (1.0 - VOLUME_ZONE):
                send_key(Key.media_volume_down, "Volume DOWN 🔉")
                last_volume_time = now

        # ── 2. Detecção de Swipe (próxima / anterior) ─────────────────────────
        wrist_x_history.append((now, wx))

        # Remove entradas fora da janela de tempo
        while wrist_x_history and now - wrist_x_history[0][0] > SWIPE_WINDOW_SEC:
            wrist_x_history.popleft()

        if len(wrist_x_history) >= 3 and now - last_gesture_time > GESTURE_COOLDOWN:
            x_start = wrist_x_history[0][1]
            x_end   = wrist_x_history[-1][1]
            delta   = x_end - x_start  # positivo = direita, negativo = esquerda

            if delta > SWIPE_THRESHOLD:
                send_key(Key.media_next, "Próxima faixa  ⏭")
                last_gesture_time = now
                wrist_x_history.clear()

            elif delta < -SWIPE_THRESHOLD:
                send_key(Key.media_previous, "Faixa anterior ⏮")
                last_gesture_time = now
                wrist_x_history.clear()

        # ── 3. Mão Aberta por 1s → Play/Pause ────────────────────────────────
        if hand_is_open:
            if open_hand_start is None:
                open_hand_start = now  # Começa a contar
            elif (now - open_hand_start >= OPEN_HAND_HOLD
                  and now - last_gesture_time > GESTURE_COOLDOWN):
                send_key(Key.media_play_pause, "Play / Pause   ⏯")
                last_gesture_time = now
                open_hand_start   = None  # Reseta para não disparar repetidamente
        else:
            open_hand_start = None  # Mão fechou: cancela contagem

        # Controle de FPS para aliviar CPU
        elapsed = time.time() - loop_start
        time.sleep(max(0.0, frame_interval - elapsed))

except KeyboardInterrupt:
    print("\n[INFO] Encerrando...")

finally:
    cap.release()
    hands.close()
    print("[INFO] Webcam liberada.")
