// ============================================================
//  replay.js — Browser-based session replay player
// ============================================================

const COLORS = {
    bg: '#0f172a',
    bgCard: '#1e293b',
    bgCanvas: '#0f172a',
    grid: '#1e293b',
    boardOutline: '#334155',
    boardFill: '#1e293b',
    cross: '#f85149',
    textDim: '#475569',
    textPrimary: '#f1f5f9',
    sensors: ['#38bdf8', '#fb7185', '#4ade80', '#fbbf24'],
};

const SENSOR_NAMES = ['Haut-Droit', 'Haut-Gauche', 'Bas-Droit', 'Bas-Gauche'];

let samples = [];
let playing = false;
let frameIdx = 0;
let speed = 1.0;
let trail = [];
const TRAIL_LEN = 15;
let animId = null;
let lastFrameTime = 0;

// Board geometry (computed on resize)
let bl, br, bt, bb, bcx, bcy;

const canvas = document.getElementById('replayCanvas');
const ctx = canvas.getContext('2d');
const timeline = document.getElementById('timeline');

// ── Load samples ────────────────────────────────────────────
fetch(`/api/session/${SESSION_ID}/samples`)
    .then(r => r.json())
    .then(data => {
        samples = data;
        timeline.max = Math.max(0, samples.length - 1);
        document.getElementById('frameInfo').textContent = `0 / ${samples.length}`;
        resize();
        if (samples.length > 0) showFrame(0);
    });

// ── Resize ──────────────────────────────────────────────────
function resize() {
    const wrap = canvas.parentElement;
    canvas.width = wrap.clientWidth;
    canvas.height = wrap.clientHeight;
    computeBoard();
    if (samples.length > 0) showFrame(frameIdx);
}
window.addEventListener('resize', resize);

function computeBoard() {
    const cw = canvas.width, ch = canvas.height;
    const margin = 50;
    const availW = cw - 2 * margin;
    const availH = ch - 2 * margin;
    const ratio = BOARD_W / BOARD_H;

    let bw, bh;
    if (availW / availH > ratio) {
        bh = availH; bw = bh * ratio;
    } else {
        bw = availW; bh = bw / ratio;
    }
    bcx = cw / 2; bcy = ch / 2;
    bl = bcx - bw / 2; br = bcx + bw / 2;
    bt = bcy - bh / 2; bb = bcy + bh / 2;
}

// ── Drawing ─────────────────────────────────────────────────
function drawBoard() {
    const cw = canvas.width, ch = canvas.height;
    ctx.fillStyle = COLORS.bgCanvas;
    ctx.fillRect(0, 0, cw, ch);

    // Board fill
    ctx.fillStyle = COLORS.boardFill;
    ctx.fillRect(bl, bt, br - bl, bb - bt);

    // Grid
    const nCols = BOARD_W / 5;
    const nRows = BOARD_H / 5;
    const stepX = (br - bl) / nCols;
    const stepY = (bb - bt) / nRows;

    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 1;
    for (let i = 1; i < nCols; i++) {
        const gx = bl + i * stepX;
        ctx.beginPath(); ctx.moveTo(gx, bt); ctx.lineTo(gx, bb); ctx.stroke();
    }
    for (let i = 1; i < nRows; i++) {
        const gy = bt + i * stepY;
        ctx.beginPath(); ctx.moveTo(bl, gy); ctx.lineTo(br, gy); ctx.stroke();
    }

    // Center dashes
    ctx.strokeStyle = COLORS.boardOutline;
    ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(bcx, bt); ctx.lineTo(bcx, bb); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(bl, bcy); ctx.lineTo(br, bcy); ctx.stroke();
    ctx.setLineDash([]);

    // Outline
    ctx.strokeStyle = COLORS.boardOutline;
    ctx.lineWidth = 2;
    ctx.strokeRect(bl, bt, br - bl, bb - bt);

    // Corner sensors
    const corners = [
        [br, bt], [bl, bt], [br, bb], [bl, bb]
    ];
    const capR = 12;
    corners.forEach((pos, idx) => {
        ctx.fillStyle = COLORS.sensors[idx];
        ctx.beginPath();
        ctx.arc(pos[0], pos[1], capR, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = COLORS.textPrimary;
        ctx.lineWidth = 1;
        ctx.stroke();

        // Number
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 9px Segoe UI';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(String(idx + 1), pos[0], pos[1]);
    });

    // Dimension labels
    ctx.fillStyle = COLORS.textDim;
    ctx.font = '9px Segoe UI';
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    ctx.fillText(`${BOARD_W} cm`, bcx, bt - 18);
    ctx.textBaseline = 'middle';
    ctx.fillText(`${BOARD_H} cm`, br + 24, bcy);

    ctx.textBaseline = 'top';
    ctx.fillText('Gauche                    Droite', bcx, bb + 12);
}

function drawSensorValues(weights) {
    const corners = [[br, bt], [bl, bt], [br, bb], [bl, bb]];
    ctx.font = '9px Consolas';
    ctx.textBaseline = 'middle';
    corners.forEach((pos, idx) => {
        const txOff = (idx % 2 === 0) ? -28 : 28;
        const tyOff = (idx < 2) ? -18 : 18;
        ctx.fillStyle = COLORS.sensors[idx];
        ctx.textAlign = 'center';
        ctx.fillText((weights[idx] / 1000).toFixed(2) + ' kg', pos[0] + txOff, pos[1] + tyOff);
    });
}

function drawTrailAndCross(xPos, yPos) {
    // Trail
    const bgRgb = hexToRgb(COLORS.bgCanvas);
    const crRgb = hexToRgb(COLORS.cross);
    trail.forEach((pt, i) => {
        if (i >= trail.length - 1) return;
        const alpha = i / TRAIL_LEN;
        const r = Math.round(bgRgb[0] + (crRgb[0] - bgRgb[0]) * alpha);
        const g = Math.round(bgRgb[1] + (crRgb[1] - bgRgb[1]) * alpha);
        const b = Math.round(bgRgb[2] + (crRgb[2] - bgRgb[2]) * alpha);
        const sz = 1.5 + alpha * 3;
        ctx.fillStyle = `rgb(${r},${g},${b})`;
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], sz, 0, Math.PI * 2);
        ctx.fill();
    });

    // Cross
    const cs = 14;
    ctx.strokeStyle = COLORS.cross;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(xPos - cs, yPos); ctx.lineTo(xPos + cs, yPos); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(xPos, yPos - cs); ctx.lineTo(xPos, yPos + cs); ctx.stroke();

    // Label
    ctx.fillStyle = COLORS.cross;
    ctx.font = 'bold 9px Segoe UI';
    ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
    ctx.fillText('CoM', xPos, yPos - cs - 4);
}

