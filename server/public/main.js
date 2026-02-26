const displayContainer = document.getElementById('cube-grid');
const statusDiv = document.getElementById('status');
const programSelect = document.getElementById('programSelect');
const runBtn = document.getElementById('runBtn');
const idleBtn = document.getElementById('idleBtn');
const displayDiv = document.getElementById('display');
const gridArea = document.querySelector('.grid-area');
const snakeControls = document.getElementById('snakeControls');
const snakeScore = document.getElementById('snakeScore');
const workloadLabel = document.querySelector('.workload-label');
const speedLabel = document.querySelector('.speed-label');
const programTools = document.getElementById('programTools');
const viewSourceBtn = document.getElementById('viewSourceBtn');
const sourceOverlay = document.getElementById('sourceOverlay');
const closeSourceBtn = document.getElementById('closeSourceBtn');
const sourceTitle = document.getElementById('sourceTitle');
const sourceCode = document.getElementById('sourceCode');
const sourceCodePre = document.querySelector('.source-pre');

function setSliderVisibility(visible) {
    // Use visibility (not display) so sliders always reserve their space
    // and toggling them never shifts the grid position.
    const v = visible ? 'visible' : 'hidden';
    if (workloadLabel) workloadLabel.style.visibility = v;
    if (speedLabel) speedLabel.style.visibility = v;
}

function setProgramToolsVisibility(visible) {
    if (!programTools) return;
    programTools.style.visibility = visible ? 'visible' : 'hidden';
    programTools.style.pointerEvents = visible ? 'auto' : 'none';
}

function setRunButtonVisibility(visible) {
    if (!runBtn) return;
    runBtn.style.visibility = visible ? 'visible' : 'hidden';
    runBtn.style.pointerEvents = visible ? 'auto' : 'none';
}

const NUM_CUBES_X = 2;
const NUM_CUBES_Y = 2;
const LED_COLS_PER_CUBE = 16;
const LED_ROWS_PER_CUBE = 32;

let isDrawing = false;
let lastLedElement = null;
let currentPrograms = [];
let currentState = 'idle';
let currentProgramId = null;

// --- Probability Control ---
const probabilitySlider = document.getElementById('probabilitySlider');
const probabilityValue = document.getElementById('probabilityValue');

// Update probability display and send to server
function updateProbability() {
    const probability = probabilitySlider.value;
    probabilityValue.textContent = `${probability}%`;
    sendControlMessage({
        type: 'probability',
        value: probability / 100.0  // Convert to 0.0-1.0 range
    });
}

probabilitySlider.addEventListener('input', updateProbability);

// --- Speed Control ---
const speedSlider = document.getElementById('speedSlider');
const speedValue = document.getElementById('speedValue');

// Update speed display and send to server
function updateSpeed() {
    const speed = speedSlider.value;
    speedValue.textContent = `${speed}ms`;
    sendControlMessage({
        type: 'speed',
        value: speed / 1000.0  // Convert to seconds
    });
}

speedSlider.addEventListener('input', updateSpeed);

// Safe WebSocket open-state constant (some portal browsers don't expose WebSocket globally)
const WS_OPEN = (typeof WebSocket !== 'undefined') ? WebSocket.OPEN : 1;
const WS_RETRY_MS = 1500;
const HTTP_POLL_MS = 1200;

// --- WebSocket Connection ---
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
let ws = null;
let wsReconnectTimer = null;
let statePollTimer = null;
let usingHttpFallback = false;
let knownProgramSignature = '';

function setStatus(text, bg) {
    statusDiv.textContent = text;
    statusDiv.style.background = bg;
}

function programSignature(programs) {
    return JSON.stringify((programs || []).map((p) => `${p.id}:${p.type}:${p.name}`));
}

function applyProgramList(programs) {
    const sig = programSignature(programs);
    if (sig !== knownProgramSignature) {
        currentPrograms = programs || [];
        renderProgramList();
        knownProgramSignature = sig;
    } else {
        currentPrograms = programs || currentPrograms;
    }
}

function handleServerMessage(data) {
    if (!data || typeof data !== 'object') return;
    if (data.type === 'init') {
        applyProgramList(data.programs || []);
        updateActiveState(data.state, data.program);
    } else if (data.type === 'state') {
        updateActiveState(data.state, data.program);
    } else if (data.type === 'score') {
        snakeScore.textContent = data.value;
    }
}

