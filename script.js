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
const transposeSlider = document.getElementById("transpose");
const transposeVal    = document.getElementById("transpose-val");

/* ---------- Nomes de notas em português ---------- */
const PT_PITCH = { C: "Dó", D: "Ré", E: "Mi", F: "Fá", G: "Sol", A: "Lá", B: "Si" };
const KEY_NAMES_PT = ["Dó","Dó♯","Ré","Ré♯","Mi","Fá","Fá♯","Sol","Sol♯","Lá","Lá♯","Si"];

function noteToPt(note) {
  const m = note.match(/^([A-G])(#{1,2}|b{1,2})?(-?\d+)$/);
  if (!m) return note;
  const [, letter, accidental, octave] = m;
  const acc = accidental ? accidental.replace(/#/g, "♯").replace(/b/g, "♭") : "";
  return PT_PITCH[letter] + acc + octave;
}

/* ---------- Escala: nº de dedos de UMA mão → grau/acorde (Dó maior) ----------
   Cada mão é independente: 1 dedo na direita = grau I, 2 dedos na
   esquerda = grau ii, e as duas tocam JUNTAS (nunca somamos as mãos).
   Uma mão só alcança graus 1-5 (I a V) contando dedos — para vi, vii°
   e as oitavas acima, feche o PUNHO da outra mão: isso "destrava" +5
   nos graus da mão que está contando (veja shiftForHand). */
const SCALE = [
  null, // 0 dedos = mão em silêncio
  { numeral: "I",    quality: "Maior", notes: ["C4", "E4", "G4"], root: "C4" },
  { numeral: "ii",   quality: "menor", notes: ["D4", "F4", "A4"], root: "D4" },
  { numeral: "iii",  quality: "menor", notes: ["E4", "G4", "B4"], root: "E4" },
  { numeral: "IV",   quality: "Maior", notes: ["F4", "A4", "C5"], root: "F4" },
  { numeral: "V",    quality: "Maior", notes: ["G4", "B4", "D5"], root: "G4" },
  { numeral: "vi",   quality: "menor", notes: ["A4", "C5", "E5"], root: "A4" },
  { numeral: "vii°", quality: "diminuto", notes: ["B4", "D5", "F5"], root: "B4" },
  { numeral: "I⁸",   quality: "Maior (8ª)", notes: ["C5", "E5", "G5"], root: "C5" },
  { numeral: "ii⁸",  quality: "menor (8ª)", notes: ["D5", "F5", "A5"], root: "D5" },
  { numeral: "iii⁸", quality: "menor (8ª)", notes: ["E5", "G5", "B5"], root: "E5" },
];

/* ---------- Escala de melodia (modo Melodia) ----------
   Posição X da mão → nota quantizada nesta escala (Dó maior, 2 oitavas).
   Da esquerda para a direita da tela = grave para agudo.            */
const MELODY_SCALE = [
  "C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5",
];

/* ---------- Estado ---------- */
let audioReady   = false;
let mode         = "chords";          // "chords" | "notes" | "melody"
let playMode     = "trigger";         // "trigger" (dedilha) | "pad" (sustenta) — chords/notes
let transpose    = 0;                 // semitons, -12..+12 — afeta todos os modos

const STABLE_FRAMES = 3;              // frames iguais necessários p/ disparar (debounce)

// Estado por mão no modo Acordes/Notas
const handChordState = {
  Left:  { candidate: -1, stable: 0, lastPlayed: -1, heldNotes: [] },
  Right: { candidate: -1, stable: 0, lastPlayed: -1, heldNotes: [] },
};

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

  // Sincroniza o motor com os valores atuais do painel de controles
  synth.set({ oscillator: { type: waveformSel.value } });
  const releaseSeconds = Number(releaseSlider.value) / 100;
  synth.set({ envelope: { release: releaseSeconds } });
  const volPct = Number(volumeSlider.value) / 100;
  synth.volume.value = volPct === 0 ? -Infinity : Tone.gainToDb(volPct) - 4;
  reverb.wet.value = Number(reverbSlider.value) / 100;
}

/* ---------- Transpose ---------- */
// Nota "crua" da escala → nota realmente tocada, deslocada pelo transpose.
function playedNote(rawNote) {
  if (!transpose) return rawNote;
  return Tone.Frequency(rawNote).transpose(transpose).toNote();
}

function transposeLabel(semi) {
  const sign = semi > 0 ? "+" : "";
  const keyIdx = ((semi % 12) + 12) % 12;
  return `${sign}${semi} · ${KEY_NAMES_PT[keyIdx]}`;
}

/* ---------- Modo Acordes / Notas: cada mão é independente ---------- */
function releaseHandNotes(label) {
  const st = handChordState[label];
  if (audioReady && synth && st.heldNotes.length) synth.triggerRelease(st.heldNotes);
  st.heldNotes = [];
}

function pulseNumeral() {
  numeralEl.classList.remove("pulse");
  void numeralEl.offsetWidth;   // reinicia a animação
  numeralEl.classList.add("pulse");
}

function updateChordHud() {
  const active = ["Left", "Right"]
    .map((l) => ({ label: l, count: handChordState[l].lastPlayed }))
    .filter((h) => h.count > 0);

  if (!active.length) {
    numeralEl.textContent = "–";
    numeralEl.classList.add("silent");
    chordNameEl.textContent = "Silêncio";
    chordNotesEl.textContent = "mostre as mãos";
    highlightLegend([]);
    return;
  }

  numeralEl.classList.remove("silent");
  numeralEl.textContent = active.map((h) => SCALE[h.count].numeral).join(" + ");
  chordNameEl.textContent = active
    .map((h) => `${noteToPt(playedNote(SCALE[h.count].root))} ${SCALE[h.count].quality}`)
    .join("   +   ");

  const allNotes = active.flatMap((h) => {
    const raw = mode === "chords" ? SCALE[h.count].notes : [SCALE[h.count].root];
    return raw.map(playedNote);
  });
  chordNotesEl.textContent = allNotes.join(" · ");

  highlightLegend(active.map((h) => h.count));
}

function playForHand(label, count) {
  const st = handChordState[label];
  const chord = SCALE[count];

  if (!chord) {
    releaseHandNotes(label);
    updateChordHud();
    return;
  }

  const rawNotes = mode === "chords" ? chord.notes : [chord.root];
  const notes = rawNotes.map(playedNote);

  if (audioReady && synth) {
    if (playMode === "pad") {
      // Sustenta: solta o que essa mão segurava antes e ataca o novo
      releaseHandNotes(label);
      synth.triggerAttack(notes);
      st.heldNotes = notes;
    } else {
      // Trigger: dedilhado curto, como tecla solta rápido
      synth.triggerAttackRelease(notes, "4n");
    }
  }

  updateChordHud();
  pulseNumeral();
}

function handleHandGesture(label, count) {
  const st = handChordState[label];
  if (count === st.candidate) {
    st.stable++;
  } else {
    st.candidate = count;
    st.stable = 1;
  }
  // Só dispara quando o gesto dessa mão ficou estável E mudou de fato
  if (st.stable === STABLE_FRAMES && st.candidate !== st.lastPlayed) {
    st.lastPlayed = st.candidate;
    playForHand(label, st.candidate);
  }
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
  const note = playedNote(melodyNoteForX(displayX));
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
    ctx.strokeStyle = "rgba(255,255,255,0.22)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(xLine, 0);
    ctx.lineTo(xLine, h);
    ctx.stroke();
    ctx.fillStyle = "rgba(238,241,248,0.5)";
    ctx.fillText(noteToPt(playedNote(MELODY_SCALE[i])), (i + 0.5) / n * w, 18);
  }
  ctx.restore();
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

  let left = 0, right = 0;
  const seenLabels = new Set();
  const rawCount = { Left: null, Right: null }; // null = mão não detectada neste frame

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
        rawCount[label] = countFingers(lm, label);
      }
    }
  }

  if (mode !== "melody") {
    // Punho fechado (0 dedos) numa mão vira um "shift": destrava +5 graus
    // (vi, vii° e as oitavas) na mão que está contando dedos do lado oposto.
    ["Left", "Right"].forEach((label) => {
      const own = rawCount[label];
      const displayCount = own === null ? 0 : own;
      if (label === "Left") right = displayCount; else left = displayCount;

      if (own === null) {                 // mão fora do quadro → silêncio
        handleHandGesture(label, 0);
        return;
      }
      const otherLabel = label === "Left" ? "Right" : "Left";
      const otherIsFist = rawCount[otherLabel] === 0;   // punho fechado, detectado
      const effective = own > 0 && otherIsFist ? own + 5 : own;
      handleHandGesture(label, effective);
    });
  }

  if (mode === "melody") {
    ["Left", "Right"].forEach((l) => { if (!seenLabels.has(l)) releaseMelodyHand(l); });
  }

  ctx.restore();                      // desfaz o espelhamento antes de desenhar texto de UI
  if (mode === "melody") drawMelodyGuides();

  // Leitura ao vivo (independente do disparo de áudio)
  leftEl.textContent  = left;
  rightEl.textContent = right;
  totalEl.textContent = left + right;

  if (mode === "melody") updateMelodyHud();
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
      ["Left", "Right"].forEach((l) => {
        releaseHandNotes(l);
        handChordState[l].lastPlayed = -1;
        handChordState[l].candidate = -1;
        handChordState[l].stable = 0;
      });
    }

    mode = next;
    legendEl.classList.toggle("is-hidden", mode === "melody");
    document.getElementById("legend-hint").classList.toggle("is-hidden", mode === "melody");

    if (mode === "melody") updateMelodyHud();
    else updateChordHud();
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
    // Trocar de pad para trigger deve soltar qualquer nota presa nas duas mãos
    if (playMode === "pad" && next === "trigger") {
      ["Left", "Right"].forEach(releaseHandNotes);
    }
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

