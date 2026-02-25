#!/usr/bin/env python3
"""
Connection Machine idle animation + interactive drawing mode.

Launched by server.js as the default display process.
- Starts in **animation** mode (random red blinking, CM2-style).
- Switches to **drawing** mode when JSON draw commands arrive on stdin.
- Reverts to animation after a few seconds of drawing inactivity.
- Accepts JSON commands on stdin to tune probability and speed on the fly.
"""

import json
import random
import select
import sys
import time
import threading

from cm_display import CMDisplay, LED_COUNT, red, OFF


# ── Tunables ──────────────────────────────────────────────────────────────────

FRAME_RATE = 60.0
STAY_ON_DURATION = 0.8        # seconds a drawn pixel stays at full brightness
FADE_OUT_DURATION = 1.2       # seconds for the fade-out tail
AUTO_RETURN_TO_ANIMATION = 3.0  # seconds of inactivity before reverting
DEFAULT_VALUES_RESET_TIME = 30.0  # seconds before resetting probability/speed

ANIMATION_PROBABILITY_DEFAULT = 0.33
ANIMATION_FRAME_INTERVAL_DEFAULT = 0.15  # 150 ms


# ── Shared state ──────────────────────────────────────────────────────────────

display = CMDisplay()

animation_probability = ANIMATION_PROBABILITY_DEFAULT
animation_frame_interval = ANIMATION_FRAME_INTERVAL_DEFAULT
display_mode = "animation"          # 'animation' | 'drawing'
led_states = [[0, 0.0] for _ in range(LED_COUNT)]  # [brightness, time_activated]
last_drawing_input = 0.0
last_revert_to_default_values = 0.0

mode_lock = threading.Lock()


# ── Animation ─────────────────────────────────────────────────────────────────

def random_blink_frame(probability=None):
    """Return a full-frame list of brightness values (0 or 255)."""
    p = probability if probability is not None else animation_probability
    return [255 if random.random() < p else 0 for _ in range(LED_COUNT)]


# ── Display loop ──────────────────────────────────────────────────────────────

def display_loop():
    global display_mode, last_drawing_input
    global animation_probability, animation_frame_interval
    global last_revert_to_default_values

    animation_last_update = 0.0

    while True:
        now = time.time()

        with mode_lock:
            # Auto-revert to animation after drawing inactivity
            if display_mode == "drawing" and last_drawing_input > 0:
                if now - last_drawing_input > AUTO_RETURN_TO_ANIMATION:
                    display_mode = "animation"
                    last_drawing_input = 0.0
                    for i in range(LED_COUNT):
                        led_states[i] = [0, 0.0]
                        display.set_pixel(i, OFF)

            # Reset tunables to defaults after timeout
            if last_revert_to_default_values > 0 and now - last_revert_to_default_values > DEFAULT_VALUES_RESET_TIME:
                animation_probability = ANIMATION_PROBABILITY_DEFAULT
                animation_frame_interval = ANIMATION_FRAME_INTERVAL_DEFAULT
                last_revert_to_default_values = 0.0

            current_mode = display_mode

        # --- Animation mode ---
        if current_mode == "animation":
            if now - animation_last_update >= animation_frame_interval:
                frame = random_blink_frame()
                for i in range(LED_COUNT):
                    display.set_pixel(i, red(frame[i]))
                animation_last_update = now

        # --- Drawing mode ---
        elif current_mode == "drawing":
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

        # Frame-rate limiter
        sleep = (1.0 / FRAME_RATE) - (time.time() - now)
        if sleep > 0:
            time.sleep(sleep)


# ── Stdin command handler ─────────────────────────────────────────────────────

def input_loop():
    global display_mode, last_drawing_input
    global animation_probability, animation_frame_interval
    global last_revert_to_default_values

    while True:
        if not select.select([sys.stdin], [], [], 0.1)[0]:
            time.sleep(0.01)
            continue

        line = sys.stdin.readline()
        if not line:
            break

        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        msg_type = data.get("type", "draw")

        if msg_type == "probability":
            animation_probability = max(0.0, min(1.0, data.get("value", 0.33)))
            last_revert_to_default_values = time.time()

        elif msg_type == "speed":
            animation_frame_interval = max(0.05, min(0.5, data.get("value", 0.15)))
            last_revert_to_default_values = time.time()

        elif msg_type == "draw":
            current_time = time.time()
            with mode_lock:
                if display_mode != "drawing":
                    display_mode = "drawing"
                    for i in range(LED_COUNT):
                        if led_states[i][1] == 0:
                            display.set_pixel(i, OFF)
                last_drawing_input = current_time

            x, y = data.get("x"), data.get("y")
            if x is not None and y is not None:
                index = CMDisplay.xy_to_index(x, y)
                if 0 <= index < LED_COUNT:
                    led_states[index] = [255, current_time]


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    display.begin()

    with mode_lock:
        globals()["display_mode"] = "animation"

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
