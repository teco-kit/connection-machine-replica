const http = require('http');
const express = require('express');
const { WebSocketServer } = require('ws');
const net = require('net');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// --- Configuration ---
const HTTP_PORT = 80;
const TCP_PORT = 1337;

// --- Logging ---
const LOG_DIR = path.join(__dirname, 'log');
const LOG_FILE = path.join(LOG_DIR, 'connections.log');
if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });

function logEvent(obj) {
    const line = JSON.stringify({ time: new Date().toISOString(), ...obj }) + '\n';
    fs.appendFile(LOG_FILE, line, () => {});  // async, fire-and-forget
}
const IDLE_TIMEOUT_MS = 60000;       // TCP idle → back to idle animation
const DRAWING_TIMEOUT_MS = 5000;     // Drawing inactivity → back to idle
const SCRIPTS_DIR = path.join(__dirname, 'scripts');
const MODES_DIR = path.join(SCRIPTS_DIR, 'modes');
const PROGRAMS_DIR = path.join(SCRIPTS_DIR, 'programs');
const CSTAR_DIR = path.join(PROGRAMS_DIR, 'cstar');
const CSTAR_EXCLUDED = new Set(['random_blink']); // covered by idle mode

// --- State Management ---
// States: 'idle' | 'drawing' | 'tcp_streaming' | 'program'
let serverState = 'booting';
let activeProcess = null;
let activeProgramId = null;
let tcpStreamTimeout = null;
let drawingTimeout = null;
let programTimeout = null;
let webSocketClients = 0;

// --- Program Discovery ---
function getAvailablePrograms() {
    const programs = [];

    // Built-in idle
    programs.push({ id: 'idle', name: 'Idle Animation', type: 'builtin' });

    // Python programs in programs/
    try {
        const files = fs.readdirSync(PROGRAMS_DIR);
        for (const f of files) {
            if (f.endsWith('.py') && f !== '__init__.py') {
                const id = f.replace('.py', '');
                const name = id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                programs.push({ id, name, type: 'python' });
            }
        }
    } catch {}

    // C* programs in programs/cstar/
    try {
        const files = fs.readdirSync(CSTAR_DIR);
        for (const f of files) {
            if (f.endsWith('.cstar')) {
                const baseName = f.replace('.cstar', '');
                if (CSTAR_EXCLUDED.has(baseName)) continue;
                const id = 'cstar:' + baseName;
                const name = baseName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                programs.push({ id, name, type: 'cstar' });
            }
        }
    } catch {}

    return programs;
}

// --- Process Management ---
function killActive() {
    if (activeProcess) {
        activeProcess.kill('SIGTERM');
        activeProcess = null;
    }
    activeProgramId = null;
}

function runScript(scriptPath, args = []) {
    killActive();
    console.log(`[${serverState}] Starting: ${scriptPath} ${args.join(' ')}`);
    const proc = spawn('sudo', ['python3', '-u', scriptPath, ...args]);

    proc.on('error', (err) => console.error(`Failed to start ${scriptPath}:`, err));
    // Suppress EPIPE and other async stdin errors (e.g. process died before write)
    proc.stdin.on('error', () => {});
    proc.stderr.on('data', (data) => console.error(`[${path.basename(scriptPath)}] ${data}`));
    proc.on('close', (code) => {
        if (code !== 0 && code !== null) console.log(`[${path.basename(scriptPath)}] exited with code ${code}`);
        if (activeProcess === proc) {
            activeProcess = null;
            // If a program finished on its own, return to idle
            if (serverState === 'program') {
                console.log('Program finished, returning to idle.');
                enterIdleState();
            }
        }
    });

    activeProcess = proc;
    return proc;
}

// --- State Transitions ---
function clearAllTimeouts() {
    if (drawingTimeout)   { clearTimeout(drawingTimeout);   drawingTimeout = null; }
    if (tcpStreamTimeout) { clearTimeout(tcpStreamTimeout); tcpStreamTimeout = null; }
    if (programTimeout)   { clearTimeout(programTimeout);   programTimeout = null; }
}

function enterIdleState() {
    if (serverState === 'idle' && activeProcess && !activeProcess.killed) return;
    console.log('→ idle (animation)');
    serverState = 'idle';
    clearAllTimeouts();
    runScript(path.join(MODES_DIR, 'idle.py'));
    broadcastState();
}

