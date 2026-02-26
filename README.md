# Connection Machine Replica: LED Matrix Server

This project recreates the iconic **Connection Machine 2 (CM2)** LED matrix display using modern WS2815 RGB LEDs. The CM2, a legendary parallel supercomputer from the 1980s, featured a distinctive front panel with a 16×32 LED array that visualized processor activity. This replica faithfully reproduces that display using a **2×2 grid** of four 16×32 matrices for a total of **2048 individually addressable LEDs** (32 × 64).

## What is this project?

The Connection Machine Replica is:

1. **Hardware accurate**: Four WS2815 matrices arranged in a 2×2 grid to replicate the CM2's original LED layout
2. **Software controlled**: A Node.js server with WebSocket and TCP interfaces for real-time LED control
3. **C\* compatible**: Runs authentic C\* data-parallel programs through the CM2 emulator on the physical display
4. **Visualizer ready**: Can display animations, real-time data streams, or interactive web-based drawing
5. **Historically inspired**: Honors the CM2's presence-as-art aesthetic by recreating its most recognizable interface element

The server provides:

- An HTTP + WebSocket portal for interactive drawing on the matrix
- A **program selector** in the web UI for switching between animations and C\* programs
- A raw TCP stream for pushing high-speed full LED frame data
- An idle animation mode that cycles when no clients are active
- Automatic state transitions between drawing, streaming, and animation modes

## Hardware layout

The physical display consists of **four 16×32 WS2815 matrices** arranged in a **2×2 grid**:

```
┌──────────────────┬──────────────────┐
│  Panel 1 (TL)    │  Panel 3 (TR)    │
│    16×32 LEDs    │    16×32 LEDs    │
├──────────────────┼──────────────────┤
│  Panel 2 (BL)    │  Panel 4 (BR)    │
│    16×32 LEDs    │    16×32 LEDs    │
└──────────────────┴──────────────────┘
Chain order: TL → BL → TR → BR
Total LEDs: 2048 (4 × 16 × 32)
```

Each matrix uses **serpentine wiring** (alternating row direction). The four panels are daisy-chained into a single 16×128 strip; the web UI remaps this into the visual 2×2 grid.

```
server/
  public/                       # Web UI (HTML/CSS/JS portal)
  scripts/
    lib/                        # Shared libraries (imported, never run directly)
      cm_display.py             # LED display API (strip config, coordinate mapping, colours)
      cm2_emulator/             # CM2 emulator package
        emulator.py             # CM2Config, CM2Machine
        cstar.py                # C* language parser & SIMD runtime
    modes/                      # Server state-machine scripts (one per state)
      idle.py                   # Idle state — CM2-style random red blinking
      drawing.py                # Drawing state — interactive drawing with fade-out
      stream.py                 # TCP streaming state — raw frame renderer
      program.py                # Program state — runs user-selected programs
    programs/                   # User-selectable programs (auto-discovered)
      rainbow.py                # Rainbow test pattern
      all_white.py              # Solid white test pattern
      cstar/                    # C* data files (auto-discovered)
        wave_front.cstar
        checker_pulse.cstar
        ring_scan.cstar
        news_diffusion.cstar
        mandelbrot.cstar
        mandelbrot_zoom.cstar
  package.json
  server.js                     # Node.js HTTP/WebSocket/TCP server
README.md
```

## Requirements

- Raspberry Pi (or compatible) with WS2815 LEDs
- Python 3 and the `rpi_ws281x` library
- Node.js (for the web/TCP server)
- Root privileges for GPIO access (the server uses `sudo`)

## Raspberry Pi setup (fresh install -> same setup as current system)

This section describes how to set up a Raspberry Pi so it matches the current
deployment model:
- project at `/home/pi/connection-machine-replica`
- Node server at `/home/pi/connection-machine-replica/server/server.js`
- autostart via `systemd` service `ConnectionMachine_Server.service`
- server runs as root (required for LED GPIO access)

### 1) Base OS + network + SSH

