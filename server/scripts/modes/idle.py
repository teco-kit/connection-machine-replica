#!/usr/bin/env python3
"""
Connection Machine idle animation.

Displays the classic CM2-style random red blinking pattern.
Accepts JSON commands on stdin to adjust probability and speed.
Exits cleanly when stdin closes (server kills the process).
"""

import json
import os
import random
import select
import sys
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, LED_COUNT, red


# ── Defaults ──────────────────────────────────────────────────────────────────

FRAME_RATE = 60.0
PROBABILITY_DEFAULT = 0.33
FRAME_INTERVAL_DEFAULT = 0.15   # 150 ms between blink updates
DEFAULT_VALUES_RESET_TIME = 30.0  # revert tunables after this many seconds


# ── State ─────────────────────────────────────────────────────────────────────

display = CMDisplay()
probability = PROBABILITY_DEFAULT
frame_interval = FRAME_INTERVAL_DEFAULT
last_tunable_change = 0.0
lock = threading.Lock()


# ── Display loop ──────────────────────────────────────────────────────────────

def display_loop():
    global probability, frame_interval, last_tunable_change

    last_update = 0.0

    while True:
        now = time.time()

        with lock:
            # Auto-reset tunables after timeout
            if last_tunable_change > 0 and now - last_tunable_change > DEFAULT_VALUES_RESET_TIME:
                probability = PROBABILITY_DEFAULT
                frame_interval = FRAME_INTERVAL_DEFAULT
                last_tunable_change = 0.0

            p = probability
            interval = frame_interval

        if now - last_update >= interval:
            for i in range(LED_COUNT):
                brightness = 255 if random.random() < p else 0
                display.set_pixel(i, red(brightness))
            last_update = now

        display.show()

        sleep = (1.0 / FRAME_RATE) - (time.time() - now)
        if sleep > 0:
            time.sleep(sleep)


# ── Stdin listener (probability / speed commands) ─────────────────────────────

def input_loop():
    global probability, frame_interval, last_tunable_change

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

        msg_type = data.get("type")

        with lock:
            if msg_type == "probability":
                probability = max(0.0, min(1.0, data.get("value", PROBABILITY_DEFAULT)))
                last_tunable_change = time.time()
            elif msg_type == "speed":
                frame_interval = max(0.05, min(0.5, data.get("value", FRAME_INTERVAL_DEFAULT)))
                last_tunable_change = time.time()


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
