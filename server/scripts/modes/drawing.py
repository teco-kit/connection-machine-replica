#!/usr/bin/env python3
"""
Connection Machine interactive drawing mode.

Reads JSON draw commands from stdin (piped by server.js from WebSocket clients).
Each drawn pixel lights up red and fades out over ~2 seconds.
Exits cleanly when stdin closes.
"""

import json
import os
import select
import sys
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, LED_COUNT, red, OFF


# ── Tunables ──────────────────────────────────────────────────────────────────

FRAME_RATE = 60.0
STAY_ON_DURATION = 0.8    # seconds at full brightness
FADE_OUT_DURATION = 1.2   # seconds for the fade tail


# ── State ─────────────────────────────────────────────────────────────────────

display = CMDisplay()
led_states = [[0, 0.0] for _ in range(LED_COUNT)]  # [brightness, time_activated]


# ── Display loop ──────────────────────────────────────────────────────────────

def display_loop():
    while True:
        now = time.time()

        for i in range(LED_COUNT):
            brightness, activated = led_states[i]
            if activated == 0:
                continue

            elapsed = now - activated
            if elapsed < STAY_ON_DURATION:
                new_brightness = 255
            elif elapsed < STAY_ON_DURATION + FADE_OUT_DURATION:
                fade = (elapsed - STAY_ON_DURATION) / FADE_OUT_DURATION
                new_brightness = int(255 * (1 - fade))
            else:
                new_brightness = 0
                led_states[i] = [0, 0.0]

            led_states[i][0] = new_brightness
            display.set_pixel(i, red(new_brightness))

        display.show()

        sleep = (1.0 / FRAME_RATE) - (time.time() - now)
        if sleep > 0:
            time.sleep(sleep)


# ── Stdin listener ────────────────────────────────────────────────────────────

def input_loop():
    while True:
        if not select.select([sys.stdin], [], [], 0.1)[0]:
            continue

        line = sys.stdin.readline()
        if not line:
            break

        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if data.get("type", "draw") != "draw":
            continue

        x, y = data.get("x"), data.get("y")
        if x is not None and y is not None:
            index = CMDisplay.xy_to_index(x, y)
            if 0 <= index < LED_COUNT:
                led_states[index] = [255, time.time()]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    display.begin()

    threading.Thread(target=display_loop, daemon=True).start()
    threading.Thread(target=input_loop, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        display.cleanup()


if __name__ == "__main__":
    main()
