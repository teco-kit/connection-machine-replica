#!/usr/bin/env python3
"""
Program mode for the Connection Machine replica.

Launched by server.js when the user selects a program (C* or Python).
Preloads all .cstar programs at startup, then accepts JSON commands on
stdin to run/switch programs.

For C* programs: runs them on the CM2 emulator and maps output to LEDs.
For Python programs: imports and calls their main() directly.

stdin protocol  (JSON per line):
    {"type": "run", "program": "mandelbrot"}
    {"type": "run", "program": "rainbow"}

stdout protocol (JSON per line):
    {"type": "programs", "list": ["mandelbrot", "wave_front", ...]}
    {"type": "started", "program": "mandelbrot"}
    {"type": "finished", "program": "mandelbrot"}
"""

import glob
import importlib.util
import json
import os
import select
import sys
import threading
import time

# ── Path setup ────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, '..', 'lib')
_PROGRAMS = os.path.join(_HERE, '..', 'programs')
_CSTAR = os.path.join(_PROGRAMS, 'cstar')

sys.path.insert(0, _LIB)

from cm_display import CMDisplay, RED, OFF
from cm2_emulator import CM2Machine, CM2Config, parse_cstar
from cm2_emulator.cstar import CStarRuntime


# ── Configuration ─────────────────────────────────────────────────────────────

EXCLUDED_CSTAR = {'random_blink'}  # Covered by idle mode


# ── Preloader ─────────────────────────────────────────────────────────────────

def preload_cstar_programs():
    """Parse every .cstar file in programs/cstar/ (minus exclusions)."""
    programs = {}
    for filepath in sorted(glob.glob(os.path.join(_CSTAR, '*.cstar'))):
        name = os.path.splitext(os.path.basename(filepath))[0]
        if name in EXCLUDED_CSTAR:
            continue
        try:
            programs[name] = parse_cstar(filepath)
        except Exception as e:
            print(f"Warning: failed to parse {filepath}: {e}", file=sys.stderr)
    return programs


def discover_python_programs():
    """Find runnable Python scripts in programs/ (excluding __init__.py)."""
    programs = []
    if not os.path.isdir(_PROGRAMS):
        return programs
    for f in sorted(os.listdir(_PROGRAMS)):
        if f.endswith('.py') and f != '__init__.py':
            programs.append(f.replace('.py', ''))
    return programs


# ── Matrix → LED mapping ─────────────────────────────────────────────────────

def matrix_to_leds(display, front_matrix):
    """Map the emulator's 64×32 front matrix to physical LED positions.

    The emulator matrix is 64 rows × 32 cols (panel_grid_rows*panel_rows × panel_grid_cols*panel_cols).
    The physical strip is 16 wide × 128 tall with chain order TL → BL → TR → BR:

        Left half  (col  0-15):  x = col,      y = row          (panels TL+BL,  strip y 0-63)
        Right half (col 16-31):  x = col - 16,  y = row + 64    (panels TR+BR,  strip y 64-127)
    """
    display.clear()
    rows = len(front_matrix)
    cols = len(front_matrix[0]) if rows else 0

    for row in range(rows):
        for col in range(cols):
            if front_matrix[row][col]:
                if col < 16:
                    x, y = col, row
                else:
                    x, y = col - 16, row + 64
                display.set_pixel_xy(x, y, RED)


# ── C* program runner (interruptible) ────────────────────────────────────────

class _StopExecution(Exception):
    """Raised inside on_led to abort a running program."""


class ProgramRunner:
    """Runs C* or Python programs on a background thread, interruptible via stop()."""

    def __init__(self, display, config, machine):
        self.display = display
        self.config = config
        self.machine = machine
        self._stop = threading.Event()
        self._thread = None
        self._current_name = None

    def run_cstar(self, name, program):
        """Start a C* program. Stops any program already running."""
        self.stop()
        self._stop.clear()
        self._current_name = name
        self._thread = threading.Thread(
            target=self._execute_cstar, args=(name, program), daemon=True
        )
        self._thread.start()

    def run_python(self, name):
        """Start a Python program. Stops any program already running."""
        self.stop()
        self._stop.clear()
        self._current_name = name
        self._thread = threading.Thread(
            target=self._execute_python, args=(name,), daemon=True
        )
        self._thread.start()

    def stop(self):
        """Signal the running program to abort and wait for it."""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        self._current_name = None

    def _execute_cstar(self, name, program):
        runtime = CStarRuntime(
            processor_count=self.machine.processor_count,
            processors_per_chip=self.config.processors_per_chip,
            chip_cols=self.config.matrix_cols,
            chip_rows=self.config.matrix_rows,
        )

        def on_led(processor_mask, delay_ms):
            if self._stop.is_set():
                raise _StopExecution()
            if processor_mask is not None:
                matrices = self.machine.processor_mask_to_led_matrices(processor_mask)
                matrix_to_leds(self.display, matrices["front"])
                self.display.show()
            else:
                # Interruptible sleep (check stop flag every 50 ms)
                end = time.time() + delay_ms / 1000.0
                while time.time() < end:
                    if self._stop.is_set():
                        raise _StopExecution()
                    time.sleep(min(0.05, max(0, end - time.time())))

        try:
            runtime.execute(program, on_led)
            _emit({"type": "finished", "program": name})
        except _StopExecution:
            pass

    def _execute_python(self, name):
        script_path = os.path.join(_PROGRAMS, name + '.py')
        if not os.path.isfile(script_path):
            print(f"Unknown Python program: {name}", file=sys.stderr)
            return

        try:
            spec = importlib.util.spec_from_file_location(name, script_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, 'main'):
                mod.main()
            _emit({"type": "finished", "program": name})
        except _StopExecution:
            pass
        except Exception as e:
            print(f"Error running {name}: {e}", file=sys.stderr)
            _emit({"type": "finished", "program": name})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _emit(obj):
    """Write a JSON line to stdout (for server.js to read)."""
    print(json.dumps(obj), flush=True)


# ── Main loop ────────────────────────────────────────────────────────────────

def main():
    # Preload all C* programs
    cstar_programs = preload_cstar_programs()
    python_programs = discover_python_programs()

    all_names = sorted(cstar_programs.keys()) + sorted(python_programs)
    _emit({"type": "programs", "list": all_names})

    # Set up hardware & emulator
    config = CM2Config(cubes=4)
    machine = CM2Machine(config)
    display = CMDisplay()
    display.begin()

    runner = ProgramRunner(display, config, machine)

    try:
        while True:
            if not select.select([sys.stdin], [], [], 0.1)[0]:
                continue

            line = sys.stdin.readline()
            if not line:
                break  # stdin closed → server killed us

            try:
                data = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            if data.get("type") == "run":
                name = data.get("program", "")
                if name in cstar_programs:
                    runner.run_cstar(name, cstar_programs[name])
                    _emit({"type": "started", "program": name})
                elif name in python_programs:
                    runner.run_python(name)
                    _emit({"type": "started", "program": name})
                else:
                    print(f"Unknown program: {name}", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop()
        display.cleanup()


if __name__ == "__main__":
    main()
