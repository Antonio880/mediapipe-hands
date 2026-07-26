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

const gearBtn      = document.getElementById("gear-btn");
const controlPanel = document.getElementById("control-panel");
const waveformSel   = document.getElementById("waveform");
const playModeBtns  = document.querySelectorAll(".segmented__btn");
const volumeSlider   = document.getElementById("volume");
const volumeVal      = document.getElementById("volume-val");
const reverbSlider   = document.getElementById("reverb");
const reverbVal      = document.getElementById("reverb-val");
const releaseSlider  = document.getElementById("release");
const releaseVal     = document.getElementById("release-val");

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

/* ---------- Escala de melodia (modo Melodia) ----------
   Posição X da mão → nota quantizada nesta escala (Dó maior, 2 oitavas).
   Da esquerda para a direita da tela = grave para agudo.            */
const MELODY_SCALE = [
  "C4", "D4", "E4", "F4", "G4", "A4", "B4",
  "C5", "D5", "E5", "F5", "G5", "A5", "B5", "C6",
];
const PT_PITCH = { C: "Dó", D: "Ré", E: "Mi", F: "Fá", G: "Sol", A: "Lá", B: "Si" };
function noteToPt(note) {
  return PT_PITCH[note[0]] + note.slice(1);
}

/* ---------- Estado ---------- */
let audioReady   = false;
let mode         = "chords";          // "chords" | "notes" | "melody"
let playMode     = "trigger";         // "trigger" (dedilha) | "pad" (sustenta) — só modos chords/notes

// Debounce por estabilidade de frames + memória do último gesto tocado
const STABLE_FRAMES = 3;              // frames iguais necessários p/ disparar
let candidateCount  = -1;
let stableFrames    = 0;
let lastPlayed      = -1;
let heldNotes       = [];             // notas atualmente sustentadas (modo pad)

// Estado de pinça por mão, exclusivo do modo Melodia (sem debounce: resposta imediata)
const pinchState = {
  Left:  { pinched: false, note: null },
  Right: { pinched: false, note: null },
};

/* ---------- Áudio (Tone.js) ---------- */
let synth, reverb;

function setupAudio() {
  reverb = new Tone.Reverb({ decay: 1.8, wet: 0.28 }).toDestination();
  synth = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: "triangle" },
    envelope: { attack: 0.02, decay: 0.18, sustain: 0.35, release: 0.9 },
  }).connect(reverb);
  synth.volume.value = -11;           // headroom para acordes

  // Sincroniza o motor com os valores atuais do painel de controles
  synth.set({ oscillator: { type: waveformSel.value } });
  const releaseSeconds = Number(releaseSlider.value) / 100;
  synth.set({ envelope: { release: releaseSeconds } });
  const volPct = Number(volumeSlider.value) / 100;
  synth.volume.value = volPct === 0 ? -Infinity : Tone.gainToDb(volPct) - 4;
  reverb.wet.value = Number(reverbSlider.value) / 100;
}

function releaseHeldNotes() {
  if (audioReady && synth && heldNotes.length) {
    synth.triggerRelease(heldNotes);
  }
  heldNotes = [];
}

