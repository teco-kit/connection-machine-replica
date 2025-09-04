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

// --- State Management ---
let serverState = 'booting';
let activeProcess = null;
let tcpStreamTimeout = null;
let webDrawTimeout = null;
let webSocketClients = 0;

// --- Process Management ---
function runScript(scriptName) {
    if (activeProcess) {
        activeProcess.kill('SIGTERM');
        activeProcess = null;
    }
    console.log(`Starting script: ${scriptName}`);
    const process = spawn('sudo', ['python3', scriptName]);

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
    if (serverState === 'idle') return;
    console.log('Entering idle state.');
    serverState = 'idle';
    if (webDrawTimeout) clearTimeout(webDrawTimeout);
    if (tcpStreamTimeout) clearTimeout(tcpStreamTimeout);
    activeProcess = runScript('./CM2_animation.py');
}

function enterTcpStreamingState() {
    console.log('Entering TCP streaming state.');
    serverState = 'tcp_streaming';
    if (webDrawTimeout) clearTimeout(webDrawTimeout);
    activeProcess = runScript('./stream_handler.py');
    resetTcpStreamTimeout();
}

function enterWebDrawingState() {
    if (serverState === 'web_drawing') return;
    console.log('Entering web drawing state.');
    serverState = 'web_drawing';
    if (tcpStreamTimeout) clearTimeout(tcpStreamTimeout);
    activeProcess = runScript('./web_draw.py');
    resetWebDrawTimeout();
}

function resetTcpStreamTimeout() {
    if (tcpStreamTimeout) clearTimeout(tcpStreamTimeout);
    tcpStreamTimeout = setTimeout(() => {
        console.log('TCP stream idle timeout reached.');
        enterIdleState();
    }, IDLE_TIMEOUT_MS);
}

function resetWebDrawTimeout() {
    if (webDrawTimeout) clearTimeout(webDrawTimeout);
    webDrawTimeout = setTimeout(() => {
        console.log('Web drawing inactivity timeout reached.');
        wss.clients.forEach(ws => ws.close()); // Disconnect all clients
        enterIdleState();
    }, IDLE_TIMEOUT_MS);
}

// --- Express Web Server ---
const app = express();

app.get('/hotspot-detect.html', (req, res) => {
    // Redirect iOS mini-browser directly to the portal
    res.redirect('/');
});

app.get(['/generate_204', '/gen_204'], (req, res) => {
    // Android probe: trigger portal by redirect
    res.redirect('/');
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
    if (webSocketClients === 0) {
        enterWebDrawingState(); // First client triggers the state change
    }
    webSocketClients++;
    console.log(`Web client connected. Total clients: ${webSocketClients}`);

    ws.on('message', (message) => {
        resetWebDrawTimeout(); // Reset inactivity timer on any message
        if (serverState === 'web_drawing' && activeProcess && activeProcess.stdin) {
            activeProcess.stdin.write(message + '\n');
        }
    });

    ws.on('close', () => {
        webSocketClients--;
        console.log(`Web client disconnected. Total clients: ${webSocketClients}`);
        if (webSocketClients === 0 && serverState === 'web_drawing') {
            console.log('Last web client disconnected.');
            enterIdleState();
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