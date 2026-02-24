const http = require('http');
const express = require('express');
const { WebSocketServer } = require('ws');
const net = require('net');
const { spawn } = require('child_process');
const path = require('path');

// --- Configuration ---
const HTTP_PORT = 80;
const TCP_PORT = 1337;
const IDLE_TIMEOUT_MS = 60000;
const DRAWING_TIMEOUT_MS = 5000; // 5 seconds after last drawing
const SCRIPTS_DIR = path.join(__dirname, 'scripts');

// --- State Management ---
let serverState = 'booting';
let activeProcess = null;
let tcpStreamTimeout = null;
let drawingTimeout = null;
let webSocketClients = 0;
let isInDrawingMode = false;

// --- Process Management ---
function runScript(scriptName) {
    if (activeProcess) {
        activeProcess.kill('SIGTERM');
        activeProcess = null;
    }
    const scriptPath = path.join(SCRIPTS_DIR, scriptName);
    console.log(`Starting script: ${scriptPath}`);
    const process = spawn('sudo', ['python3', scriptPath]);

    process.on('error', (err) => console.error(`Failed to start script ${scriptName}:`, err));
    process.stderr.on('data', (data) => console.error(`Error from ${scriptName}: ${data}`));
    process.on('close', (code) => {
        if (code !== 0) console.log(`Script ${scriptName} exited with code ${code}.`);
        if (activeProcess === process) activeProcess = null;
    });

    return process;
}

// --- State Transitions ---
function enterIdleState() {
    console.log('Entering idle/animation state.');
    serverState = 'idle';
    isInDrawingMode = false;
    if (drawingTimeout) clearTimeout(drawingTimeout);
    if (tcpStreamTimeout) clearTimeout(tcpStreamTimeout);
    
    if (!activeProcess || activeProcess.killed) {
        activeProcess = runScript('CM2_animation_and_drawing.py');
    }
    // If process is already running, it will naturally return to animation mode
}

function enterTcpStreamingState() {
    console.log('Entering TCP streaming state.');
    serverState = 'tcp_streaming';
    isInDrawingMode = false;
    if (drawingTimeout) clearTimeout(drawingTimeout);
    activeProcess = runScript('stream_handler.py');
    resetTcpStreamTimeout();
}

function enterWebDrawingState() {
    console.log('Switching to drawing mode within hybrid display.');
    serverState = 'web_drawing';
    isInDrawingMode = true;
    if (tcpStreamTimeout) clearTimeout(tcpStreamTimeout);
    
    // Keep the same hybrid process running - it will switch to drawing mode
    // when it receives drawing input
    if (!activeProcess || activeProcess.killed) {
        activeProcess = runScript('CM2_animation_and_drawing.py');
    }
}

function resetTcpStreamTimeout() {
    if (tcpStreamTimeout) clearTimeout(tcpStreamTimeout);
    tcpStreamTimeout = setTimeout(() => {
        console.log('TCP stream idle timeout reached.');
        enterIdleState();
    }, IDLE_TIMEOUT_MS);
}

function resetDrawingTimeout() {
    if (drawingTimeout) clearTimeout(drawingTimeout);
    drawingTimeout = setTimeout(() => {
        console.log('Drawing inactivity timeout reached (3s). Returning to animation.');
        hasReceivedDrawingInput = false;
        isInDrawingMode = false;
        // Don't kill the process, just let it return to animation mode naturally
        // by not sending any more drawing inputs
        serverState = 'idle';
    }, DRAWING_TIMEOUT_MS);
}

// --- Express Web Server ---
const app = express();

app.get('/hotspot-detect.html', (req, res) => {
    // Redirect iOS mini-browser directly to the portal
    res.redirect('/');
});

app.get(['/generate_204', '/gen_204', '/clients3.google.com/generate_204'], (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get(['/ncsi.txt', '/connecttest.txt'], (req, res) => {
    // Windows probe
    res.redirect('/');
});

app.get('/check_network_status.txt', (req, res) => {
    // Linux probe
    res.redirect('/');
});

// Catch-all for the actual portal page
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

const httpServer = http.createServer(app);

// --- WebSocket Server ---
const wss = new WebSocketServer({ server: httpServer });

wss.on('connection', (ws) => {
    webSocketClients++;
    console.log(`Web client connected. Total clients: ${webSocketClients}`);
    
    // Start hybrid display if not running, but don't switch to drawing mode yet
    if (!activeProcess || activeProcess.killed) {
        console.log('Starting hybrid display for new client connection.');
        activeProcess = runScript('CM2_animation_and_drawing.py');
        serverState = 'idle'; // Start in animation mode
    }

    ws.on('message', (message) => {
        // First drawing input received - switch to drawing mode
        if (!isInDrawingMode) {
            console.log('First drawing input received. Entering drawing mode.');
            enterWebDrawingState();
        }
        
        // Reset drawing timeout on every drawing input
        resetDrawingTimeout();
        
        // Send drawing data to hybrid display
        if (activeProcess && activeProcess.stdin && !activeProcess.killed) {
            try {
                activeProcess.stdin.write(message + '\n');
            } catch (err) {
                console.error('Error writing to hybrid display:', err.message);
            }
        }
    });

    ws.on('close', () => {
        webSocketClients--;
        console.log(`Web client disconnected. Total clients: ${webSocketClients}`);
        
        // Don't immediately return to idle - let the 3-second timer handle it
        // This allows multiple people to connect/disconnect without interrupting
        if (webSocketClients === 0) {
            console.log('Last web client disconnected.');
            if (!isInDrawingMode) {
                // No drawing ever happened, continue with animation
                console.log('No drawing occurred, continuing animation.');
            }
            // If drawing was happening, the drawingTimeout will handle the transition
        }
    });

    ws.on('error', (err) => console.error('WebSocket error:', err.message));
});

// --- TCP Server for Data Streaming ---
const tcpServer = net.createServer((socket) => {
    console.log('TCP client connected. Overriding web/idle states.');
    enterTcpStreamingState();

    socket.on('data', (data) => {
        resetTcpStreamTimeout();
        if (serverState === 'tcp_streaming' && activeProcess && activeProcess.stdin) {
            activeProcess.stdin.write(data);
        }
    });

    socket.on('end', () => {
        console.log('TCP client disconnected.');
        if (serverState === 'tcp_streaming') enterIdleState();
    });

    socket.on('error', (err) => {
        console.error('TCP socket error:', err.message);
        if (serverState === 'tcp_streaming') enterIdleState();
    });
});

// --- Main Startup ---
function main() {
    httpServer.listen(HTTP_PORT, '0.0.0.0', () => console.log(`HTTP server listening on http://0.0.0.0:${HTTP_PORT}`));
    tcpServer.listen(TCP_PORT,  '0.0.0.0', () => console.log(`TCP server listening on port ${TCP_PORT}`));
    process.on('SIGINT', () => {
        console.log('Caught interrupt signal. Cleaning up.');
        if (activeProcess) activeProcess.kill('SIGINT');
        process.exit(0);
    });
    enterIdleState();
}

main();