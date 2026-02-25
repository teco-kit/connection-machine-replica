#!/usr/bin/env python3
"""
TCP Breakout test client for Connection Machine Replica.

Sends 2048-byte frames (red-channel brightness) to the Pi TCP stream server.
The game runs autonomously (simple paddle AI), so it is useful as a quick
end-to-end connectivity and mapping test from macOS.
"""

from __future__ import annotations

import argparse
import random
import socket
import sys
import time


VIEW_W = 32
VIEW_H = 64
STRIP_W = 16
STRIP_H = 128
LED_COUNT = STRIP_W * STRIP_H


def visual_to_strip_xy(x: int, y: int) -> tuple[int, int]:
    """Map visual 32x64 coordinates to physical 16x128 strip coordinates."""
    if x < 16 and y < 32:       # TL panel -> rows 0..31
        return x, y
    if x < 16 and y >= 32:      # BL panel -> rows 32..63
        return x, y
    if x >= 16 and y < 32:      # TR panel -> rows 64..95
        return x - 16, y + 64
    # BR panel -> rows 96..127
    return x - 16, y + 64


def strip_index(sx: int, sy: int) -> int:
    """Serpentine mapping for 16x128 strip."""
    base = sy * STRIP_W
    if sy % 2 == 0:
        return base + sx
    return base + (STRIP_W - 1 - sx)


def set_pixel(frame: bytearray, x: int, y: int, value: int) -> None:
    if not (0 <= x < VIEW_W and 0 <= y < VIEW_H):
        return
    sx, sy = visual_to_strip_xy(x, y)
    idx = strip_index(sx, sy)
    frame[idx] = max(0, min(255, value))


def draw_rect(frame: bytearray, x0: int, y0: int, w: int, h: int, value: int) -> None:
    for yy in range(y0, y0 + h):
        for xx in range(x0, x0 + w):
            set_pixel(frame, xx, yy, value)


def run(host: str, port: int, fps: float) -> None:
    brick_rows = 8
    brick_h = 2
    brick_w = 4
    brick_top = 3
    brick_gap_x = 0
    bricks_x = VIEW_W // (brick_w + brick_gap_x)
    bricks = [[True for _ in range(bricks_x)] for _ in range(brick_rows)]

    paddle_w = 7
    paddle_y = VIEW_H - 3
    paddle_x = (VIEW_W - paddle_w) // 2

    ball_x = VIEW_W // 2
    ball_y = VIEW_H // 2
    vx = random.choice([-1, 1])
    vy = -1

    score = 0
    frame_delay = 1.0 / max(1.0, fps)

    with socket.create_connection((host, port), timeout=5) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"Connected to {host}:{port}. Running Breakout stream...")

        while True:
            loop_start = time.time()

            # Paddle AI: move toward ball.
            paddle_center = paddle_x + paddle_w // 2
            if ball_x < paddle_center:
                paddle_x -= 1
            elif ball_x > paddle_center:
                paddle_x += 1
            paddle_x = max(0, min(VIEW_W - paddle_w, paddle_x))

            # Ball integration.
            next_x = ball_x + vx
            next_y = ball_y + vy

            # Wall collisions.
            if next_x < 0 or next_x >= VIEW_W:
                vx *= -1
                next_x = ball_x + vx
            if next_y < 0:
                vy *= -1
                next_y = ball_y + vy

            # Paddle collision.
            if next_y == paddle_y and paddle_x <= next_x < paddle_x + paddle_w and vy > 0:
                rel = next_x - paddle_x
                if rel < paddle_w // 3:
                    vx = -1
                elif rel > 2 * paddle_w // 3:
                    vx = 1
                vy = -1
                next_y = ball_y + vy

            # Brick collision.
            hit_brick = False
            if next_y >= brick_top:
                row = (next_y - brick_top) // brick_h
                if 0 <= row < brick_rows:
                    col = next_x // (brick_w + brick_gap_x)
                    local_x = next_x % (brick_w + brick_gap_x)
                    if col < bricks_x and local_x < brick_w and bricks[row][col]:
                        bricks[row][col] = False
                        score += 1
                        vy *= -1
                        next_y = ball_y + vy
                        hit_brick = True

            ball_x, ball_y = next_x, next_y

            # Missed paddle: reset ball only (keep bricks so run stays interesting).
            if ball_y >= VIEW_H - 1:
                ball_x = VIEW_W // 2
                ball_y = VIEW_H // 2
                vx = random.choice([-1, 1])
                vy = -1

            # If all bricks cleared, repopulate.
            if not any(any(row) for row in bricks):
                bricks = [[True for _ in range(bricks_x)] for _ in range(brick_rows)]

            # Render.
            frame = bytearray(LED_COUNT)

            # Bricks.
            for r in range(brick_rows):
                y0 = brick_top + r * brick_h
                for c in range(bricks_x):
                    if bricks[r][c]:
                        x0 = c * (brick_w + brick_gap_x)
                        draw_rect(frame, x0, y0, brick_w, brick_h, 170 if (r % 2) else 220)

            # Paddle + ball.
            draw_rect(frame, paddle_x, paddle_y, paddle_w, 1, 255)
            set_pixel(frame, ball_x, ball_y, 255)

            # Small score stripe on right edge.
            meter = min(VIEW_H, score // 2)
            for y in range(VIEW_H - meter, VIEW_H):
                set_pixel(frame, VIEW_W - 1, y, 120 if hit_brick else 80)

            sock.sendall(frame)

            elapsed = time.time() - loop_start
            sleep_for = frame_delay - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream Breakout test frames to CM TCP server.")
    parser.add_argument("--host", required=True, help="Raspberry Pi IP or hostname")
    parser.add_argument("--port", type=int, default=1337, help="TCP port (default: 1337)")
    parser.add_argument("--fps", type=float, default=30.0, help="Frame rate (default: 30)")
    args = parser.parse_args()

    try:
        run(args.host, args.port, args.fps)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
