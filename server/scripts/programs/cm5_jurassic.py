#!/usr/bin/env python3
"""
CM-5 Jurassic Park front-panel chaser lights.

Faithful port of the original Adafruit chaser.py by Phillip Burgess for
Adafruit Industries (SPDX-License-Identifier: MIT).

Each row holds a 16-bit integer; one bit per column. Every frame the
integer shifts one step left or right (alternating in bands of 4 rows)
and a new random bit enters from the leading edge. 6 FPS and binary
on/off per LED — the deliberate chunkiness IS the look from the film.
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, STRIP_WIDTH, STRIP_HEIGHT, red

DENSITY    = 30    # Percentage of bits set (0-100), matches original
FPS        = 6     # Intentionally slow — one shift per frame like the original
BRIGHTNESS = 220   # LED brightness (0-255)

MASK = (1 << STRIP_WIDTH) - 1  # 0xFFFF for a 16-column display


def main():
    with CMDisplay() as display:
        # One 16-bit integer per physical row. Bit N → column N.
        bits = [0] * STRIP_HEIGHT
        for row in range(STRIP_HEIGHT):
            for b in range(STRIP_WIDTH):
                if random.randint(1, 100) <= DENSITY:
                    bits[row] |= 1 << b

        interval = 1.0 / FPS
        last = time.monotonic()

        try:
            while True:
                display.clear()

                for row in range(STRIP_HEIGHT):
                    # New random bit injected at the leading edge each frame
                    new_bit = 1 if random.randint(1, 100) <= DENSITY else 0

                    if row & 4:
                        # Drift right: shift integer left, new bit enters at col 0
                        bits[row] = ((bits[row] << 1) & MASK) | new_bit
                    else:
                        # Drift left: shift integer right, new bit enters at col 15
                        bits[row] = (bits[row] >> 1) | (new_bit << (STRIP_WIDTH - 1))

                    # Draw each set bit as a lit LED
                    pat = bits[row]
                    col = 0
                    while pat:
                        if pat & 1:
                            display.set_pixel_xy(col, row, red(BRIGHTNESS))
                        pat >>= 1
                        col += 1

                display.show()

                # Busy-wait like the original for consistent frame timing
                while (time.monotonic() - last) < interval:
                    pass
                last = time.monotonic()

        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
