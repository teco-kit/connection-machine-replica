#!/usr/bin/env python3
"""
Strobe light effect — flashes all 2048 LEDs between full white and off.

Flash rate: ~10 Hz  (50 ms on, 50 ms off)
Brightness is deliberately limited to avoid blinding viewers.
"""

import sys
import time

sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, rgb, OFF

FLASH_ON_MS  = 50   # milliseconds white
FLASH_OFF_MS = 50   # milliseconds dark
WHITE = rgb(255, 255, 255)

def main():
    display = CMDisplay(brightness=80)

    try:
        while True:
            display.fill(WHITE)
            display.show()
            time.sleep(FLASH_ON_MS / 1000.0)

            display.fill(OFF)
            display.show()
            time.sleep(FLASH_OFF_MS / 1000.0)

    except KeyboardInterrupt:
        pass
    finally:
        display.fill(OFF)
        display.show()

if __name__ == '__main__':
    main()
