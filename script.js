/* =========================================================
   Aria — instrumento gestual
   Visão (MediaPipe Hands) → contagem de dedos → Tone.js
   ========================================================= */

"use strict";

/* ---------- Elementos ---------- */
const video      = document.getElementById("input-video");
const canvas     = document.getElementById("output-canvas");
const ctx        = canvas.getContext("2d");

const startBtn   = document.getElementById("start-btn");
const cover      = document.getElementById("cover");
const statusEl   = document.getElementById("status");

const numeralEl  = document.getElementById("numeral");
const chordNameEl= document.getElementById("chord-name");
const chordNotesEl = document.getElementById("chord-notes");

const leftEl     = document.getElementById("left-count");
const rightEl    = document.getElementById("right-count");
const totalEl    = document.getElementById("total-count");

const legendEl   = document.getElementById("legend");
const modeBtns   = document.querySelectorAll(".mode__btn");

/* ---------- Escala: nº de dedos → grau / acorde (Dó maior) ----------
   Índice do array = total de dedos levantados (0 a 10).            */
const SCALE = [
  null, // 0 dedos = silêncio
  { numeral: "I",   name: "Dó Maior",        notes: ["C4", "E4", "G4"], root: "C4" },
  { numeral: "ii",  name: "Ré menor",        notes: ["D4", "F4", "A4"], root: "D4" },
  { numeral: "iii", name: "Mi menor",        notes: ["E4", "G4", "B4"], root: "E4" },
  { numeral: "IV",  name: "Fá Maior",        notes: ["F4", "A4", "C5"], root: "F4" },
  { numeral: "V",   name: "Sol Maior",       notes: ["G4", "B4", "D5"], root: "G4" },
  { numeral: "vi",  name: "Lá menor",        notes: ["A4", "C5", "E5"], root: "A4" },
  { numeral: "vii°",name: "Si diminuto",     notes: ["B4", "D5", "F5"], root: "B4" },
  { numeral: "I⁸",  name: "Dó Maior (8ª)",   notes: ["C5", "E5", "G5"], root: "C5" },
  { numeral: "ii⁸", name: "Ré menor (8ª)",   notes: ["D5", "F5", "A5"], root: "D5" },
  { numeral: "V⁸",  name: "Sol Maior (8ª)",  notes: ["G5", "B5", "D6"], root: "G5" },
];

/* ---------- Estado ---------- */
let audioReady   = false;
let mode         = "chords";          // "chords" | "notes"

// Debounce por estabilidade de frames + memória do último gesto tocado
const STABLE_FRAMES = 3;              // frames iguais necessários p/ disparar
let candidateCount  = -1;
let stableFrames    = 0;
let lastPlayed      = -1;

/* ---------- Áudio (Tone.js) ---------- */
let synth, reverb;

function setupAudio() {
  reverb = new Tone.Reverb({ decay: 1.8, wet: 0.28 }).toDestination();
  synth = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: "triangle" },
    envelope: { attack: 0.02, decay: 0.18, sustain: 0.35, release: 0.9 },
  }).connect(reverb);
  synth.volume.value = -11;           // headroom para acordes
}

function playForCount(count) {
  const chord = SCALE[count];

  if (!chord) {                       // 0 dedos → silêncio visual, nada toca
    numeralEl.textContent = "–";
    numeralEl.classList.add("silent");
    numeralEl.classList.remove("pulse");
    chordNameEl.textContent = "Silêncio";
    chordNotesEl.textContent = "mostre as mãos";
    highlightLegend(0);
    return;
  }

  const toPlay = mode === "chords" ? chord.notes : [chord.root];
  if (audioReady && synth) {
    synth.triggerAttackRelease(toPlay, "4n");
  }

  // HUD
  numeralEl.textContent = chord.numeral;
  numeralEl.classList.remove("silent");
  chordNameEl.textContent = chord.name;
  chordNotesEl.textContent = toPlay.join(" · ");

  // pulso de "ataque"
  numeralEl.classList.remove("pulse");
  void numeralEl.offsetWidth;         // reinicia a animação
  numeralEl.classList.add("pulse");

  highlightLegend(count);
}

/* ---------- Debounce de gestos ---------- */
function handleGesture(totalCount) {
  if (totalCount === candidateCount) {
    stableFrames++;
  } else {
    candidateCount = totalCount;
    stableFrames = 1;
  }

  // Só dispara quando o gesto se manteve estável E mudou de fato
  if (stableFrames === STABLE_FRAMES && candidateCount !== lastPlayed) {
    lastPlayed = candidateCount;
    playForCount(candidateCount);
  }
}

