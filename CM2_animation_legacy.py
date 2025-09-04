#!/usr/bin/env python3
import time
import random
from rpi_ws281x import PixelStrip, Color

# Matrix layout
MATRIX_WIDTH = 38
MATRIX_HEIGHT_PER_MATRIX = 32
NUM_MATRICES = 4  # <-- CHANGE THIS to how many vertical matrices you stack
MATRIX_HEIGHT = MATRIX_HEIGHT_PER_MATRIX * NUM_MATRICES
LED_COUNT = MATRIX_WIDTH * MATRIX_HEIGHT


LED_PIN = 21
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 60
LED_INVERT = False
LED_CHANNEL = 0

# Initialize strip
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                   LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# Serpentine mapping
def xy_to_index(x, y, width=MATRIX_WIDTH, serpentine=True):
    if serpentine and y % 2 == 1:
        x = width - 1 - x
    return y * width + x

# Check if (x, y) is allowed to be lit based on pattern
def is_active_pixel(x):
    if 0 <= x < 16:
        return x % 2 == 0  # Even indexes only
    elif 16 <= x < 22:
        return False
    elif 22 <= x < 38:
        return x % 2 == 1  # Odd indexes only
    else:
        return False

# Red blinking noise within active pixels
def patterned_red_noise(probability=0.2):
    for y in range(MATRIX_HEIGHT_PER_MATRIX):
        for x in range(MATRIX_WIDTH):
            if is_active_pixel(x) and random.random() < probability:
                color = Color(0, 255, 0)
            else:
                color = Color(0, 0, 0)

            for i in range(NUM_MATRICES):
                y_offset = y + (i * MATRIX_HEIGHT_PER_MATRIX)
                index = xy_to_index(x, y_offset)
                strip.setPixelColor(index, color)

    strip.show()

# Main loop
try:
    while True:
        patterned_red_noise(probability=0.33)
        time.sleep(0.05)

except KeyboardInterrupt:
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
