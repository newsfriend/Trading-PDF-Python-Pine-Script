"""Non-authoritative structural preview used for chart comparison.

The V4 full-cycle engine is the binding implementation. This module mirrors
Pine's explicitly labelled ``Structural Preview (Not V4 Confirmed)`` mode and
must not be presented as a notes-compliant Elliott confirmation engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StructuralPivot:
    bar: int
    price: float
    kind: int  # +1 high, -1 low
    atr: float = 0.0
    important_range: float = 0.0


@dataclass
class ClientSwingStructure:
    wave_atr_multiple: float = 1.0
    wave_range_fraction: float = 0.01
    wave2_min_retrace: float = 0.10
    wave3_min_multiple: float = 0.618
    correction_c_min_multiple: float = 0.618
    max_cycles: int = 3
    nodes: list[StructuralPivot] = field(default_factory=list)
    cycles: list[tuple[StructuralPivot, ...]] = field(default_factory=list)
    bullish: bool = False
    reason: str = "SEARCHING_FOR_STRUCTURAL_POINT_0"

    @property
    def stage(self) -> int:
        return len(self.nodes)

    def _reset(self, pivot: StructuralPivot) -> None:
        self.nodes = [pivot]

    def _minimum_move(self, pivot: StructuralPivot) -> float:
        return max(
            pivot.atr * self.wave_atr_multiple,
            pivot.important_range * self.wave_range_fraction,
        )

    def add(self, pivot: StructuralPivot) -> bool:
        """Consume one alternating confirmed pivot; return True on full cycle."""
        if not self.nodes:
            self._reset(pivot)
            self.reason = "POINT_0_CANDIDATE"
            return False

        p0 = self.nodes[0]
        minimum = self._minimum_move(pivot)
        stage = self.stage

        if stage == 1:
            if pivot.kind == p0.kind:
                more_extreme = pivot.price > p0.price if pivot.kind == 1 else pivot.price < p0.price
                if more_extreme:
                    self.nodes[0] = pivot
                    self.reason = "POINT_0_IMPROVED"
            elif abs(pivot.price - p0.price) >= minimum:
                self.nodes.append(pivot)
                self.bullish = pivot.price > p0.price
                self.reason = "W1_CONFIRMED_STRUCTURAL"
            else:
                self._reset(pivot)
                self.reason = "W1_TOO_SMALL_REBASE"
            return False

        p1 = self.nodes[1]
        if stage == 2:
            if pivot.kind == p0.kind:
                crossed = pivot.price <= p0.price if self.bullish else pivot.price >= p0.price
                retrace = abs(p1.price - pivot.price) / abs(p1.price - p0.price)
                if crossed:
                    self._reset(pivot)
                    self.reason = "W2_ORIGIN_BREAK_RECOUNT"
                elif self.wave2_min_retrace <= retrace < 1.0:
                    self.nodes.append(pivot)
                    self.reason = "W2_CONFIRMED_STRUCTURAL"
                else:
                    self.reason = "W2_RETRACE_PENDING"
            return False

        p2 = self.nodes[2]
        if stage == 3:
            if pivot.kind == p1.kind:
                exceeds = pivot.price > p1.price if self.bullish else pivot.price < p1.price
                w3 = abs(pivot.price - p2.price)
                if exceeds and w3 >= self.wave3_min_multiple * abs(p1.price - p0.price):
                    self.nodes.append(pivot)
                    self.reason = "W3_CONFIRMED_STRUCTURAL"
                else:
                    self.reason = "W3_EXTENSION_PENDING"
            elif pivot.kind == p0.kind:
                protected = pivot.price > p0.price if self.bullish else pivot.price < p0.price
                improves = pivot.price < p2.price if self.bullish else pivot.price > p2.price
                if not protected:
                    self._reset(pivot)
                    self.bullish = False
                    self.reason = "W2_ORIGIN_BREAK_RECOUNT"
                elif improves:
                    self.nodes[2] = pivot
                    self.reason = "W2_TERMINAL_IMPROVED"
            return False

        p3 = self.nodes[3]
        if stage == 4:
            if pivot.kind == p0.kind:
                origin_ok = pivot.price > p0.price if self.bullish else pivot.price < p0.price
                normal = pivot.price > p1.price if self.bullish else pivot.price < p1.price
                diagonal = pivot.price > p2.price if self.bullish else pivot.price < p2.price
                retrace = abs(p3.price - pivot.price) / abs(p3.price - p0.price)
                if not origin_ok:
                    self._reset(pivot)
                    self.reason = "W4_ORIGIN_BREAK_RECOUNT"
                elif (normal or diagonal) and 0.10 <= retrace <= 0.70:
                    self.nodes.append(pivot)
                    self.reason = "W4_CONFIRMED_STRUCTURAL" if normal else "W4_DIAGONAL_OVERLAP"
                else:
                    self.reason = "W4_CORRECTION_PENDING"
            return False

        p4 = self.nodes[4]
        if stage == 5:
            if pivot.kind == p1.kind:
                normal = pivot.price > p3.price if self.bullish else pivot.price < p3.price
                with_trend = pivot.price > p4.price if self.bullish else pivot.price < p4.price
                truncated = with_trend and abs(pivot.price - p4.price) >= 0.382 * abs(p1.price - p0.price)
                if normal or truncated:
                    self.nodes.append(pivot)
                    self.reason = "W5_CONFIRMED_STRUCTURAL" if normal else "W5_TRUNCATED_STRUCTURAL"
                else:
                    self.reason = "W5_TERMINAL_PENDING"
            return False

        p5 = self.nodes[5]
        if stage == 6:
            if pivot.kind == p0.kind and abs(p5.price - pivot.price) >= 0.5 * minimum:
                self.nodes.append(pivot)
                self.reason = "A_CONFIRMED_STRUCTURAL"
            else:
                self.reason = "A_LEG_PENDING"
            return False

        p_a = self.nodes[6]
        if stage == 7:
            if pivot.kind == p1.kind:
                b_retrace = abs(pivot.price - p_a.price) / abs(p5.price - p_a.price)
                if 0.10 <= b_retrace <= 1.618:
                    self.nodes.append(pivot)
                    self.reason = "B_CONFIRMED_STRUCTURAL"
                else:
                    self.reason = "B_PATTERN_PENDING"
            return False

        p_b = self.nodes[7]
        if pivot.kind == p0.kind:
            c_multiple = abs(p_b.price - pivot.price) / abs(p5.price - p_a.price)
            beyond_a = pivot.price < p_a.price if self.bullish else pivot.price > p_a.price
            if beyond_a or c_multiple >= self.correction_c_min_multiple:
                self.nodes.append(pivot)
                cycle = tuple(self.nodes)
                self.cycles.append(cycle)
                self.cycles = self.cycles[-self.max_cycles :]
                self._reset(pivot)
                self.bullish = False
                self.reason = "IMPULSE_AND_ABC_CONFIRMED"
                return True
            self.reason = "C_TERMINAL_PENDING"
        return False


LABELS = ("0", "1", "2", "3", "4", "5", "A", "B", "C")
