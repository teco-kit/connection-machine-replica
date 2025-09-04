#!/usr/bin/env python3
import time
import random
from rpi_ws281x import PixelStrip, Color

# Matrix layout
LEDS_PER_ROW = 16  # 8 on left + 8 on right
ROWS_PER_PANEL = 32
NUM_PANELS = 4
TOTAL_ROWS = ROWS_PER_PANEL * NUM_PANELS
LED_COUNT = LEDS_PER_ROW * TOTAL_ROWS

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

# Serpentine mapping for your row layout
def xy_to_index(x, y, width=LEDS_PER_ROW, serpentine=True):
    if serpentine and y % 2 == 1:
        x = width - 1 - x
    return y * width + x

# Random blinking for all LEDs
def random_blink_animation(probability=0.33):
    for y in range(TOTAL_ROWS):
        for x in range(LEDS_PER_ROW):
            if random.random() < probability:
                color = Color(255, 0, 0)  # Green (was red in original)
            else:
                color = Color(0, 0, 0)    # Off

            index = xy_to_index(x, y)
            strip.setPixelColor(index, color)

    strip.show()

# Main loop
try:
    while True:
        random_blink_animation(probability=0.33)
        time.sleep(0.15)

except KeyboardInterrupt:
    # Turn off all LEDs on exit
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()