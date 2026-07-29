"""Explicit, split-disjoint scenario layouts with geometry hashes.

Every layout is a named, hashable geometry. Splits draw from **disjoint discrete
parameter sets**, so no train/validation/test layout can share geometry — this is
guaranteed by construction and asserted by
`tests/test_layout_split_disjointness.py`.

Physical reasoning behind the corridor widths (world 12x12 m):

    robot radius r          = 0.18 m
    obstacle radius R       = 0.35 m
    robot-obstacle bound    = 0.55 m   (min_ro_distance)
    robot-robot bound       = 0.40 m   (min_rr_distance)
    nominal spacing d0      = 0.90 m

For a gate of two opposing obstacle rows whose innermost centres sit at y = +-W/2,
a robot centre is admissible only where |y| <= W/2 - 0.55. Hence:

    single file (line)      needs  W >= 1.10 m
    compact grid (keep)     needs  W >= 2 * (0.9 + 0.55) = 2.90 m   (3-column grid)
    two lanes (split)       needs  W >= 2 * (0.65 + 0.55) = 2.40 m   (lane_gap 1.3)

so a gate with W in [1.4, 2.2] admits `line` and excludes both `keep` and `split`;
a central blocker with side channels admits `split` and excludes `line` (the file
would run through the blocker) and `keep` (its centre column is blocked).

These are hypotheses about which mode *can* pass, not labels. Empirical
oracle-best modes come from rollout outcomes only (Task 5).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

FAMILIES = (
    "keep_open",        # A
    "line_corridor",    # B
    "split_around",     # C
    "keep_line_keep",   # D
    "keep_split_merge", # E
    "ambiguous",        # F
    "infeasible",       # G
)

SPLITS = ("train", "val", "test")

# --- Disjoint discrete parameter sets, one per split -------------------------
# Gate width W (m) for line-favourable gates. Ranges overlap in *purpose* but the
# values are pairwise disjoint, so geometry can never coincide across splits.
GATE_WIDTH = {"train": (1.40, 1.70, 2.00), "val": (1.50, 1.80, 2.10), "test": (1.60, 1.90, 2.20)}
# Outer wall half-separation for split-favourable layouts.
OUTER_HALF = {"train": (1.55, 1.75), "val": (1.60, 1.80), "test": (1.65, 1.85)}
# Gate x-position (m). Disjoint across splits.
GATE_X = {"train": (-0.30, 0.30), "val": (-0.20, 0.20), "test": (-0.10, 0.10)}
# Sparse-obstacle lateral offsets for open layouts.
OPEN_OFFSET = {"train": (2.30, 3.10), "val": (2.45, 3.25), "test": (2.60, 3.40)}
# Wall-tile spacing along y.
TILE_DY = 0.70
WALL_EXTENT = 3.6


@dataclass(frozen=True)
class Layout:
    layout_id: str
    family: str
    split: str
    obstacles: Tuple[Tuple[float, float], ...]
    goal: Tuple[float, float]
    start_center: Tuple[float, float]
    params: Dict[str, float] = field(default_factory=dict)

    @property
    def obstacle_array(self) -> np.ndarray:
        return np.array(self.obstacles, dtype=np.float32).reshape(-1, 2)

    def geometry_hash(self) -> str:
        """Hash of the geometry alone -- identical geometry gives an identical hash."""
        h = hashlib.sha256()
        arr = np.round(self.obstacle_array.astype(np.float64), 6)
        order = np.lexsort((arr[:, 1], arr[:, 0])) if len(arr) else np.array([], dtype=int)
        h.update(arr[order].tobytes())
        h.update(np.round(np.array(self.goal, dtype=np.float64), 6).tobytes())
        h.update(np.round(np.array(self.start_center, dtype=np.float64), 6).tobytes())
        return h.hexdigest()[:24]


def _wall_column(x: float, half_gap: float, extent: float = WALL_EXTENT) -> List[Tuple[float, float]]:
    """Two vertical obstacle rows forming a gate of full width 2*half_gap at x."""
    tiles: List[Tuple[float, float]] = []
    y = half_gap
    while y <= extent:
        tiles.append((x, round(y, 4)))
        tiles.append((x, round(-y, 4)))
        y += TILE_DY
    return tiles


def _blocker(x: float, half_height: float = 0.0) -> List[Tuple[float, float]]:
    """Central blocker on the corridor axis."""
    if half_height <= 0.0:
        return [(x, 0.0)]
    tiles = [(x, 0.0)]
    y = TILE_DY
    while y <= half_height:
        tiles.append((x, round(y, 4)))
        tiles.append((x, round(-y, 4)))
        y += TILE_DY
    return tiles


def build_layouts(split: str) -> List[Layout]:
    """All layouts for one split. Deterministic; no RNG."""
    assert split in SPLITS
    gw, oh, gx, oo = GATE_WIDTH[split], OUTER_HALF[split], GATE_X[split], OPEN_OFFSET[split]
    goal = (4.56, 0.0)
    start = (-4.56, 0.0)
    out: List[Layout] = []

    def add(family, idx, obstacles, params, goal_=goal, start_=start):
        out.append(Layout(f"{split}_{family}_{idx:03d}", family, split,
                          tuple(obstacles), goal_, start_, params))

    # A. keep_open -- sparse obstacles well off the corridor axis.
    for i, off in enumerate(oo):
        obs = [(-1.5, off), (1.5, -off), (0.0, off + 1.2), (0.0, -off - 1.2)]
        add("keep_open", i + 1, obs, {"lateral_offset": off})

    # B. line_corridor -- one gate, width admits single file only.
    for i, w in enumerate(gw):
        add("line_corridor", i + 1, _wall_column(gx[0], w / 2.0), {"gate_width": w, "gate_x": gx[0]})

    # C. split_around -- central blocker plus outer walls; centre column blocked.
    for i, half in enumerate(oh):
        obs = _blocker(gx[1]) + _wall_column(gx[1], half)
        add("split_around", i + 1, obs, {"outer_half": half, "gate_x": gx[1]})

    # D. keep_line_keep -- open, then a finite corridor, then open.
    for i, w in enumerate(gw[:2]):
        obs = _wall_column(gx[0] - 0.5, w / 2.0) + _wall_column(gx[0] + 0.5, w / 2.0)
        add("keep_line_keep", i + 1, obs, {"gate_width": w, "corridor_len": 1.0})

    # E. keep_split_merge -- open, blocker with two channels, open, shared goal.
    for i, half in enumerate(oh):
        obs = (_blocker(gx[1] - 0.5) + _blocker(gx[1] + 0.5)
               + _wall_column(gx[1] - 0.5, half) + _wall_column(gx[1] + 0.5, half))
        add("keep_split_merge", i + 1, obs, {"outer_half": half, "blocker_len": 1.0})

    # F. ambiguous -- gate wide enough for every mode.
    for i, w in enumerate((gw[-1] + 1.4, gw[-1] + 1.8)):
        add("ambiguous", i + 1, _wall_column(gx[0], w / 2.0), {"gate_width": round(w, 3)})

    # G. infeasible -- gate narrower than one robot can pass (needs W >= 1.10).
    for i, w in enumerate((0.80, 0.95)):
        add("infeasible", i + 1, _wall_column(gx[1], w / 2.0), {"gate_width": w})

    return out


def all_layouts() -> Dict[str, List[Layout]]:
    return {s: build_layouts(s) for s in SPLITS}


def layouts_by_family(split: str) -> Dict[str, List[Layout]]:
    grouped: Dict[str, List[Layout]] = {}
    for lay in build_layouts(split):
        grouped.setdefault(lay.family, []).append(lay)
    return grouped


def get_layout(layout_id: str) -> Layout:
    for split in SPLITS:
        for lay in build_layouts(split):
            if lay.layout_id == layout_id:
                return lay
    raise KeyError(layout_id)


# --- Feasibility hypotheses (NOT labels) -------------------------------------
def mode_feasibility_hypothesis(layout: Layout) -> Dict[str, bool]:
    """Geometric admissibility, computed from clearances -- a hypothesis only.

    Empirical oracle-best modes come from rollout outcomes, never from this.
    """
    p = layout.params
    w = p.get("gate_width")
    half = p.get("outer_half")
    if w is not None:
        chan = w / 2.0 - 0.55          # admissible |y| for a robot centre
        return {"keep": chan >= 0.90, "line": chan >= 0.0, "split": chan >= 0.65}
    if half is not None:
        band_ok = (half - 0.55) >= 0.65   # outer wall leaves room for a lane
        return {"keep": False, "line": False, "split": band_ok}
    return {"keep": True, "line": True, "split": True}