function enterDrawingState() {
    if (serverState === 'drawing' && activeProcess && !activeProcess.killed) return;
    console.log('→ drawing');
    serverState = 'drawing';
    clearAllTimeouts();
    runScript(path.join(MODES_DIR, 'drawing.py'));
    broadcastState();
}

function enterTcpStreamingState() {
    console.log('→ tcp_streaming');
    serverState = 'tcp_streaming';
    clearAllTimeouts();
    runScript(path.join(MODES_DIR, 'stream.py'));
    resetTcpStreamTimeout();
    broadcastState();
}

// Interactive programs that are spawned directly (need their own stdin)
const INTERACTIVE_PROGRAMS = new Set(['snake']);
const PROGRAM_TIMEOUT_MS = 60000;  // Auto-return to idle after 60s (non-interactive)

function enterProgramState(programId) {
    clearAllTimeouts();

    // Resolve the program name the mode script needs
    const programName = programId.startsWith('cstar:')
        ? programId.replace('cstar:', '')
        : programId;

    // Interactive programs (e.g. snake) are spawned directly — they read stdin
    if (INTERACTIVE_PROGRAMS.has(programId)) {
        console.log(`→ program (${programId}) [interactive]`);
        serverState = 'program';

        const scriptPath = path.join(PROGRAMS_DIR, programId + '.py');
        const proc = runScript(scriptPath);
        activeProgramId = programId;

        // Listen for JSON messages on stdout (score, finished)
        let stdoutBuf = '';
        proc.stdout.on('data', (chunk) => {
            stdoutBuf += chunk.toString();
            let nl;
            while ((nl = stdoutBuf.indexOf('\n')) >= 0) {
                const line = stdoutBuf.slice(0, nl).trim();
                stdoutBuf = stdoutBuf.slice(nl + 1);
                if (!line) continue;
                try {
                    const msg = JSON.parse(line);
                    if (msg.type === 'finished' && serverState === 'program' && activeProcess === proc) {
                        console.log(`[${programId}] Game over, returning to idle.`);
                        enterIdleState();
                    } else if (msg.type === 'score') {
                        const scoreMsg = JSON.stringify({ type: 'score', value: msg.value });
                        wss.clients.forEach((ws) => {
                            if (ws.readyState === 1) ws.send(scoreMsg);
                        });
                    }
                } catch {}
            }
        });

        broadcastState();
        return;
    }

    // Non-interactive: always kill and spawn fresh program.py
    console.log(`→ program (${programId})`);
    serverState = 'program';
    killActive();
    activeProgramId = programId;

    const scriptPath = path.join(MODES_DIR, 'program.py');
    console.log(`[${serverState}] Starting: ${scriptPath}`);
    const proc = spawn('sudo', ['python3', '-u', scriptPath]);

    proc.on('error', (err) => console.error('Failed to start program mode:', err));
    proc.stdin.on('error', () => {});
    proc.stderr.on('data', (data) => console.error(`[program] ${data}`));

    // Parse JSON messages from stdout (programs list, started, finished)
    let stdoutBuf = '';
    proc.stdout.on('data', (chunk) => {
        stdoutBuf += chunk.toString();
        let nl;
        while ((nl = stdoutBuf.indexOf('\n')) >= 0) {
            const line = stdoutBuf.slice(0, nl).trim();
            stdoutBuf = stdoutBuf.slice(nl + 1);
            if (!line) continue;
            try {
                const msg = JSON.parse(line);
                if (msg.type === 'programs') {
                    console.log(`[program] Available: ${msg.list.join(', ')}`);
                } else if (msg.type === 'finished' && serverState === 'program' && activeProcess === proc) {
                    console.log('[program] Program finished, returning to idle.');
                    enterIdleState();
                }
            } catch {}
        }
    });

    proc.on('close', (code) => {
        if (code !== 0 && code !== null) console.log(`[program] exited with code ${code}`);
        if (activeProcess === proc) {
            activeProcess = null;
            if (serverState === 'program') enterIdleState();
        }
    });

    activeProcess = proc;

    // Send program selection (stdin is buffered; mode reads it after preloading)
    try {
        proc.stdin.write(JSON.stringify({ type: 'run', program: programName }) + '\n');
    } catch {};
    broadcastState();

    // Auto-return to idle after timeout
    programTimeout = setTimeout(() => {
        if (serverState === 'program') {
            console.log('Program timeout, returning to idle.');
            enterIdleState();
        }
    }, PROGRAM_TIMEOUT_MS);
}