function playForCount(count) {
  const chord = SCALE[count];

  if (!chord) {                       // 0 dedos → silêncio, solta o que estiver preso
    releaseHeldNotes();
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
    if (playMode === "pad") {
      // Sustenta: solta o acorde anterior e ataca o novo, sem soltar ainda
      releaseHeldNotes();
      synth.triggerAttack(toPlay);
      heldNotes = toPlay;
    } else {
      // Trigger: dedilhado curto, como tecla solta rápido
      synth.triggerAttackRelease(toPlay, "4n");
    }
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

/* ---------- Modo Melodia: posição da mão = altura, pinça = dedilhar ----------
   Cada mão toca sua própria voz de forma independente: mova para escolher
   a nota (quantizada, sempre afinada) e feche o polegar contra o indicador
   para dedilhar. Sem debounce — a resposta é imediata, como uma corda. */
function isPinched(landmarks) {
  const wrist = landmarks[0], middleMcp = landmarks[9];
  const handSize = distance(wrist, middleMcp) || 0.001;
  const pinchDist = distance(landmarks[4], landmarks[8]) / handSize;
  return pinchDist < 0.55;
}

function melodyNoteForX(displayX) {
  const idx = Math.min(
    MELODY_SCALE.length - 1,
    Math.max(0, Math.floor(displayX * MELODY_SCALE.length))
  );
  return MELODY_SCALE[idx];
}

function handleMelodyHand(label, landmarks) {
  // x normalizado (0–1) da ponta do indicador; corrigido para a tela espelhada
  const displayX = 1 - landmarks[8].x;
  const note = melodyNoteForX(displayX);
  const st = pinchState[label];
  const pinched = isPinched(landmarks);

  if (pinched && !st.pinched) {
    if (audioReady && synth) synth.triggerAttack(note);
    st.pinched = true;
    st.note = note;
  } else if (pinched && st.pinched && note !== st.note) {
    // deslizou para outra nota mantendo a pinça: troca sem soltar o gesto
    if (audioReady && synth) { synth.triggerRelease(st.note); synth.triggerAttack(note); }
    st.note = note;
  } else if (!pinched && st.pinched) {
    if (audioReady && synth) synth.triggerRelease(st.note);
    st.pinched = false;
    st.note = null;
  }
}

function releaseMelodyHand(label) {
  const st = pinchState[label];
  if (st.pinched) {
    if (audioReady && synth) synth.triggerRelease(st.note);
    st.pinched = false;
    st.note = null;
  }
}

function updateMelodyHud() {
  const held = ["Left", "Right"].map((l) => pinchState[l]).filter((s) => s.pinched);
  numeralEl.textContent = held.length ? "♪" : "–";
  numeralEl.classList.toggle("silent", held.length === 0);
  chordNameEl.textContent = held.length
    ? held.map((s) => noteToPt(s.note)).join(" + ")
    : "Melodia";
  chordNotesEl.textContent = "una polegar e indicador para dedilhar";
}

function drawMelodyGuides() {
  const n = MELODY_SCALE.length;
  const w = canvas.width, h = canvas.height;
  ctx.save();
  ctx.font = "600 12px 'IBM Plex Mono', monospace";
  ctx.textAlign = "center";
  for (let i = 0; i < n; i++) {
    const xLine = (i / n) * w;
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.beginPath();
    ctx.moveTo(xLine, 0);
    ctx.lineTo(xLine, h);
    ctx.stroke();
    ctx.fillStyle = "rgba(238,241,248,0.5)";
    ctx.fillText(noteToPt(MELODY_SCALE[i]), (i + 0.5) / n * w, 18);
  }
  ctx.restore();
}


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
  const seenLabels = new Set();

  if (results.multiHandLandmarks && results.multiHandLandmarks.length) {
    for (let i = 0; i < results.multiHandLandmarks.length; i++) {
      const lm = results.multiHandLandmarks[i];
      const label = results.multiHandedness[i].label; // "Left" | "Right"
      seenLabels.add(label);

      drawConnectors(ctx, lm, HAND_CONNECTIONS, { color: "#38f0e0", lineWidth: 3 });
      drawLandmarks(ctx, lm, { color: "#ff4d8d", lineWidth: 1, radius: 3.5 });

      if (mode === "melody") {
        handleMelodyHand(label, lm);
      } else {
        const c = countFingers(lm, label);
        total += c;
        // O canvas exibe a imagem espelhada (efeito selfie), mas o rótulo
        // "Left"/"Right" do MediaPipe se refere à mão real, não-espelhada.
        // Por isso invertemos aqui só a atribuição do HUD (esquerda/direita
        // na tela), mantendo o rótulo original para a lógica do polegar.
        if (label === "Left") right = c; else left = c;
      }
    }
  }

  // Mão que saiu do quadro no modo melodia deve soltar a nota dedilhada
  if (mode === "melody") {
    ["Left", "Right"].forEach((l) => { if (!seenLabels.has(l)) releaseMelodyHand(l); });
  }

  ctx.restore();                      // desfaz o espelhamento antes de desenhar texto de UI
  if (mode === "melody") drawMelodyGuides();

  // Leitura ao vivo (independente do disparo de áudio)
  leftEl.textContent  = left;
  rightEl.textContent = right;
  totalEl.textContent = total;

  if (mode === "melody") {
    updateMelodyHud();
  } else {
    handleGesture(total);
  }
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

/* ---------- Alternar modo (acordes / notas / melodia) ---------- */
modeBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    modeBtns.forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    const next = btn.dataset.mode;

    if (mode === "melody" && next !== "melody") {
      ["Left", "Right"].forEach(releaseMelodyHand);
    }
    if (mode !== "melody" && next === "melody") {
      releaseHeldNotes();
      lastPlayed = -1;
    }

    mode = next;
    legendEl.classList.toggle("is-hidden", mode === "melody");

    if (mode === "melody") {
      updateMelodyHud();
    } else if (lastPlayed > 0) {
      // Re-emite o gesto atual para atualizar o rótulo (notas x acordes)
      playForCount(lastPlayed);
    }
  });
});

/* ---------- Painel de ajustes (drivers do synth) ---------- */
gearBtn.addEventListener("click", () => {
  const open = controlPanel.classList.toggle("is-open");
  gearBtn.setAttribute("aria-expanded", String(open));
  controlPanel.setAttribute("aria-hidden", String(!open));
});

waveformSel.addEventListener("change", () => {
  if (synth) synth.set({ oscillator: { type: waveformSel.value } });
});

playModeBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    playModeBtns.forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    const next = btn.dataset.playMode;
    // Trocar de pad para trigger deve soltar qualquer nota presa
    if (playMode === "pad" && next === "trigger") releaseHeldNotes();
    playMode = next;
  });
});

volumeSlider.addEventListener("input", () => {
  volumeVal.textContent = volumeSlider.value;
  if (synth) {
    // 0–100% mapeado para -40dB (quase mudo) até 0dB
    const pct = Number(volumeSlider.value) / 100;
    synth.volume.value = pct === 0 ? -Infinity : Tone.gainToDb(pct) - 4;
  }
});

reverbSlider.addEventListener("input", () => {
  reverbVal.textContent = reverbSlider.value;
  if (reverb) reverb.wet.value = Number(reverbSlider.value) / 100;
});

releaseSlider.addEventListener("input", () => {
  const seconds = Number(releaseSlider.value) / 100;
  releaseVal.textContent = seconds.toFixed(2);
  if (synth) synth.set({ envelope: { release: seconds } });
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
