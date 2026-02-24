#!/usr/bin/env python3
import time
import sys
import math
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

# --- Update Configuration ---
DEFAULT_UPDATE_INTERVAL = 0.1  # Default update interval (seconds)

def hsv_to_rgb(h, s, v):
    """Convert HSV color to RGB values (0-255)"""
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    
    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    
    r = int((r + m) * 255)
    g = int((g + m) * 255)
    b = int((b + m) * 255)
    
    return r, g, b

def rainbow_color(position, time_offset=0):
    """Generate rainbow color based on position and time"""
    # Create a rainbow that cycles through hues
    hue = (position * 360 / LED_COUNT + time_offset) % 360
    r, g, b = hsv_to_rgb(hue, 1.0, 1.0)  # Full saturation and brightness
    return Color(r, g, b)

def main():
    # Parse command line arguments
    if len(sys.argv) > 1:
        try:
            UPDATE_INTERVAL = float(sys.argv[1])
            if UPDATE_INTERVAL <= 0:
                print("Error: Update interval must be positive!")
                print("Usage: python3 rainbow.py [interval_in_seconds]")
                sys.exit(1)
        except ValueError:
            print("Error: Invalid number format!")
            print("Usage: python3 rainbow.py [interval_in_seconds]")
            sys.exit(1)
    else:
        UPDATE_INTERVAL = DEFAULT_UPDATE_INTERVAL
    
    # Initialize the LED strip
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, STRIP_TYPE)
    strip.begin()
    
    try:
        print(f"Starting rainbow mode, updating every {UPDATE_INTERVAL} seconds. Press Ctrl+C to exit.")
        
        time_offset = 0
        
        # Main loop: continuously update LEDs with rainbow colors
        while True:
            # Set all LEDs to rainbow colors
            for i in range(LED_COUNT):
                color = rainbow_color(i, time_offset)
                strip.setPixelColor(i, color)
            strip.show()
            
            # Advance the rainbow animation
            time_offset = (time_offset + 5) % 360  # Rotate hue by 5 degrees each update
            
            # Wait for the specified interval
            time.sleep(UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        print("\nStopping rainbow mode...")
        # Turn off all LEDs on exit
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

if __name__ == '__main__':
    main()