transposeSlider.addEventListener("input", () => {
  transpose = Number(transposeSlider.value);
  transposeVal.textContent = transposeLabel(transpose);
  renderLegendNames();
  if (mode === "melody") updateMelodyHud();
  else updateChordHud();
});
transposeVal.textContent = transposeLabel(0);

/* ---------- Legenda dos graus ---------- */
function buildLegend() {
  for (let i = 1; i <= 7; i++) {
    const item = document.createElement("div");
    item.className = "legend__item";
    item.dataset.count = i;
    const numText = i <= 5 ? `${i} ${i === 1 ? "dedo" : "dedos"}` : `${i - 5} + punho`;
    item.innerHTML = `
      <span class="legend__num">${numText}</span>
      <span class="legend__deg">${SCALE[i].numeral}</span>
      <span class="legend__name"></span>`;
    legendEl.appendChild(item);
  }
  renderLegendNames();
}

function renderLegendNames() {
  legendEl.querySelectorAll(".legend__item").forEach((el) => {
    const i = Number(el.dataset.count);
    const chord = SCALE[i];
    el.querySelector(".legend__name").textContent =
      `${noteToPt(playedNote(chord.root))} ${chord.quality}`;
  });
}

function highlightLegend(counts) {
  legendEl.querySelectorAll(".legend__item").forEach((el) => {
    el.classList.toggle("is-active", counts.includes(Number(el.dataset.count)));
  });
}

buildLegend();
