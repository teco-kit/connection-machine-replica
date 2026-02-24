const displayContainer = document.getElementById('cube-grid');
const statusDiv = document.getElementById('status');

const NUM_CUBES_X = 2;
const NUM_CUBES_Y = 2;
const LED_COLS_PER_CUBE = 16;
const LED_ROWS_PER_CUBE = 32;

let isDrawing = false;
let lastLedElement = null;

// --- Probability Control ---
const probabilitySlider = document.getElementById('probabilitySlider');
const probabilityValue = document.getElementById('probabilityValue');

// Update probability display and send to server
function updateProbability() {
    const probability = probabilitySlider.value;
    probabilityValue.textContent = `${probability}%`;
    
    // Send probability update to server
    if (ws.readyState === WebSocket.OPEN) {
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
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'speed',
            value: speed / 1000.0  // Convert to seconds
        }));
    }
}

speedSlider.addEventListener('input', updateSpeed);

// --- WebSocket Connection ---
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${protocol}://${window.location.host}`);

ws.onopen = () => {
    statusDiv.textContent = 'Connected';
    statusDiv.style.background = '#27ae60';
    // Send initial values
    updateProbability();
    updateSpeed();
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

    // This maps the 2x2 visual grid to a 1x4 vertical strip of panels
    const panelIndex = cubeY * 2 + cubeX;
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
});
