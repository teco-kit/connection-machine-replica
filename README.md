# Connection Machine Replica: LED Matrix Server

This project recreates the iconic **Connection Machine 2 (CM2)** LED matrix display using modern WS281x RGB LEDs. The CM2, a legendary parallel supercomputer from the 1980s, featured a distinctive front panel with a 16×32 LED array that visualized processor activity. This replica faithfully reproduces that display by stacking four 16×32 matrices for a total of **2048 individually addressable LEDs** (16 × 128).

## What is this project?

The Connection Machine Replica is:

1. **Hardware accurate**: Four WS281x matrices stacked vertically to replicate the CM2's original LED layout
2. **Software controlled**: A Node.js server with WebSocket and TCP interfaces for real-time LED control
3. **Visualizer ready**: Can display animations, real-time data streams, or interactive web-based drawing
4. **Historically inspired**: Honors the CM2's presence-as-art aesthetic by recreating its most recognizable interface element

The server provides:

- An HTTP + WebSocket portal for interactive drawing on the matrix
- A raw TCP stream for pushing high-speed full LED frame data
- An idle animation mode that cycles when no clients are active  
- Automatic state transitions between drawing, streaming, and animation modes

## Hardware layout

The physical display consists of **four 16×32 WS281x matrices** stacked vertically:

```
┌──────────────────┐
│  Matrix 1 (32H)  │  (rows 0–31)
├──────────────────┤
│  Matrix 2 (32H)  │  (rows 32–63)
├──────────────────┤
│  Matrix 3 (32H)  │  (rows 64–95)
├──────────────────┤
│  Matrix 4 (32H)  │  (rows 96–127)
└──────────────────┘
Width: 16 pixels
Height: 128 pixels total
Total LEDs: 2048
```

Each matrix uses **serpentine wiring** (alternating row direction) to match the hardware layout, so the LED index maps directly to physical position.

```
server/
  public/                 # Web UI
  scripts/                # Python LED scripts
  package.json
  server.js
README.md
```

## Requirements

- Raspberry Pi (or compatible) with WS281x LEDs
- Python 3 and the `rpi_ws281x` library
- Node.js (for the web/TCP server)
- Root privileges for GPIO access (the server uses `sudo`)

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

- `server/server.js` launches Python scripts in `server/scripts/` using `sudo`.
- The server starts in idle animation mode.
- WebSocket messages from the portal switch the display into drawing mode.
- A TCP client can stream raw frame data to take control immediately.
- If no drawing or TCP data arrives, the system returns to animation mode.

## TCP streaming protocol

- Connect to TCP port `1337`.
- Send exactly `2048` bytes per frame (16 x 128 LEDs).
- Each byte is a red brightness value from 0 to 255.
- The byte order maps directly to LED index (the strip handles serpentine).

## Python scripts

- `CM2_animation_and_drawing.py`: Idle animation + drawing mode
- `stream_handler.py`: Raw frame stream renderer (TCP input via stdin)
- `all_white.py`: Solid white test
- `rainbow.py`: Rainbow test
- `CM2_legacy_animation.py`: Older animation (kept for reference)

## Notes

- The server uses ports 80 and 1337. Adjust in `server/server.js` if needed.
- If you run on a non-Raspberry Pi system, the WS281x library will not work.
