"""Episode-level metric aggregation with explicit, documented semantics.

`SwarmFormationEnv.compute_metrics()` is evaluated on the *current* state and
carries no history, so every value it returns is a terminal-state quantity unless
the evaluator aggregates it. This module performs that aggregation.

Semantics codes used in the docstrings below follow
`docs/EPISODE_METRIC_SPECIFICATION.md`:

    A terminal   B conjunction   C event latch   D count
    E min/max    F time average  G % of time     H first-passage time
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Bump when episode-metric semantics change. Results carrying different versions
# must never be aggregated together.
#   1 = pre-correction (terminal-step safety, no latches, no clearance tracking)
#   2 = this specification
EVALUATION_SCHEMA_VERSION = 2


@dataclass
class EpisodeAccumulator:
    """Accumulates per-step `info` dicts into episode-level metrics."""

    formation_tolerance: float
    dt: float = 1.0

    steps: int = 0
    # C — event latches
    _goal_reached: bool = False
    _deadlock: bool = False
    _collapse: bool = False
    # B — conjunction
    _collision_free: bool = True
    # D — counts
    _rr_collision_steps: int = 0
    _ro_collision_steps: int = 0
    _shield_activations: int = 0
    _form_ok_steps: int = 0
    _no_progress_steps: int = 0
    # E — extrema
    _min_rr_clearance: float = math.inf
    _min_ro_clearance: float = math.inf
    _form_rms_max: float = 0.0
    _rr_collision_max: float = 0.0
    _ro_collision_max: float = 0.0
    # F — running sums for time averages
    _form_rms_sum: float = 0.0
    # H — first passage
    _first_goal_step: Optional[int] = None

    _prev_goal_distance: Optional[float] = None
    _per_step_collision_free: List[float] = field(default_factory=list)

    def update(self, info: Dict[str, float], shield_activated: bool = False) -> None:
        """Fold one simulator step into the accumulator."""
        self.steps += 1
        step_index = self.steps

        # ---- C: event latches -------------------------------------------------
        if float(info.get("goal_reached", 0.0)) > 0.5:
            self._goal_reached = True
            if self._first_goal_step is None:
                self._first_goal_step = step_index
        if float(info.get("deadlock", 0.0)) > 0.5:
            self._deadlock = True
        if float(info.get("irreversible_collapse", 0.0)) > 0.5:
            self._collapse = True

        # ---- B: safety conjunction -------------------------------------------
        collision_free = float(info.get("collision_free", 1.0))
        self._per_step_collision_free.append(collision_free)
        if collision_free <= 0.5:
            self._collision_free = False

        # ---- D: counts --------------------------------------------------------
        rr = float(info.get("rr_collision", 0.0))
        ro = float(info.get("ro_collision", 0.0))
        if rr > 0.0:
            self._rr_collision_steps += 1
        if ro > 0.0:
            self._ro_collision_steps += 1
        if float(info.get("form_ok", 0.0)) > 0.5:
            self._form_ok_steps += 1
        if shield_activated:
            self._shield_activations += 1

        # ---- E: extrema -------------------------------------------------------
        self._rr_collision_max = max(self._rr_collision_max, rr)
        self._ro_collision_max = max(self._ro_collision_max, ro)
        form_rms = float(info.get("form_rms", 0.0))
        self._form_rms_max = max(self._form_rms_max, form_rms)
        if "min_rr_clearance" in info:
            self._min_rr_clearance = min(self._min_rr_clearance, float(info["min_rr_clearance"]))
        if "min_ro_clearance" in info:
            self._min_ro_clearance = min(self._min_ro_clearance, float(info["min_ro_clearance"]))

        # ---- F: running sums --------------------------------------------------
        self._form_rms_sum += form_rms

        # no-progress indicator, derived from the reported goal_distance sequence
        goal_distance = info.get("goal_distance")
        if goal_distance is not None:
            goal_distance = float(goal_distance)
            if self._prev_goal_distance is not None and goal_distance >= self._prev_goal_distance:
                self._no_progress_steps += 1
            self._prev_goal_distance = goal_distance

    def finalize(self, last_info: Dict[str, float]) -> Dict[str, float]:
        """Return the terminal dict augmented with episode-level metrics.

        Every redefined key keeps its previous (terminal) value under a
        `*_terminal` alias so both conventions stay reportable.
        """
        out = dict(last_info)
        n = max(self.steps, 1)

        # Preserve the pre-correction terminal values.
        out["goal_reached_terminal"] = float(last_info.get("goal_reached", 0.0))
        out["deadlock_terminal"] = float(last_info.get("deadlock", 0.0))
        out["irreversible_collapse_terminal"] = float(last_info.get("irreversible_collapse", 0.0))
        out["stall_rate_terminal"] = float(last_info.get("stall_rate", 0.0))
        out["collision_free_terminal"] = float(last_info.get("collision_free", 1.0))
        out["success_terminal"] = float(last_info.get("success", 0.0))
        out["form_ok_terminal"] = float(last_info.get("form_ok", 0.0))

        # C — latches
        out["goal_reached"] = float(self._goal_reached)
        out["deadlock"] = float(self._deadlock)
        out["irreversible_collapse"] = float(self._collapse)

        # B — conjunction
        out["collision_free"] = float(self._collision_free)

        # D — counts
        out["robot_robot_collision_steps"] = float(self._rr_collision_steps)
        out["robot_obstacle_collision_steps"] = float(self._ro_collision_steps)
        out["safety_filter_activations"] = float(self._shield_activations)

        # E — extrema
        out["min_rr_clearance"] = (
            float(self._min_rr_clearance) if math.isfinite(self._min_rr_clearance) else float("nan")
        )
        out["min_ro_clearance"] = (
            float(self._min_ro_clearance) if math.isfinite(self._min_ro_clearance) else float("nan")
        )
        out["rr_collision_max"] = float(self._rr_collision_max)
        out["ro_collision_max"] = float(self._ro_collision_max)
        out["form_rms_max"] = float(self._form_rms_max)

        # F / G — time averages
        out["form_rms_mean"] = float(self._form_rms_sum / n)
        out["time_in_formation_tube"] = float(self._form_ok_steps / n)
        out["stall_rate"] = float(self._no_progress_steps / n)
        out["safety_filter_activation_rate"] = float(self._shield_activations / n)

        # H — first-passage time (censored when the goal is never reached)
        out["first_goal_step"] = (
            float(self._first_goal_step) if self._first_goal_step is not None else float("nan")
        )
        out["completion_time"] = (
            float(self._first_goal_step) * float(self.dt)
            if self._first_goal_step is not None
            else float("nan")
        )
        out["completion_time_censored"] = float(self._first_goal_step is None)

        # B — success: latched goal AND episode-wide collision-free AND terminal
        # form_ok. The formation term is deliberately left as the terminal flag;
        # see docs/EPISODE_METRIC_SPECIFICATION.md.
        out["success"] = float(
            self._goal_reached
            and self._collision_free
            and float(last_info.get("form_ok", 0.0)) > 0.5
        )

        out["steps"] = float(self.steps)
        out["evaluation_schema_version"] = float(EVALUATION_SCHEMA_VERSION)
        return out


def per_step_conjunction(per_step_values: List[float]) -> float:
    """Reference implementation of semantics B, for use in tests."""
    return float(all(float(v) > 0.5 for v in per_step_values))