On a fresh Raspberry Pi OS install:

```bash
sudo apt update
sudo apt upgrade -y
sudo systemctl enable ssh
sudo systemctl start ssh
```

Find the LAN IP (Ethernet) for SSH:

```bash
ip -4 addr show eth0
hostname -I
```

If you also run captive portal AP mode, `wlan0` is typically on `192.168.4.1`
(hostapd + dnsmasq), while deployment/maintenance should use `eth0`.

### Android captive portal stability (Pixel and newer Android versions)

Modern Android captive portal apps can drop WebSocket connections and can also
churn when probe URLs are repeatedly redirected. The current setup addresses
both:
- Captive probe endpoints are handled in a stable way (reduced redirect churn
  after the portal is already open for that client).
- The web UI automatically falls back to HTTP polling/control if WebSocket is
  unavailable in the captive portal webview.
- Optional AP firewall lockdown can be enabled if Android still dismisses the
  portal because upstream HTTPS validation succeeds.

Runtime env vars:
- `CAPTIVE_LOCKDOWN=0` disables AP firewall lockdown (enabled by default)
- `CAPTIVE_AP_IFACE=<iface>` changes AP interface (default: `wlan0`)

Example systemd override:

```bash
sudo systemctl edit --full ConnectionMachine_Server.service
```

Add under `[Service]` if needed:

```ini
Environment=CAPTIVE_AP_IFACE=wlan0
Environment=CAPTIVE_LOCKDOWN=1
```

### 2) Install runtime dependencies

Install Node.js, Python and build tools:

```bash
sudo apt install -y nodejs npm python3 python3-pip python3-dev git build-essential scons swig
```

Install the WS281x Python library used by `cm_display.py`:

```bash
sudo pip3 install rpi-ws281x --break-system-packages
```

### 3) Copy repository to the Pi

From your Mac:

```bash
scp -r -i ~/.ssh/pi_4_rsa "/Users/philipp/Documents/TECO/Projekte/Connection Machine Replica/connection-machine-replica" pi@10.16.0.225:~/
```

Then on the Pi:

```bash
cd /home/pi/connection-machine-replica/server
npm install
```

### 4) Create systemd autostart service

Create `/etc/systemd/system/ConnectionMachine_Server.service`:

```ini
[Unit]
Description=Connection Machine LED Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/connection-machine-replica/server
ExecStart=/usr/bin/node /home/pi/connection-machine-replica/server/server.js
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Enable + start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ConnectionMachine_Server.service
sudo systemctl start ConnectionMachine_Server.service
sudo systemctl status ConnectionMachine_Server.service
```

Verify startup logs:

```bash
journalctl -u ConnectionMachine_Server.service -f
```

### 5) Updating code later

```bash
sudo systemctl stop ConnectionMachine_Server.service
cd /home/pi/connection-machine-replica/server
npm install
sudo systemctl start ConnectionMachine_Server.service
```

If the service still points to an old path (for example `/home/pi/CM_Server`),
replace it with:

```bash
sudo systemctl edit --full ConnectionMachine_Server.service
sudo systemctl daemon-reload
sudo systemctl restart ConnectionMachine_Server.service
```

## Install

From the repo root:

```
cd server
npm install
```

## Run

Start the server (listens on HTTP :80 and TCP :1337):

```
cd server
sudo npm start
```

Then open the portal in a browser:

```
http://<pi-ip>/
```

## How it works

The server manages four states:

1. **idle** — Runs `modes/idle.py` (CM2-style random red blinking). This is the default.
2. **drawing** — Runs `modes/drawing.py` when a web user starts drawing. Reverts to idle after 5 s of inactivity.
3. **tcp_streaming** — Runs `modes/stream.py` when a TCP client connects. Reverts to idle after 60 s of inactivity.
4. **program** — Runs `modes/program.py` when the user selects a program. Returns to idle when the program finishes.

