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

function setSliderVisibility(visible) {
    // Use visibility (not display) so sliders always reserve their space
    // and toggling them never shifts the grid position.
    const v = visible ? 'visible' : 'hidden';
    if (workloadLabel) workloadLabel.style.visibility = v;
    if (speedLabel) speedLabel.style.visibility = v;
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
    
    // Send probability update to server
    if (ws.readyState === WS_OPEN) {
        ws.send(JSON.stringify({
            type: 'probability',
            value: probability / 100.0  // Convert to 0.0-1.0 range
        }));
    }
}

probabilitySlider.addEventListener('input', updateProbability);

// --- Speed Control ---
const speedSlider = document.getElementById('speedSlider');
const speedValue = document.getElementById('speedValue');

// Update speed display and send to server
function updateSpeed() {
    const speed = speedSlider.value;
    speedValue.textContent = `${speed}ms`;
    
    // Send speed update to server
    if (ws.readyState === WS_OPEN) {
        ws.send(JSON.stringify({
            type: 'speed',
            value: speed / 1000.0  // Convert to seconds
        }));
    }
}

speedSlider.addEventListener('input', updateSpeed);

// Safe WebSocket open-state constant (some portal browsers don't expose WebSocket globally)
const WS_OPEN = (typeof WebSocket !== 'undefined') ? WebSocket.OPEN : 1;

// --- WebSocket Connection ---
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
let ws;
try {
    ws = new WebSocket(`${protocol}://${window.location.host}`);
} catch (e) {
    // WebSocket not supported (e.g. captive portal mini-browser)
    ws = { readyState: -1, send: () => {}, onopen: null, onclose: null, onerror: null, onmessage: null };
}

ws.onopen = () => {
    statusDiv.textContent = 'Connected';
    statusDiv.style.background = '#27ae60';
    // Send initial values
    if (probabilitySlider) updateProbability();
    if (speedSlider) updateSpeed();
};
ws.onclose = () => {
    statusDiv.textContent = 'Disconnected';
    statusDiv.style.background = '#c0392b';
};
ws.onerror = (err) => {
    console.error('WebSocket error:', err);
    statusDiv.textContent = 'Error';
    statusDiv.style.background = '#c0392b';
};

ws.onmessage = (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch { return; }

    if (data.type === 'init') {
        currentPrograms = data.programs || [];
        renderProgramList();
        updateActiveState(data.state, data.program);
    } else if (data.type === 'state') {
        updateActiveState(data.state, data.program);
    } else if (data.type === 'score') {
        snakeScore.textContent = data.value;
    }
};

// --- Program Selector ---
function renderProgramList() {
    programSelect.innerHTML = '';
    for (const prog of currentPrograms) {
        if (prog.id === 'idle') continue; // idle has its own button
        const opt = document.createElement('option');
        opt.value = prog.id;
        opt.textContent = prog.name;
        if (prog.type === 'cstar') opt.textContent = '🗄️ ' + prog.name;
        programSelect.appendChild(opt);
    }
}

runBtn.addEventListener('click', () => {
    const id = programSelect.value;
    if (id && ws.readyState === WS_OPEN) {
        ws.send(JSON.stringify({ type: 'run_program', id }));
    }
});

idleBtn.addEventListener('click', () => {
    if (ws.readyState === WS_OPEN) {
        ws.send(JSON.stringify({ type: 'run_program', id: 'idle' }));
    }
    // Immediately restore idle UI and reset dropdown
    gridArea.style.display = '';
    snakeControls.style.display = 'none';
    setSliderVisibility(true);
    // Reset dropdown so pre-run snake check doesn't re-show controls
    if (currentPrograms.length > 1) programSelect.selectedIndex = 0;
});

programSelect.addEventListener('change', () => {
    // Show snake controls as soon as snake is selected (pre-run preview)
    const showSnake = (programSelect.value === 'snake');
    gridArea.style.display = showSnake ? 'none' : '';
    snakeControls.style.display = showSnake ? 'flex' : 'none';
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

    // Show sliders in idle and drawing states
    setSliderVisibility(state === 'idle' || state === 'drawing');

    // When returning to idle, reset dropdown FIRST so the preview check below is correct
    if (state === 'idle') programSelect.selectedIndex = 0;

    // Toggle snake UI vs normal display
    // Only show when snake is actively running, or pre-selected in idle
    const isSnake = (state === 'program' && programId === 'snake');
    const previewSnake = (state === 'idle' && programSelect.value === 'snake');
    const showSnake = isSnake || previewSnake;
    gridArea.style.display = showSnake ? 'none' : '';
    snakeControls.style.display = showSnake ? 'flex' : 'none';
    if (isSnake) snakeScore.textContent = '0';
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
        
        ws.send(JSON.stringify({ type: 'draw', x, y }));
        
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
        if (ws.readyState === WS_OPEN) {
            ws.send(JSON.stringify({ type: 'direction', value: dir }));
        }
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
});
