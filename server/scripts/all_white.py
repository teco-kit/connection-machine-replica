#!/usr/bin/env python3
import time
import sys
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
DEFAULT_UPDATE_INTERVAL = 2.0  # Default update interval (seconds)

def main():
    # Parse command line arguments
    if len(sys.argv) > 1:
        try:
            UPDATE_INTERVAL = float(sys.argv[1])
            if UPDATE_INTERVAL <= 0:
                print("Error: Update interval must be positive!")
                print("Usage: python3 all_white.py [interval_in_seconds]")
                sys.exit(1)
        except ValueError:
            print("Error: Invalid number format!")
            print("Usage: python3 all_white.py [interval_in_seconds]")
            sys.exit(1)
    else:
        UPDATE_INTERVAL = DEFAULT_UPDATE_INTERVAL
    # Initialize the LED strip
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, STRIP_TYPE)
    strip.begin()
    
    try:
        print(f"Setting all LEDs to white, updating every {UPDATE_INTERVAL} seconds. Press Ctrl+C to exit.")
        
        # Main loop: continuously update LEDs
        while True:
            # Set all LEDs to white
            for i in range(LED_COUNT):
                strip.setPixelColor(i, Color(255, 255, 255))  # WHITE (R, G, B)
            strip.show()
            
            # Wait for the specified interval
            time.sleep(UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        print("\nStop")

if __name__ == '__main__':
    main()