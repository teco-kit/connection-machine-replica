#!/usr/bin/env python3
"""
Rainbow test pattern.

Scrolls a full-spectrum rainbow across the LED strip.
Optional argument: update interval in seconds (default 0.1).
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, LED_COUNT, hsv_to_color


DEFAULT_UPDATE_INTERVAL = 0.1  # seconds


def main():
    interval = DEFAULT_UPDATE_INTERVAL
    if len(sys.argv) > 1:
        try:
            interval = float(sys.argv[1])
            assert interval > 0
        except (ValueError, AssertionError):
            print("Usage: python3 rainbow.py [interval_in_seconds]")
            sys.exit(1)

    with CMDisplay() as display:
        hue_offset = 0.0
        while True:
            for i in range(LED_COUNT):
                hue = (i * 360.0 / LED_COUNT + hue_offset) % 360
                display.set_pixel(i, hsv_to_color(hue))
            display.show()
            hue_offset = (hue_offset + 5) % 360
            time.sleep(interval)


if __name__ == "__main__":
    main()