function resetTcpStreamTimeout() {
    if (tcpStreamTimeout) clearTimeout(tcpStreamTimeout);
    tcpStreamTimeout = setTimeout(() => {
        console.log('TCP stream idle timeout.');
        enterIdleState();
    }, IDLE_TIMEOUT_MS);
}

function resetDrawingTimeout() {
    if (drawingTimeout) clearTimeout(drawingTimeout);
    drawingTimeout = setTimeout(() => {
        console.log('Drawing inactivity timeout.');
        enterIdleState();
    }, DRAWING_TIMEOUT_MS);
}

// --- Broadcast helpers ---
function broadcastState() {
    const msg = JSON.stringify({
        type: 'state',
        state: serverState,
        program: activeProgramId
    });
    wss.clients.forEach((ws) => {
        if (ws.readyState === 1) ws.send(msg);
    });
}

// --- Express Web Server ---
const app = express();

// Helper: issue an absolute 302 redirect to our portal root.
// Using the IP from the incoming socket ensures the captive portal browser
// can reach us (the Host header may contain a foreign hostname).
function portalRedirect(req, res) {
    const localIp = req.socket.localAddress.replace(/^::ffff:/, '');
    res.redirect(302, `http://${localIp}/`);
}

// --- Captive portal detection endpoints ---

// Apple (iOS/macOS Captive Network Assistant): redirect to trigger portal popup.
// iOS checks captive.apple.com/hotspot-detect.html; if it gets anything other
// than the known "Success" body, it opens the CNA browser pointing at the URL
// we redirect to.
app.get(['/hotspot-detect.html', '/library/test/success.html', '/success.html'], (req, res) => {
    portalRedirect(req, res);
});

// Android / Google: expects 204 for internet, redirect → captive portal popup
// Note: Android 10+ also checks via HTTPS (port 443). Without TLS interception
// that HTTPS check reaches real Google and returns 204, which can dismiss the
// portal on modern devices. The HTTP checks below catch connections where the
// DNS/firewall routes all HTTP traffic to us.
app.get([
    '/generate_204',
    '/gen_204',
    '/clients3.google.com/generate_204',
    '/connectivitycheck.gstatic.com/generate_204',
    '/connectivitycheck.android.com/generate_204',
], (req, res) => portalRedirect(req, res));

// Samsung-specific detection
app.get([
    '/connectivitycheck.samsung.com/generate_204',
    '/wifi.samsung.com/generate_204',
    '/samsung.com/generate_204',
    '/www.samsung.com/generate_204',
], (req, res) => portalRedirect(req, res));

// Xiaomi / MIUI
app.get('/generate204', (req, res) => portalRedirect(req, res));
app.get('/miui/v5/redirect', (req, res) => portalRedirect(req, res));

// Windows NCSI: expects exact strings, otherwise shows "No Internet" banner.
// A redirect here also triggers the captive portal notification on Windows.
app.get('/ncsi.txt', (req, res) => res.type('txt').send('Microsoft NCSI'));
app.get('/connecttest.txt', (req, res) => res.type('txt').send('Microsoft Connect Test'));
app.get('/redirect', (req, res) => portalRedirect(req, res));

// Generic Android / misc
app.get('/check_network_status.txt', (req, res) => portalRedirect(req, res));

// Catch-all: if the request Host does not match our IP (i.e. the device's DNS
// resolver sent a foreign hostname's request to us), redirect to the portal.
// This only handles HTTP — HTTPS captive-portal checks on Android 10+ bypass
// this since they go directly to Google's servers over port 443.
app.use((req, res, next) => {
    const localIp = req.socket.localAddress.replace(/^::ffff:/, '');
    const host = (req.headers.host || '').split(':')[0];
    // Also allow hostname-style access (e.g. "raspberrypi.local")
    if (host && host !== localIp && host !== 'localhost' && !host.endsWith('.local')) {
        return portalRedirect(req, res);
    }
    next();
});

app.get('/api/programs', (req, res) => {
    res.json(getAvailablePrograms());
});

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.use(express.static(path.join(__dirname, 'public')));

const httpServer = http.createServer(app);

