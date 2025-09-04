#!/usr/bin/env python3
import sys
import time
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

# --- Main ---
def main():
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, STRIP_TYPE)
    strip.begin()

    try:
        while True:
            # The data stream is a flat 2048-byte array that maps directly to the LEDs
            frame_data = sys.stdin.buffer.read(LED_COUNT)

            if not frame_data or len(frame_data) != LED_COUNT:
                break

            for i in range(LED_COUNT):
                brightness = frame_data[i]
                # The index `i` corresponds directly to the physical LED index
                # because the hardware handles the serpentine layout.
                strip.setPixelColor(i, Color(brightness, 0, 0)) # RED

            strip.show()

    except KeyboardInterrupt:
        pass
    finally:
        # Clean up on exit
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

if __name__ == '__main__':
    main()