State transitions:
- `server.js` launches mode scripts from `scripts/modes/` using `sudo`.
- WebSocket draw messages switch from idle → drawing (kills idle, starts drawing process).
- A TCP client connection switches to tcp_streaming (kills whatever is running).
- Probability/speed slider commands are forwarded to the idle animation process.
- The web UI program selector sends `run_program` messages to switch to any available program.

The program selector in the web UI automatically discovers:
- Python scripts in `scripts/programs/` (rainbow, all\_white, etc.)
- C\* programs in `scripts/programs/cstar/*.cstar` (mandelbrot, wave\_front, etc.)

## TCP streaming protocol

- Connect to TCP port `1337`.
- Send exactly `2048` bytes per frame (32 x 64 LEDs).
- Each byte is a red brightness value from 0 to 255.
- The byte order maps directly to LED index (the strip handles serpentine).

### TCP test client (Breakout from macOS)

A ready-to-run client is included at repo root:

```bash
tcp_breakout_client.py
```

Run from your Mac:

```bash
python3 tcp_breakout_client.py --host <pi-ip> --port 1337 --fps 30
```

It opens one TCP connection and continuously streams a classic Breakout-style
animation to the matrix. Use `Ctrl+C` to stop.

## Python scripts

Scripts are organized into three directories under `server/scripts/`:

### Library (`scripts/lib/`)

Shared code imported by mode and program scripts. Never run directly.

- **`cm_display.py`** — Shared LED display API. Owns the strip configuration, coordinate mapping, colour helpers, and a thread-safe `CMDisplay` class. All other scripts import this instead of talking to `rpi_ws281x` directly.
- **`cm2_emulator/`** — CM2 emulator package. Contains `CM2Config`/`CM2Machine` (processor mask → LED matrix mapping) and `CStarRuntime` (data-parallel C\* interpreter with 32 768 virtual processors).

### Modes (`scripts/modes/`)

State-machine scripts — one per server state. Managed by `server.js`; not user-selectable.

- **`idle.py`** — CM2-style random red blinking (idle state)
- **`drawing.py`** — Interactive drawing with fade-out (drawing state)
- **`stream.py`** — Raw frame stream renderer (tcp\_streaming state)
- **`program.py`** — Program execution mode (program state). Preloads all C\* programs at startup and accepts stdin commands to run both C\* and Python programs. Stays alive across program switches for instant transitions.

### Programs (`scripts/programs/`)

User-selectable programs, available via the web UI program selector.

- **`rainbow.py`** — Rainbow test pattern
- **`all_white.py`** — Solid white test pattern

## C\* programs

The `scripts/programs/cstar/` directory contains data-parallel C\* programs that run on the emulator's `CStarRuntime` (32 768 virtual processors, 16 per chip, mapped to the 2048-LED display). These are **preloaded at startup** by `modes/program.py` and automatically shown in the web UI. Switching between programs is instant because the program mode process stays alive and reuses the parsed programs.

`random_blink.cstar` is excluded from the selector since the idle mode already covers that pattern.

Available programs:
- **wave_front** — Running sine wave across chip indices
- **checker_pulse** — Alternating checkerboard pattern
- **ring_scan** — Scanning ring with variable width
- **news_diffusion** — 5-point stencil diffusion using NEWS inter-processor communication
- **mandelbrot** — Static Mandelbrot set (parallel escape-time iteration)
- **mandelbrot_zoom** — Animated Mandelbrot zoom

To add a new C\* program, place a `.cstar` file in `scripts/programs/cstar/`. It will automatically appear in the web UI.

## Notes

- The server uses ports 80 and 1337. Adjust in `server/server.js` if needed.
- If you run on a non-Raspberry Pi system, the `rpi_ws281x` library will not work.
- To add a new Python animation, create a script in `scripts/programs/` that imports `cm_display` from `lib/`. See `rainbow.py` for a minimal example. It will auto-appear in the web UI.
- To add a new C\* program, place a `.cstar` file in `scripts/programs/cstar/`. See the existing examples for the supported language constructs.
