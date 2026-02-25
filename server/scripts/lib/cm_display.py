#!/usr/bin/env python3
"""
Connection Machine Replica — LED Display API

Provides a single, clean interface to the physical LED hardware.
All scripts (idle animation, drawing, TCP streaming, test patterns, future
C* emulator, …) import this module instead of talking to rpi_ws281x directly.

Physical setup
──────────────
Four 16×32 WS2815 panels arranged in a 2×2 grid and daisy-chained into one
serpentine strip of 2048 LEDs (16 columns × 128 rows).

Chain order:
    Panel 1 (TL)  →  Panel 2 (BL)  →  Panel 3 (TR)  →  Panel 4 (BR)
    rows 0–31        rows 32–63       rows 64–95       rows 96–127

    ┌────────────┬────────────┐
    │  Panel 1   │  Panel 3   │   rows  0–31  /  64–95
    ├────────────┼────────────┤
    │  Panel 2   │  Panel 4   │   rows 32–63  /  96–127
    └────────────┴────────────┘

The web UI maps this 16×128 strip back into the visual 2×2 layout.
"""

from __future__ import annotations

import colorsys
import contextlib
import threading
from typing import Optional, Tuple

from rpi_ws281x import PixelStrip, Color, WS2811_STRIP_GRB


# ── Hardware constants ────────────────────────────────────────────────────────

PANEL_WIDTH = 16
PANEL_HEIGHT = 32
PANELS_X = 2
PANELS_Y = 2

STRIP_WIDTH = PANEL_WIDTH                          # 16
STRIP_HEIGHT = PANEL_HEIGHT * PANELS_X * PANELS_Y  # 128
LED_COUNT = STRIP_WIDTH * STRIP_HEIGHT              # 2048

LED_PIN = 21
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 60
LED_INVERT = False
LED_CHANNEL = 0
STRIP_TYPE = WS2811_STRIP_GRB


# ── Colour helpers ────────────────────────────────────────────────────────────

def rgb(r: int, g: int, b: int) -> int:
    """Convenience wrapper around ``rpi_ws281x.Color``."""
    return Color(r, g, b)


RED   = rgb(255, 0, 0)
GREEN = rgb(0, 255, 0)
BLUE  = rgb(0, 0, 255)
WHITE = rgb(255, 255, 255)
OFF   = rgb(0, 0, 0)


def red(brightness: int) -> int:
    """Return a red ``Color`` at the given brightness (0-255)."""
    return Color(brightness, 0, 0)


def hsv_to_color(h: float, s: float = 1.0, v: float = 1.0) -> int:
    """Convert HSV (h 0-360, s/v 0-1) to an ``rpi_ws281x.Color``.

    Useful for rainbow effects and smooth colour transitions.
    """
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, s, v)
    return Color(int(r * 255), int(g * 255), int(b * 255))


# ── Display API ───────────────────────────────────────────────────────────────

class CMDisplay:
    """Thread-safe interface to the Connection Machine LED display.

    Usage::

        with CMDisplay() as display:
            display.fill(RED)
            display.show()

    Or without a context manager::

        display = CMDisplay()
        display.begin()
        ...
        display.cleanup()
    """

    def __init__(self, brightness: Optional[int] = None) -> None:
        self._brightness = brightness or LED_BRIGHTNESS
        self._strip = PixelStrip(
            LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
            LED_INVERT, self._brightness, LED_CHANNEL, STRIP_TYPE,
        )
        self._lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def begin(self) -> None:
        """Initialise the LED strip hardware."""
        self._strip.begin()

    def cleanup(self) -> None:
        """Turn off every LED and push the result to hardware."""
        self.clear()
        self.show()

    def __enter__(self) -> "CMDisplay":
        self.begin()
        return self

    def __exit__(self, *exc) -> None:
        self.cleanup()

    # ── Coordinate mapping ────────────────────────────────────────────────

    @staticmethod
    def xy_to_index(x: int, y: int) -> int:
        """Convert (x, y) to the physical LED index on the serpentine strip.

        Parameters
        ----------
        x : int  Column (0 … STRIP_WIDTH-1)
        y : int  Row    (0 … STRIP_HEIGHT-1)

        Returns
        -------
        int  Physical LED index (0 … LED_COUNT-1)
        """
        idx = y * STRIP_WIDTH
        if y % 2 == 0:
            idx += x
        else:
            idx += (STRIP_WIDTH - 1 - x)
        return idx

    # ── Single-pixel operations ───────────────────────────────────────────

    def set_pixel(self, index: int, color: int) -> None:
        """Set pixel at *physical index* to *color*."""
        self._strip.setPixelColor(index, color)

    def set_pixel_xy(self, x: int, y: int, color: int) -> None:
        """Set pixel at (x, y) to *color*, applying serpentine mapping."""
        self._strip.setPixelColor(self.xy_to_index(x, y), color)

    def get_pixel(self, index: int) -> int:
        """Read back the colour stored for *index* (from driver buffer)."""
        return self._strip.getPixelColor(index)

    # ── Bulk operations ───────────────────────────────────────────────────

    def fill(self, color: int) -> None:
        """Set every LED to *color* (call ``show()`` to push)."""
        for i in range(LED_COUNT):
            self._strip.setPixelColor(i, color)

    def clear(self) -> None:
        """Turn off every LED (call ``show()`` to push)."""
        self.fill(OFF)

    def set_frame(self, colors: list[int] | bytes | bytearray) -> None:
        """Set all LEDs from a flat sequence.

        *colors* may be:
        - A list/tuple of ``Color`` ints (length ``LED_COUNT``).
        - A ``bytes``/``bytearray`` of single-channel brightness values
          (length ``LED_COUNT``), which will be mapped to red.
        """
        if isinstance(colors, (bytes, bytearray)):
            for i in range(LED_COUNT):
                self._strip.setPixelColor(i, red(colors[i]))
        else:
            for i in range(LED_COUNT):
                self._strip.setPixelColor(i, colors[i])

    # ── Output ────────────────────────────────────────────────────────────

    def show(self) -> None:
        """Push the current pixel buffer to the hardware (thread-safe)."""
        with self._lock:
            self._strip.show()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def led_count(self) -> int:
        return LED_COUNT

    @property
    def width(self) -> int:
        return STRIP_WIDTH

    @property
    def height(self) -> int:
        return STRIP_HEIGHT