// ── Frame display ───────────────────────────────────────────
function showFrame(idx) {
    if (idx < 0 || idx >= samples.length) return;
    frameIdx = idx;
    timeline.value = idx;

    const s = samples[idx];
    const weights = [s.w0, s.w1, s.w2, s.w3];
    const total = weights.reduce((a, b) => a + b, 0);

    // Update sidebar
    document.getElementById('w0').textContent = (weights[0] / 1000).toFixed(3) + ' kg';
    document.getElementById('w1').textContent = (weights[1] / 1000).toFixed(3) + ' kg';
    document.getElementById('w2').textContent = (weights[2] / 1000).toFixed(3) + ' kg';
    document.getElementById('w3').textContent = (weights[3] / 1000).toFixed(3) + ' kg';
    document.getElementById('total').textContent = (total / 1000).toFixed(3) + ' kg';
    document.getElementById('coords').textContent =
        `X: ${(s.cx * 100).toFixed(1)}%  Y: ${(s.cy * 100).toFixed(1)}%`;
    document.getElementById('timeInfo').textContent = (s.t / 1000).toFixed(3) + ' s';
    document.getElementById('frameInfo').textContent = `${idx + 1} / ${samples.length}`;

    // Compute CoM position
    let xPos, yPos;
    if (total > 1) {
        xPos = bcx + s.cx * (br - bl) / 2;
        yPos = bcy + s.cy * (bb - bt) / 2;
        xPos = Math.max(bl, Math.min(br, xPos));
        yPos = Math.max(bt, Math.min(bb, yPos));
    } else {
        xPos = bcx; yPos = bcy;
    }

    trail.push([xPos, yPos]);
    if (trail.length > TRAIL_LEN) trail = trail.slice(-TRAIL_LEN);

    // Draw everything
    drawBoard();
    drawSensorValues(weights);
    drawTrailAndCross(xPos, yPos);
}

// ── Playback controls ───────────────────────────────────────
function togglePlay() {
    if (playing) {
        playing = false;
        document.getElementById('btnPlay').textContent = 'PLAY';
        document.getElementById('btnPlay').style.background = 'var(--accent-teal)';
        if (animId) { cancelAnimationFrame(animId); animId = null; }
    } else {
        if (frameIdx >= samples.length - 1) { frameIdx = 0; trail = []; }
        playing = true;
        document.getElementById('btnPlay').textContent = 'PAUSE';
        document.getElementById('btnPlay').style.background = 'var(--accent-amber)';
        lastFrameTime = performance.now();
        playStep();
    }
}

function playStep() {
    if (!playing || frameIdx >= samples.length - 1) {
        playing = false;
        document.getElementById('btnPlay').textContent = 'PLAY';
        document.getElementById('btnPlay').style.background = 'var(--accent-teal)';
        return;
    }

    const now = performance.now();
    const currT = samples[frameIdx].t;
    const nextT = samples[frameIdx + 1].t;
    const neededDelay = (nextT - currT) / speed;

    if (now - lastFrameTime >= neededDelay) {
        showFrame(frameIdx);
        frameIdx++;
        lastFrameTime = now;
    }

    animId = requestAnimationFrame(playStep);
}

function setSpeed(s) {
    speed = s;
    document.querySelectorAll('.speed-btns button').forEach(b => {
        b.classList.toggle('active', parseFloat(b.textContent) === s);
    });
}

function seek(idx) {
    trail = [];
    showFrame(parseInt(idx));
}

function onSlider(val) {
    if (!playing) {
        trail = [];
        showFrame(parseInt(val));
    }
}

// ── Utility ─────────────────────────────────────────────────
function hexToRgb(h) {
    h = h.replace('#', '');
    return [parseInt(h.substr(0, 2), 16),
            parseInt(h.substr(2, 2), 16),
            parseInt(h.substr(4, 2), 16)];
}