// --- WebSocket Server ---
const wss = new WebSocketServer({ server: httpServer });

wss.on('connection', (ws, req) => {
    const clientIp = (req.socket.remoteAddress || '').replace(/^::ffff:/, '');
    const userAgent = req.headers['user-agent'] || '';
    const connectedAt = Date.now();
    webSocketClients++;
    logEvent({ event: 'connect', ip: clientIp, userAgent, totalClients: webSocketClients });
    console.log(`Web client connected from ${clientIp} (${webSocketClients} total).`);

    // Send current state and program list to new client
    ws.send(JSON.stringify({
        type: 'init',
        state: serverState,
        program: activeProgramId,
        programs: getAvailablePrograms()
    }));

    ws.on('message', (message) => {
        let parsed;
        try {
            parsed = JSON.parse(message);
        } catch {
            return;
        }

        const msgType = parsed.type || 'draw';

        // While a TCP stream is live, ignore all web control commands.
        // The UI will reflect the tcp_streaming state; controls are re-enabled
        // automatically when the TCP client disconnects.
        if (serverState === 'tcp_streaming') return;

        if (msgType === 'draw') {
            // Switch to drawing state if not already there
            if (serverState !== 'drawing') {
                enterDrawingState();
            }
            resetDrawingTimeout();

            // Forward draw command to drawing.py
            if (activeProcess && activeProcess.stdin && !activeProcess.killed) {
                try { activeProcess.stdin.write(message + '\n'); } catch {}
            }
        } else if (msgType === 'probability' || msgType === 'speed') {
            // Forward tunable commands to whichever script is running
            // (idle_animation.py handles these; drawing.py ignores them)
            if (activeProcess && activeProcess.stdin && !activeProcess.killed) {
                try { activeProcess.stdin.write(message + '\n'); } catch {}
            }
        } else if (msgType === 'direction') {
            // Forward direction input to the running program (e.g. snake)
            if (serverState === 'program' && activeProcess && activeProcess.stdin && !activeProcess.killed) {
                try { activeProcess.stdin.write(JSON.stringify(parsed) + '\n'); } catch {}
            }
        } else if (msgType === 'run_program') {
            const programId = parsed.id;
            if (!programId) return;
            logEvent({ event: 'run_program', program: programId, ip: clientIp });

            if (programId === 'idle') {
                enterIdleState();
            } else {
                // Validate program exists
                const available = getAvailablePrograms();
                if (available.some(p => p.id === programId)) {
                    enterProgramState(programId);
                }
            }
        } else if (msgType === 'stop_program') {
            enterIdleState();
        }
    });

    ws.on('close', () => {
        webSocketClients--;
        const durationSec = Math.round((Date.now() - connectedAt) / 1000);
        logEvent({ event: 'disconnect', ip: clientIp, durationSec, totalClients: webSocketClients });
        console.log(`Web client disconnected from ${clientIp} after ${durationSec}s (${webSocketClients} total).`);
    });

    ws.on('error', (err) => console.error('WebSocket error:', err.message));
});

// --- TCP Server for Data Streaming ---
const tcpServer = net.createServer((socket) => {
    console.log('TCP client connected.');
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
    httpServer.on('error', (err) => {
        if (err.code === 'EACCES') {
            console.error(`\nError: Permission denied on port ${HTTP_PORT}. Run with sudo:\n\n  sudo node server.js\n`);
        } else {
            console.error('HTTP server error:', err.message);
        }
        process.exit(1);
    });

    tcpServer.on('error', (err) => {
        if (err.code === 'EACCES') {
            console.error(`\nError: Permission denied on port ${TCP_PORT}. Run with sudo:\n\n  sudo node server.js\n`);
        } else {
            console.error('TCP server error:', err.message);
        }
        process.exit(1);
    });

    httpServer.listen(HTTP_PORT, '0.0.0.0', () => console.log(`HTTP server on http://0.0.0.0:${HTTP_PORT}`));
    tcpServer.listen(TCP_PORT,  '0.0.0.0', () => console.log(`TCP server on port ${TCP_PORT}`));
    process.on('SIGINT', () => {
        console.log('Shutting down.');
        killActive();
        process.exit(0);
    });

    console.log('Available programs:', getAvailablePrograms().map(p => p.id).join(', '));
    enterIdleState();
}

main();