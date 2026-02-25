#!/usr/bin/env python3
"""
Raw TCP frame stream renderer.

Reads flat 2048-byte frames from stdin (piped by server.js from the TCP socket).
Each byte is a red brightness value (0-255) mapped directly to the LED index.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, LED_COUNT


def main():
    with CMDisplay() as display:
        while True:
            frame = sys.stdin.buffer.read(LED_COUNT)
            if not frame or len(frame) != LED_COUNT:
                break
            display.set_frame(frame)
            display.show()


if __name__ == "__main__":
    main()
