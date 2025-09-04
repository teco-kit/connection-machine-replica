#!/usr/bin/env python3
import sys
import json
import time
import threading
import random
import select
from rpi_ws281x import PixelStrip, Color, WS2811_STRIP_GRB

# --- Configuration ---
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

# --- State Management ---
display_mode = 'animation'  # 'animation' or 'drawing'
led_states = [[0, 0] for _ in range(LED_COUNT)]  # [brightness, time_activated]
strip_lock = threading.Lock()
mode_lock = threading.Lock()
last_drawing_input = 0  # Timestamp of last drawing input
AUTO_RETURN_TO_ANIMATION = 3.0  # Seconds to wait before returning to animation
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, STRIP_TYPE)

# --- Mapping Logic ---
def xy_to_physical_index(x, y):
    res = y * 16
    if y % 2 == 0:
        res = res + x
    else:
        res = res + (15 - x)
    return res

# --- Animation Functions ---
def random_blink_frame(probability=0.33):
    """Generate a random blinking frame for animation mode"""
    frame = []
    for i in range(LED_COUNT):
        if random.random() < probability:
            frame.append(255)  # On
        else:
            frame.append(0)    # Off
    return frame

# --- Display Loop ---
def display_loop():
    global display_mode, last_drawing_input
    animation_last_update = 0
    animation_frame_interval = 0.15  # 150ms between animation updates
    
    while True:
        start_time = time.time()
        
        # Check if we should return to animation mode
        with mode_lock:
            if display_mode == 'drawing' and last_drawing_input > 0:
                if start_time - last_drawing_input > AUTO_RETURN_TO_ANIMATION:
                    print("Returning to animation mode after 3 seconds of inactivity", file=sys.stderr, flush=True)
                    display_mode = 'animation'
                    last_drawing_input = 0
                    # Clear all LED states
                    for i in range(LED_COUNT):
                        led_states[i] = [0, 0]
                        strip.setPixelColor(i, Color(0, 0, 0))
            
            current_mode = display_mode
        
        if current_mode == 'animation':
            # Animation mode: update less frequently for blinking effect
            if start_time - animation_last_update >= animation_frame_interval:
                animation_frame = random_blink_frame(probability=0.33)
                for i in range(LED_COUNT):
                    brightness = animation_frame[i]
                    strip.setPixelColor(i, Color(brightness, 0, 0))  # RED
                animation_last_update = start_time
        
        elif current_mode == 'drawing':
            # Drawing mode: update LED states with fade effects
            now = start_time
            for i in range(LED_COUNT):
                brightness, activated_time = led_states[i]
                if activated_time == 0:
                    continue

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
                strip.setPixelColor(i, Color(new_brightness, 0, 0))  # RED

        with strip_lock:
            strip.show()

        # Frame rate limiting
        elapsed_time = time.time() - start_time
        sleep_time = (1.0 / FRAME_RATE) - elapsed_time
        if sleep_time > 0:
            time.sleep(sleep_time)

# --- Input Handler ---
def handle_input():
    global display_mode, last_drawing_input
    
    while True:
        # Check if there's input available (non-blocking)
        if select.select([sys.stdin], [], [], 0.1)[0]:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                # Update last drawing input timestamp
                current_time = time.time()
                
                # Switch to drawing mode on any input
                with mode_lock:
                    if display_mode != 'drawing':
                        print("Switching to drawing mode", file=sys.stderr, flush=True)
                        display_mode = 'drawing'
                        # Clear animation state
                        for i in range(LED_COUNT):
                            if led_states[i][1] == 0:  # Only clear non-drawing LEDs
                                strip.setPixelColor(i, Color(0, 0, 0))
                    
                    last_drawing_input = current_time
                
                # Process drawing input
                data = json.loads(line)
                x, y = data.get('x'), data.get('y')
                index = xy_to_physical_index(x, y)
                if 0 <= index < LED_COUNT:
                    led_states[index] = [255, current_time]
                    
            except (json.JSONDecodeError, AttributeError, IndexError, TypeError, ValueError):
                pass
        else:
            # No input available, continue
            time.sleep(0.01)

# --- Mode Switch Handler ---
def handle_mode_commands():
    global display_mode
    
    while True:
        try:
            # Listen for mode switch commands from server
            # This could be extended to listen on a separate port or pipe
            time.sleep(0.1)
        except:
            break

# --- Main ---
def main():
    global display_mode
    
    strip.begin()
    
    # Start with animation mode
    with mode_lock:
        display_mode = 'animation'
    
    # Start threads
    display_thread = threading.Thread(target=display_loop, daemon=True)
    input_thread = threading.Thread(target=handle_input, daemon=True)
    
    display_thread.start()
    input_thread.start()
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        # Clean up on exit
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

if __name__ == '__main__':
    main()
