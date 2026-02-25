#!/usr/bin/env python3
"""
Rick Roll GIF player for the Connection Machine replica.

Plays rick_roll.gif on the physical 32×64 LED display (2×2 panel grid).
Requires Pillow: pip3 install Pillow

Visual coordinate mapping to the 16×128 LED strip:
    Left half  (x  0-15): strip x = x,      strip y = y
    Right half (x 16-31): strip x = x - 16,  strip y = y + 64
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, rgb

try:
    from PIL import Image
except ImportError:
    print("Pillow is required: sudo pip3 install Pillow", file=sys.stderr)
    sys.exit(1)

# Visual display dimensions
DISPLAY_W = 32
DISPLAY_H = 64

# Path to gif (sibling of this script)
GIF_PATH = os.path.join(os.path.dirname(__file__), 'rick_roll.gif')


def load_frames(path):
    """Load all GIF frames, resize to DISPLAY_W×DISPLAY_H, return list of
    (pixels_2d, duration_s) tuples. pixels_2d[y][x] = (r, g, b)."""
    frames = []
    img = Image.open(path)
    try:
        while True:
            frame = img.convert('RGB').resize(
                (DISPLAY_W, DISPLAY_H), Image.LANCZOS
            )
            # Default GIF delay is 100ms if not specified
            duration = img.info.get('duration', 100) / 1000.0
            # Clamp: some GIFs have unreasonably small values (< 20 ms)
            duration = max(0.02, duration)

            pixels = [
                [frame.getpixel((x, y)) for x in range(DISPLAY_W)]
                for y in range(DISPLAY_H)
            ]
            frames.append((pixels, duration))
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    return frames


def render_frame(display, pixels):
    """Write one frame to the LED display."""
    display.clear()
    for y in range(DISPLAY_H):
        for x in range(DISPLAY_W):
            r, g, b = pixels[y][x]
            if r > 4 or g > 4 or b > 4:  # skip near-black pixels for speed
                if x < 16:
                    display.set_pixel_xy(x, y, rgb(r, g, b))
                else:
                    display.set_pixel_xy(x - 16, y + 64, rgb(r, g, b))
    display.show()


def main():
    if not os.path.isfile(GIF_PATH):
        print(f"GIF not found: {GIF_PATH}", file=sys.stderr)
        sys.exit(1)

    print("Loading GIF frames...", file=sys.stderr)
    frames = load_frames(GIF_PATH)
    print(f"Loaded {len(frames)} frames.", file=sys.stderr)

    with CMDisplay() as display:
        try:
            while True:
                for pixels, duration in frames:
                    t0 = time.monotonic()
                    render_frame(display, pixels)
                    elapsed = time.monotonic() - t0
                    remaining = duration - elapsed
                    if remaining > 0:
                        time.sleep(remaining)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
