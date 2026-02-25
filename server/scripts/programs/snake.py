#!/usr/bin/env python3
"""
Snake game for the Connection Machine replica.

Playfield: 32 × 64 mapped across the 2×2 panel grid (each panel is 16 × 32).
Accepts direction commands on stdin (JSON: {"type":"direction","value":"up"}).
Sends {"type":"finished","program":"snake"} on game over.

Coordinate mapping to the physical 16×128 strip:
    Left half  (game x  0-15): strip x = game_x,      strip y = game_y
    Right half (game x 16-31): strip x = game_x - 16,  strip y = game_y + 64
"""

import json
import os
import random
import select
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from cm_display import CMDisplay, RED, GREEN, OFF, rgb, red


# ── Game constants ────────────────────────────────────────────────────────────

GAME_W = 32
GAME_H = 64
TICK_INTERVAL = 0.15  # seconds between moves

SNAKE_COLOR = GREEN
FOOD_COLOR = RED
HEAD_COLOR = rgb(255, 80, 0)  # orange head so you can tell direction


# ── Coordinate mapping ────────────────────────────────────────────────────────

def game_to_strip(gx, gy):
    """Convert game (gx, gy) to physical strip (x, y)."""
    if gx < 16:
        return gx, gy
    else:
        return gx - 16, gy + 64


# ── Directions ────────────────────────────────────────────────────────────────

UP    = (0, -1)
DOWN  = (0, 1)
LEFT  = (-1, 0)
RIGHT = (1, 0)

DIR_MAP = {
    'up':    UP,
    'down':  DOWN,
    'left':  LEFT,
    'right': RIGHT,
}

OPPOSITES = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}


# ── Game logic ────────────────────────────────────────────────────────────────

class SnakeGame:
    def __init__(self):
        cx, cy = GAME_W // 2, GAME_H // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = RIGHT
        self.food = None
        self.alive = True
        self.score = 0
        self._place_food()

    def _place_food(self):
        occupied = set(self.snake)
        free = [(x, y) for x in range(GAME_W) for y in range(GAME_H)
                if (x, y) not in occupied]
        if free:
            self.food = random.choice(free)
        else:
            self.food = None  # you won!

    def set_direction(self, d):
        # Prevent 180° reversal
        if OPPOSITES.get(d) != self.direction:
            self.direction = d

    def tick(self):
        if not self.alive:
            return

        hx, hy = self.snake[0]
        dx, dy = self.direction
        nx, ny = hx + dx, hy + dy

        # Wall collision
        if nx < 0 or nx >= GAME_W or ny < 0 or ny >= GAME_H:
            self.alive = False
            return

        # Self collision
        if (nx, ny) in set(self.snake):
            self.alive = False
            return

        self.snake.insert(0, (nx, ny))

        if (nx, ny) == self.food:
            self.score += 1
            self._place_food()
        else:
            self.snake.pop()


# ── Rendering ─────────────────────────────────────────────────────────────────

def render(display, game):
    display.clear()

    # Draw snake body
    for i, (gx, gy) in enumerate(game.snake):
        sx, sy = game_to_strip(gx, gy)
        color = HEAD_COLOR if i == 0 else SNAKE_COLOR
        display.set_pixel_xy(sx, sy, color)

    # Draw food
    if game.food:
        fx, fy = game_to_strip(*game.food)
        display.set_pixel_xy(fx, fy, FOOD_COLOR)

    display.show()


def render_death(display, game):
    """Flash the snake red on death."""
    for flash in range(4):
        color = RED if flash % 2 == 0 else OFF
        for gx, gy in game.snake:
            sx, sy = game_to_strip(gx, gy)
            display.set_pixel_xy(sx, sy, color)
        display.show()
        time.sleep(0.2)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _emit(obj):
    print(json.dumps(obj), flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with CMDisplay() as display:
        game = SnakeGame()
        render(display, game)

        last_tick = time.time()

        try:
            while game.alive:
                # Check for direction input (non-blocking)
                now = time.time()
                wait = max(0, TICK_INTERVAL - (now - last_tick))

                if select.select([sys.stdin], [], [], wait)[0]:
                    line = sys.stdin.readline()
                    if not line:
                        break  # stdin closed
                    try:
                        data = json.loads(line)
                        if data.get('type') == 'direction':
                            d = DIR_MAP.get(data.get('value'))
                            if d:
                                game.set_direction(d)
                    except (json.JSONDecodeError, ValueError):
                        pass

                # Time to advance?
                if time.time() - last_tick >= TICK_INTERVAL:
                    prev_score = game.score
                    game.tick()
                    if game.score != prev_score:
                        _emit({"type": "score", "value": game.score})
                    render(display, game)
                    last_tick = time.time()

            # Death animation
            if not game.alive:
                render_death(display, game)

        except KeyboardInterrupt:
            pass

        _emit({"type": "finished", "program": "snake"})


if __name__ == "__main__":
    main()
