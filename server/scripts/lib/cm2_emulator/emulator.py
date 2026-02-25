from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class CM2Config:
    cubes: int = 4
    processors_per_chip: int = 16
    panel_cols: int = 16
    panel_rows: int = 32
    panel_grid_cols: int = 2
    panel_grid_rows: int = 2

    def __post_init__(self) -> None:
        if self.cubes not in (4, 8):
            raise ValueError("Only 4-cube and 8-cube configurations are supported.")

    @property
    def leds_per_panel(self) -> int:
        return self.panel_cols * self.panel_rows

    @property
    def panels_per_side(self) -> int:
        return self.panel_grid_cols * self.panel_grid_rows

    @property
    def leds_per_side(self) -> int:
        return self.leds_per_panel * self.panels_per_side

    @property
    def sides(self) -> List[str]:
        return ["front"] if self.cubes == 4 else ["front", "back"]

    @property
    def chips_total(self) -> int:
        return self.leds_per_side * len(self.sides)

    @property
    def processors_total(self) -> int:
        return self.chips_total * self.processors_per_chip

    @property
    def matrix_cols(self) -> int:
        return self.panel_cols * self.panel_grid_cols

    @property
    def matrix_rows(self) -> int:
        return self.panel_rows * self.panel_grid_rows


class CM2Machine:
    def __init__(self, config: CM2Config):
        self.config = config
        self.processor_count = config.processors_total

    def processor_mask_to_led_matrices(self, processor_mask: List[bool]) -> Dict[str, List[List[bool]]]:
        if len(processor_mask) != self.processor_count:
            raise ValueError(
                f"processor_mask has length {len(processor_mask)}, expected {self.processor_count}."
            )

        chips = self._processors_to_chip_activity(processor_mask)
        side_count = len(self.config.sides)
        chips_per_side = self.config.leds_per_side

        matrices: Dict[str, List[List[bool]]] = {}
        for side_idx, side in enumerate(self.config.sides):
            start = side_idx * chips_per_side
            end = start + chips_per_side
            side_chips = chips[start:end]
            matrices[side] = self._chips_to_matrix(side_chips)
        if side_count == 1:
            matrices["back"] = self._blank_matrix()
        return matrices

    def _processors_to_chip_activity(self, processor_mask: List[bool]) -> List[bool]:
        ppc = self.config.processors_per_chip
        chips = [False] * self.config.chips_total
        for chip_idx in range(self.config.chips_total):
            base = chip_idx * ppc
            active = False
            for i in range(ppc):
                if processor_mask[base + i]:
                    active = True
                    break
            chips[chip_idx] = active
        return chips

    def _chips_to_matrix(self, side_chips: List[bool]) -> List[List[bool]]:
        rows = self.config.matrix_rows
        cols = self.config.matrix_cols
        matrix = [[False for _ in range(cols)] for _ in range(rows)]

        for chip_idx, on in enumerate(side_chips):
            panel_idx = chip_idx // self.config.leds_per_panel
            local_idx = chip_idx % self.config.leds_per_panel

            panel_row = panel_idx // self.config.panel_grid_cols
            panel_col = panel_idx % self.config.panel_grid_cols

            local_row = local_idx // self.config.panel_cols
            local_col = local_idx % self.config.panel_cols

            row = panel_row * self.config.panel_rows + local_row
            col = panel_col * self.config.panel_cols + local_col
            matrix[row][col] = on
        return matrix

    def _blank_matrix(self) -> List[List[bool]]:
        return [[False for _ in range(self.config.matrix_cols)] for _ in range(self.config.matrix_rows)]
