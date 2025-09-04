#!/usr/bin/env python3
import sys
import time
from rpi_ws281x import PixelStrip, Color, WS2811_STRIP_GRB

# --- Configuration (16x128 Layout) ---
MATRIX_WIDTH = 16
MATRIX_HEIGHT = 128
LED_COUNT = MATRIX_WIDTH * MATRIX_HEIGHT

LED_PIN = 21
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 200
LED_INVERT = False
LED_CHANNEL = 0
STRIP_TYPE = WS2811_STRIP_GRB

# --- Mapping Logic (Simple Raster Scan - No Serpentine) ---
def xy_to_physical_index(x, y):
    # The hardware appears to handle serpentine automatically.
    # We just provide a direct raster scan index.
    return y * MATRIX_WIDTH + x

# --- Main Debug Loop ---
def main():
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, STRIP_TYPE)
    strip.begin()

    try:
        print("Starting FINAL debug sequence (16x128, NO serpentine)...")
        for y in range(MATRIX_HEIGHT):
            for x in range(MATRIX_WIDTH):
                for i in range(LED_COUNT):
                    strip.setPixelColor(i, Color(0,0,0))

                physical_index = xy_to_physical_index(x, y)
                
                print(f"Lighting ({x}, {y}) -> Index: {physical_index}")
                strip.setPixelColor(physical_index, Color(255, 255, 255))
                strip.show()
                time.sleep(0.02)

    except KeyboardInterrupt:
        pass
    finally:
        print("Cleaning up.")
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

if __name__ == '''__main__''':
    main()
