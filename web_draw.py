#!/usr/bin/env python3
import sys
import json
import time
import threading
import select
from rpi_ws281x import PixelStrip, Color, WS2811_STRIP_GRB

# --- Configuration (FINAL SIMPLE Layout - CONFIRMED) ---
MATRIX_WIDTH = 16
MATRIX_HEIGHT = 128
LED_COUNT = MATRIX_WIDTH * MATRIX_HEIGHT

LED_PIN = 21
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 60
LED_INVERT = False
LED_CHANNEL = 0
STRIP_TYPE = WS2811_STRIP_GRB

# --- Animation & Timing ---
FRAME_RATE = 60.0
STAY_ON_DURATION = 0.8
FADE_OUT_DURATION = 1.2

# --- High-Performance State ---
led_states = [[0, 0] for _ in range(LED_COUNT)] # [brightness, time_activated]
strip_lock = threading.Lock()
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, STRIP_TYPE)

# --- Mapping Logic (Simple Raster Scan - Confirmed Working) ---
# def xy_to_physical_index(x, y):
#     # The hardware handles serpentine automatically.
#     return y * MATRIX_WIDTH + x

def xy_to_physical_index(x, y):
    res = y * 16
    if y % 2 == 0:
        res = res + x
    else:
        res = res + (15 - x)
    return res



# --- High-Performance Animation Loop ---
def animation_loop():
    while True:
        start_time = time.time()
        now = start_time
        
        for i in range(LED_COUNT):
            brightness, activated_time = led_states[i]
            if activated_time == 0: continue

            time_since_activation = now - activated_time
            new_brightness = 0

            if time_since_activation < STAY_ON_DURATION:
                new_brightness = 255
            elif time_since_activation < STAY_ON_DURATION + FADE_OUT_DURATION:
                fade_progress = (time_since_activation - STAY_ON_DURATION) / FADE_OUT_DURATION
                new_brightness = int(255 * (1 - fade_progress))
            else:
                led_states[i] = [0, 0]

            led_states[i][0] = new_brightness
            # The led_states index `i` is already the physical index in this simple layout
            strip.setPixelColor(i, Color(new_brightness, 0, 0)) # RED

        with strip_lock:
            strip.show()

        elapsed_time = time.time() - start_time
        sleep_time = (1.0 / FRAME_RATE) - elapsed_time
        if sleep_time > 0:
            time.sleep(sleep_time)

# --- Main ---
def main():
    strip.begin()

    anim_thread = threading.Thread(target=animation_loop, daemon=True)
    anim_thread.start()

    try:
        for line in sys.stdin:
            try:
                data = json.loads(line)
                x, y = data.get('x'), data.get('y')
                # Convert web (x,y) to the simple raster index
                index = xy_to_physical_index(x, y)
                if 0 <= index < LED_COUNT:
                    led_states[index] = [255, time.time()]
            except (json.JSONDecodeError, AttributeError, IndexError, TypeError): pass
    except KeyboardInterrupt:
        pass
    finally:
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

if __name__ == '''__main__''':
    main()