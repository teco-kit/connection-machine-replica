const displayContainer = document.getElementById('display');
const statusDiv = document.getElementById('status');

const NUM_CUBES_X = 2;
const NUM_CUBES_Y = 2;
const LED_COLS_PER_CUBE = 16;
const LED_ROWS_PER_CUBE = 32;

let isDrawing = false;
let lastLedElement = null;

// --- WebSocket Connection ---
//const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
//const ws = new WebSocket(`${protocol}://${window.location.host}`);

// ws.onopen = () => {
//     statusDiv.textContent = 'Connected';
//     statusDiv.style.background = '#27ae60';
// };
// ws.onclose = () => {
//     statusDiv.textContent = 'Disconnected';
//     statusDiv.style.background = '#c0392b';
// };
// ws.onerror = (err) => {
//     console.error('WebSocket error:', err);
//     statusDiv.textContent = 'Error';
//     statusDiv.style.background = '#c0392b';
// };

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
// function handleDraw(clientX, clientY) {
//     const element = document.elementFromPoint(clientX, clientY);
//     if (element && element.classList.contains('led') && element !== lastLedElement) {
//         lastLedElement = element;
//         const { x, y } = element.dataset;

//         if (ws.readyState === WebSocket.OPEN) {
//             ws.send(JSON.stringify({ x: parseInt(x), y: parseInt(y) }));
//         }

//         // Remove class if already present to restart animation
//         element.classList.remove('drawn-on');
//         // Force reflow to restart animation
//         element.offsetHeight;
//         element.classList.add('drawn-on');
//     }
// }

function startDrawing(e) {
    isDrawing = true;
    const touch = e.touches ? e.touches[0] : e;
    handleDraw(touch.clientX, touch.clientY);
}

function stopDrawing() {
    isDrawing = false;
    lastLedElement = null;
}

function draw(e) {
    if (!isDrawing) return;
    e.preventDefault();
    const touch = e.touches ? e.touches[0] : e;
    handleDraw(touch.clientX, touch.clientY);
}

// --- Init ---
window.addEventListener('DOMContentLoaded', () => {
    createFullDisplay();

    document.addEventListener('mousedown', startDrawing);
    document.addEventListener('mouseup', stopDrawing);
    document.addEventListener('mouseleave', stopDrawing);
    document.addEventListener('mousemove', draw);

    document.addEventListener('touchstart', startDrawing, { passive: false });
    document.addEventListener('touchend', stopDrawing);
    document.addEventListener('touchcancel', stopDrawing);
    document.addEventListener('touchmove', draw, { passive: false });
});
