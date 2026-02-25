#!/usr/bin/env python3
"""
Solid white test pattern.

Fills every LED with white. Useful for checking dead pixels and power draw.
Optional argument: update interval in seconds (default 2.0).
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, WHITE


DEFAULT_UPDATE_INTERVAL = 2.0  # seconds


def main():
    interval = DEFAULT_UPDATE_INTERVAL
    if len(sys.argv) > 1:
        try:
            interval = float(sys.argv[1])
            assert interval > 0
        except (ValueError, AssertionError):
            print("Usage: python3 all_white.py [interval_in_seconds]")
            sys.exit(1)

    with CMDisplay() as display:
        while True:
            display.fill(WHITE)
            display.show()
            time.sleep(interval)


if __name__ == "__main__":
    main()