/* ---------- Contagem de dedos ----------
   4 dedos (indicador→mínimo): ponta mais longe do pulso que a junta PIP
   (invariante à rotação da mão).
   Polegar: comparação em x relativa à junta IP, com direção pela mão. */
function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function countFingers(landmarks, handedness) {
  const wrist = landmarks[0];
  let count = 0;

  // Polegar (4=ponta, 3=IP). MediaPipe rotula a mão; a direção do
  // polegar estendido depende disso. Se parecer invertido no seu
  // setup, troque "<" por ">" abaixo.
  const thumbOut =
    handedness === "Right"
      ? landmarks[4].x < landmarks[3].x
      : landmarks[4].x > landmarks[3].x;
  if (thumbOut) count++;

  // Demais dedos: ponta vs junta PIP em relação ao pulso
  const tips = [8, 12, 16, 20];
  const pips = [6, 10, 14, 18];
  for (let i = 0; i < 4; i++) {
    if (distance(landmarks[tips[i]], wrist) > distance(landmarks[pips[i]], wrist)) {
      count++;
    }
  }
  return count;
}

/* ---------- Callback do MediaPipe ---------- */
function onResults(results) {
  // Ajusta o canvas ao tamanho do frame uma única vez
  if (canvas.width !== results.image.width) {
    canvas.width = results.image.width;
    canvas.height = results.image.height;
  }

  ctx.save();
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Espelha (efeito "selfie"): imagem e landmarks juntos
  ctx.translate(canvas.width, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(results.image, 0, 0, canvas.width, canvas.height);

  let total = 0, left = 0, right = 0;

  if (results.multiHandLandmarks && results.multiHandLandmarks.length) {
    for (let i = 0; i < results.multiHandLandmarks.length; i++) {
      const lm = results.multiHandLandmarks[i];
      const label = results.multiHandedness[i].label; // "Left" | "Right"

      drawConnectors(ctx, lm, HAND_CONNECTIONS, { color: "#38f0e0", lineWidth: 3 });
      drawLandmarks(ctx, lm, { color: "#ff4d8d", lineWidth: 1, radius: 3.5 });

      const c = countFingers(lm, label);
      total += c;
      if (label === "Left") left = c; else right = c;
    }
  }

  ctx.restore();

  // Leitura ao vivo (independente do disparo de áudio)
  leftEl.textContent  = left;
  rightEl.textContent = right;
  totalEl.textContent = total;

  handleGesture(total);
}

/* ---------- MediaPipe Hands + câmera ---------- */
const hands = new Hands({
  locateFile: (file) =>
    `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/${file}`,
});
hands.setOptions({
  maxNumHands: 2,
  modelComplexity: 1,
  minDetectionConfidence: 0.7,
  minTrackingConfidence: 0.6,
});
hands.onResults(onResults);

const camera = new Camera(video, {
  onFrame: async () => { await hands.send({ image: video }); },
  width: 1280,
  height: 720,
});

/* ---------- Botão iniciar (libera áudio + câmera) ---------- */
startBtn.addEventListener("click", async () => {
  startBtn.disabled = true;
  try {
    statusEl.textContent = "Liberando áudio…";
    await Tone.start();               // exige gesto do usuário
    setupAudio();
    audioReady = true;

    statusEl.textContent = "Carregando modelo e câmera…";
    await camera.start();             // solicita permissão da webcam

    cover.classList.add("is-hidden");
    statusEl.textContent = "Ativo";
  } catch (err) {
    console.error(err);
    statusEl.textContent = "Erro: " + (err && err.message ? err.message : "não foi possível iniciar");
    startBtn.disabled = false;
  }
});

/* ---------- Alternar modo (acordes / notas) ---------- */
modeBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    modeBtns.forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    mode = btn.dataset.mode;
    // Re-emite o gesto atual para atualizar o rótulo (notas x acordes)
    if (lastPlayed > 0) playForCount(lastPlayed);
  });
});

/* ---------- Legenda dos graus ---------- */
function buildLegend() {
  for (let i = 1; i <= 7; i++) {
    const s = SCALE[i];
    const item = document.createElement("div");
    item.className = "legend__item";
    item.dataset.count = i;
    item.innerHTML = `
      <span class="legend__num">${i} ${i === 1 ? "dedo" : "dedos"}</span>
      <span class="legend__deg">${s.numeral}</span>
      <span class="legend__name">${s.name}</span>`;
    legendEl.appendChild(item);
  }
}

function highlightLegend(count) {
  legendEl.querySelectorAll(".legend__item").forEach((el) => {
    el.classList.toggle("is-active", Number(el.dataset.count) === count);
  });
}

buildLegend();