async function pollStateOnce() {
    try {
        const resp = await fetch('/api/state', { cache: 'no-store' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        applyProgramList(data.programs || []);
        updateActiveState(data.state, data.program);
        if (usingHttpFallback) setStatus('Connected (HTTP)', '#27ae60');
    } catch {
        if (usingHttpFallback) setStatus('Disconnected', '#c0392b');
    }
}

function startStatePolling() {
    if (statePollTimer) return;
    usingHttpFallback = true;
    pollStateOnce();
    statePollTimer = setInterval(pollStateOnce, HTTP_POLL_MS);
}

function stopStatePolling() {
    if (!statePollTimer) return;
    clearInterval(statePollTimer);
    statePollTimer = null;
}

function scheduleWsReconnect() {
    if (wsReconnectTimer) return;
    wsReconnectTimer = setTimeout(() => {
        wsReconnectTimer = null;
        connectWebSocket();
    }, WS_RETRY_MS);
}

function connectWebSocket() {
    if (typeof WebSocket === 'undefined') {
        startStatePolling();
        setStatus('Connected (HTTP)', '#27ae60');
        return;
    }

    try {
        ws = new WebSocket(`${protocol}://${window.location.host}`);
    } catch {
        startStatePolling();
        setStatus('Connected (HTTP)', '#27ae60');
        return;
    }

    ws.onopen = () => {
        usingHttpFallback = false;
        stopStatePolling();
        setStatus('Connected', '#27ae60');
        if (probabilitySlider) updateProbability();
        if (speedSlider) updateSpeed();
    };
    ws.onclose = () => {
        setStatus('Reconnecting...', '#e67e22');
        scheduleWsReconnect();
        startStatePolling();
    };
    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
    ws.onmessage = (event) => {
        let data;
        try { data = JSON.parse(event.data); } catch { return; }
        handleServerMessage(data);
    };
}

async function sendControlMessage(payload) {
    if (ws && ws.readyState === WS_OPEN) {
        ws.send(JSON.stringify(payload));
        return true;
    }
    try {
        const resp = await fetch('/api/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            cache: 'no-store',
            body: JSON.stringify(payload),
        });
        if (!resp.ok) return false;
        const out = await resp.json().catch(() => null);
        if (out && out.state) {
            updateActiveState(out.state, out.program);
        }
        return true;
    } catch {
        return false;
    }
}

// --- Program Selector ---
function renderProgramList() {
    programSelect.innerHTML = '';
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = '-- choose program to run --';
    programSelect.appendChild(placeholder);

    for (const prog of currentPrograms) {
        if (prog.id === 'idle') continue; // idle has its own button
        const opt = document.createElement('option');
        opt.value = prog.id;
        opt.textContent = prog.name;
        if (prog.type === 'cstar') opt.textContent = '🗄️ ' + prog.name;
        programSelect.appendChild(opt);
    }
    programSelect.value = '';
}

runBtn.addEventListener('click', () => {
    const id = programSelect.value;
    if (id) sendControlMessage({ type: 'run_program', id });
});

idleBtn.addEventListener('click', () => {
    sendControlMessage({ type: 'run_program', id: 'idle' });
    // Immediately restore idle UI and reset dropdown
    gridArea.style.display = '';
    snakeControls.style.display = 'none';
    setSliderVisibility(true);
    setProgramToolsVisibility(false);
    hideSourceOverlay();
    // Reset dropdown so no previous program appears selected in idle
    programSelect.value = '';
});

programSelect.addEventListener('change', () => {
    // Show snake controls as soon as snake is selected (pre-run preview)
    const showSnake = (programSelect.value === 'snake');
    gridArea.style.display = showSnake ? 'none' : '';
    snakeControls.style.display = showSnake ? 'flex' : 'none';
    updateActiveState(currentState, currentProgramId);
});

function updateActiveState(state, programId) {
    currentState = state;
    currentProgramId = programId;

    // Update button states
    idleBtn.classList.toggle('active', state === 'idle');
    runBtn.classList.toggle('active', state === 'program');

    // Sync dropdown to the running program
    if (state === 'program' && programId) {
        programSelect.value = programId;
    }

    // UI mode:
    // - running program -> source button visible, sliders hidden
    // - idle + selected program (preview) -> source button visible, sliders hidden
    // - otherwise (idle without selection or drawing) -> sliders visible
    const selectedProgramId = programSelect.value || '';
    const effectiveProgramId = (state === 'program' && programId) ? programId : selectedProgramId;
    const showProgramTools = !!effectiveProgramId;
    const showSliders = !showProgramTools && (state === 'idle' || state === 'drawing');
    setSliderVisibility(showSliders);
    setProgramToolsVisibility(showProgramTools);
    setRunButtonVisibility(state === 'idle');
    if (!showProgramTools) hideSourceOverlay();

    // Toggle snake UI vs normal display
    // Only show when snake is actively running, or pre-selected in idle
    const isSnake = (state === 'program' && programId === 'snake');
    const previewSnake = (state === 'idle' && programSelect.value === 'snake');
    const showSnake = isSnake || previewSnake;
    gridArea.style.display = showSnake ? 'none' : '';
    snakeControls.style.display = showSnake ? 'flex' : 'none';
    if (isSnake) snakeScore.textContent = '0';
}

function getProgramMetaById(id) {
    return currentPrograms.find((p) => p.id === id) || null;
}

function showSourceOverlay() {
    sourceOverlay.classList.remove('hidden');
    sourceOverlay.setAttribute('aria-hidden', 'false');
}

function hideSourceOverlay() {
    sourceOverlay.classList.add('hidden');
    sourceOverlay.setAttribute('aria-hidden', 'true');
}

async function loadSelectedProgramSource() {
    const selectedId = (currentState === 'program' && currentProgramId)
        ? currentProgramId
        : (programSelect.value || '');
    if (!selectedId) return;

    const meta = getProgramMetaById(selectedId);
    sourceTitle.textContent = `Source: ${meta ? meta.name : selectedId}`;
    sourceCode.textContent = 'Loading...';
    sourceCode.removeAttribute('data-lang');
    sourceCodePre.classList.remove('lang-python', 'lang-cstar');
    showSourceOverlay();

    try {
        const resp = await fetch(`/api/program-source/${encodeURIComponent(selectedId)}`);
        if (!resp.ok) {
            const errJson = await resp.json().catch(() => ({}));
            throw new Error(errJson.error || `HTTP ${resp.status}`);
        }
        const payload = await resp.json();
        sourceTitle.textContent = `Source: ${payload.name}`;
        sourceCode.innerHTML = highlightCode(payload.source || '', payload.type);
        sourceCode.setAttribute('data-lang', payload.type || '');
        sourceCodePre.classList.remove('lang-python', 'lang-cstar');
        if (payload.type === 'python') sourceCodePre.classList.add('lang-python');
        if (payload.type === 'cstar') sourceCodePre.classList.add('lang-cstar');
    } catch (err) {
        sourceCode.textContent = `Failed to load source.\n${err.message}`;
    }
}

function escapeHtml(s) {
    return s
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
}

function highlightCode(source, type) {
    const keywords = type === 'python'
        ? /\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b/g
        : /\b(float|int|if|else|while|for|return)\b/g;
    const constants = /\b[0-9]+(?:\.[0-9]+)?\b/g;

    const src = source || '';
    const lines = src.split('\n');
    const out = [];

    for (const line of lines) {
        const commentPos = type === 'python' ? line.indexOf('#') : line.indexOf('//');
        let codePart = line;
        let commentPart = '';
        if (commentPos >= 0) {
            codePart = line.slice(0, commentPos);
            commentPart = line.slice(commentPos);
        }

        const tokenized = [];
        let i = 0;
        while (i < codePart.length) {
            const ch = codePart[i];
            if (ch === '"' || ch === "'") {
                const quote = ch;
                let j = i + 1;
                while (j < codePart.length) {
                    if (codePart[j] === '\\') { j += 2; continue; }
                    if (codePart[j] === quote) { j += 1; break; }
                    j += 1;
                }
                const lit = codePart.slice(i, j);
                tokenized.push(`<span class="tok-string">${escapeHtml(lit)}</span>`);
                i = j;
                continue;
            }
            let j = i;
            while (j < codePart.length && codePart[j] !== '"' && codePart[j] !== "'") {
                j += 1;
            }
            const plain = codePart.slice(i, j);
            tokenized.push(highlightPlainCode(plain, keywords, constants));
            i = j;
        }

        let colored = tokenized.join('');
        if (commentPart) {
            colored += `<span class="tok-comment">${escapeHtml(commentPart)}</span>`;
        }
        out.push(colored);
    }

    return out.join('\n');
}

function highlightPlainCode(plain, keywords, constants) {
    let s = escapeHtml(plain);
    s = s.replace(constants, '<span class="tok-number">$&</span>');
    s = s.replace(keywords, '<span class="tok-keyword">$&</span>');
    return s;
}

// --- Grid Creation ---
function createLed(logicalX, logicalY) {
    const led = document.createElement('div');
    led.classList.add('led');
    led.dataset.x = logicalX;
    led.dataset.y = logicalY;
    return led;
}

function createCube(cubeX, cubeY) {
    const cube = document.createElement('div');
    cube.classList.add('cube');

    // Maps the 2x2 visual grid to the physical panel chain (TL→BL→TR→BR)
    const panelIndex = cubeX * 2 + cubeY;
    const logicalYOffset = panelIndex * LED_ROWS_PER_CUBE;

    // Left 8 columns
    for (let i = 0; i < 8; i++) {
        const column = document.createElement('div');
        column.classList.add('column');
        for (let j = 0; j < LED_ROWS_PER_CUBE; j++) {
            column.appendChild(createLed(i, logicalYOffset + j));
        }
        cube.appendChild(column);
    }

    // Gap
    const gap = document.createElement('div');
    gap.classList.add('gapColumn');
    cube.appendChild(gap);

    // Right 8 columns
    for (let i = 8; i < 16; i++) {
        const column = document.createElement('div');
        column.classList.add('column');
        for (let j = 0; j < LED_ROWS_PER_CUBE; j++) {
            column.appendChild(createLed(i, logicalYOffset + j));
        }
        cube.appendChild(column);
    }
    return cube;
}

function createFullDisplay() {
    for (let y = 0; y < NUM_CUBES_Y; y++) {
        for (let x = 0; x < NUM_CUBES_X; x++) {
            displayContainer.appendChild(createCube(x, y));
        }
    }
}

// --- Drawing Logic ---
function handleDraw(clientX, clientY) {
    const element = document.elementFromPoint(clientX, clientY);
    if (element && element.classList.contains('led') && element !== lastLedElement) {
        const x = parseInt(element.dataset.x);
        const y = parseInt(element.dataset.y);
        sendControlMessage({ type: 'draw', x, y });
        
        element.classList.add('drawn-on');
        lastLedElement = element;
    }
}

function startDrawing(e) {
    // Only start drawing if touching an LED element
    const touch = e.touches ? e.touches[0] : e;
    const element = document.elementFromPoint(touch.clientX, touch.clientY);
    if (!element || !element.classList.contains('led')) return;
    
    isDrawing = true;
    handleDraw(touch.clientX, touch.clientY);
}

function stopDrawing() {
    isDrawing = false;
    lastLedElement = null;
}

function draw(e) {
    if (!isDrawing) return;
    
    // Only prevent default if we're actually drawing on LEDs
    const touch = e.touches ? e.touches[0] : e;
    const element = document.elementFromPoint(touch.clientX, touch.clientY);
    if (element && element.classList.contains('led')) {
        e.preventDefault();
        handleDraw(touch.clientX, touch.clientY);
    }
}

// --- Init ---
window.addEventListener('DOMContentLoaded', () => {
    setStatus('Connecting...', '#333');
    connectWebSocket();
    createFullDisplay();

    // Add event listeners only to the LED grid container
    displayContainer.addEventListener('mousedown', startDrawing);
    displayContainer.addEventListener('mousemove', draw);
    
    displayContainer.addEventListener('touchstart', startDrawing, { passive: false });
    displayContainer.addEventListener('touchmove', draw, { passive: false });
    
    // Global listeners for stopping drawing
    document.addEventListener('mouseup', stopDrawing);
    document.addEventListener('mouseleave', stopDrawing);
    document.addEventListener('touchend', stopDrawing);
    document.addEventListener('touchcancel', stopDrawing);

    // --- Snake Controls ---
    function sendDirection(dir) {
        sendControlMessage({ type: 'direction', value: dir });
    }

    document.getElementById('btnUp').addEventListener('click', () => sendDirection('up'));
    document.getElementById('btnDown').addEventListener('click', () => sendDirection('down'));
    document.getElementById('btnLeft').addEventListener('click', () => sendDirection('left'));
    document.getElementById('btnRight').addEventListener('click', () => sendDirection('right'));

    // Keyboard arrows / WASD
    document.addEventListener('keydown', (e) => {
        if (snakeControls.style.display === 'none') return;
        const map = {
            ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
            w: 'up', s: 'down', a: 'left', d: 'right',
            W: 'up', S: 'down', A: 'left', D: 'right',
        };
        if (map[e.key]) { e.preventDefault(); sendDirection(map[e.key]); }
    });

    // Swipe gesture on snake area
    let touchStartX = 0, touchStartY = 0;
    snakeControls.addEventListener('touchstart', (e) => {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });
    snakeControls.addEventListener('touchend', (e) => {
        const dx = e.changedTouches[0].clientX - touchStartX;
        const dy = e.changedTouches[0].clientY - touchStartY;
        const absDx = Math.abs(dx), absDy = Math.abs(dy);
        if (Math.max(absDx, absDy) < 30) return; // too short
        if (absDx > absDy) {
            sendDirection(dx > 0 ? 'right' : 'left');
        } else {
            sendDirection(dy > 0 ? 'down' : 'up');
        }
    }, { passive: true });

    viewSourceBtn.addEventListener('click', () => {
        loadSelectedProgramSource();
    });
    closeSourceBtn.addEventListener('click', hideSourceOverlay);
    sourceOverlay.addEventListener('click', (e) => {
        if (e.target === sourceOverlay) hideSourceOverlay();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !sourceOverlay.classList.contains('hidden')) {
            hideSourceOverlay();
        }
    });
});
