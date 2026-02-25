#!/usr/bin/env python3
"""
CM-5 front-panel animation (Jurassic Park style).

Recreates the iconic Thinking Machines CM-5 front-panel display:
vertical columns of red LEDs with independent cascading wave fronts
scrolling downward at different speeds on a black background.

The display is split into two halves (left/right) with a dark gap
in the middle, mimicking the CM-5 cabinet layout.
"""

import os
import sys
import time
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, STRIP_WIDTH, STRIP_HEIGHT, red, OFF


# ── CM-5 column layout ───────────────────────────────────────────────────────
# The CM-5 had vertical columns of red LEDs in two groups with a gap.
# On our 16-wide display: columns 0-6 (left bank) and 9-15 (right bank),
# with columns 7-8 as the dark gap.

ACTIVE_COLS = list(range(0, 7)) + list(range(9, 16))


def main():
    with CMDisplay() as display:
        # Each active column gets its own independent cascade state
        columns = []
        for col in ACTIVE_COLS:
            columns.append({
                'x': col,
                'head': random.randint(0, STRIP_HEIGHT - 1),
                'speed': random.uniform(1.5, 5.0),     # rows per frame
                'trail': random.randint(8, 30),         # length of lit tail
                'accum': 0.0,                           # fractional row accumulator
            })

        try:
            while True:
                display.clear()

                for c in columns:
                    head = int(c['head'])
                    trail = c['trail']

                    # Draw the lit trail above (and wrapping around) the head
                    for t in range(trail):
                        y = (head - t) % STRIP_HEIGHT
                        # Brightness fades from full at head to dim at tail
                        brightness = int(255 * ((trail - t) / trail) ** 0.6)
                        if brightness > 0:
                            display.set_pixel_xy(c['x'], y, red(brightness))

                    # Advance head position (fractional for variable speed)
                    c['accum'] += c['speed']
                    while c['accum'] >= 1.0:
                        c['head'] = (c['head'] + 1) % STRIP_HEIGHT
                        c['accum'] -= 1.0

                    # Occasionally randomise speed/trail for organic feel
                    if random.random() < 0.005:
                        c['speed'] = random.uniform(1.5, 5.0)
                        c['trail'] = random.randint(8, 30)

                display.show()
                time.sleep(0.025)  # ~40 fps

        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
