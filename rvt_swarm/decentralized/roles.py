"""Persistent formation roles and pairwise formation geometry.

Replaces the centralized runtime slot assignment in `controllers._desired_offsets`,
which computed the line template with `np.argsort(pos @ corridor)` -- a sort over
the *joint state* executed at every control step. That is a central runtime
assignment service and is prohibited.

Here each robot carries a persistent ID and a role coordinate for each mode,
fixed at mission-configuration time and never recomputed at runtime. Desired
geometry is expressed purely pairwise:

    d_ij^tau = R(psi_mission) [ r_j^tau - r_i^tau ]

which robot i computes from its own role, the neighbour's communicated role,
and the shared mission direction. Because it is a difference of role
coordinates, any common translation of the template cancels -- so no robot ever
needs the swarm centroid, and antisymmetry d_ij = -d_ji is exact by
construction rather than by convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from ..topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    construct_topology_from_spacing,
    local_pairwise_offset,
    rotate_template_vector,
)
from .system_model import (
    MODES, CentralizedAccessError, NeighbourRecord, RobotView,
)

Vec2 = Tuple[float, float]


def rotation(mission_dir: Vec2) -> np.ndarray:
    """R(psi_mission) mapping template frame -> world frame.

    The template's +x axis maps onto the shared mission direction. Every robot
    loads the same mission direction, so every robot computes the same R; no
    communication and no global state is involved.
    """
    ex = rotate_template_vector((1.0, 0.0), mission_dir)
    c, s = ex
    return np.array([[c, -s], [s, c]], dtype=np.float32)


@dataclass(frozen=True)
class RoleAssignment:
    """Persistent per-robot role coordinates in the template frame.

    `keep[i]` and `line[i]` are robot i's template-frame coordinates. They are
    mission constants: computed once, before t = 0, and burned into each robot
    alongside its persistent ID. Nothing recomputes them during the control
    loop -- `test_pairwise_formation_geometry.py` asserts this.
    """

    keep: np.ndarray            # (N, 2) template-frame coordinates
    line: np.ndarray            # (N, 2)
    spacing: float
    source: str                 # "index" | "initial_formation"
    compact: Optional[np.ndarray] = None

    def __post_init__(self) -> None:
        if self.keep.shape != self.line.shape or self.keep.ndim != 2:
            raise ValueError("role tables must both be (N, 2)")
        if self.compact is not None and self.compact.shape != self.keep.shape:
            raise ValueError("compact role table must match KEEP/LINE shape")

    @property
    def n(self) -> int:
        return int(self.keep.shape[0])

    def coords(self, mode: int) -> np.ndarray:
        if mode == KEEP:
            return self.keep
        if mode == COMPACT and self.compact is not None:
            return self.compact
        if mode == LINE:
            return self.line
        raise ValueError(
            f"mode {mode} is unavailable in this role assignment; "
            f"selected runtime modes are {MODES}"
        )

    def role_of(self, robot_id: int, mode: int) -> Vec2:
        c = self.coords(mode)[robot_id]
        return (float(c[0]), float(c[1]))

    # -- construction -------------------------------------------------------
    @staticmethod
    def _keep_template(n: int, spacing: float) -> np.ndarray:
        """Grid template, identical to the existing centralized keep layout.

        The existing keep template is already index-based -- cell = divmod(i,
        cols) -- so it needs no runtime joint-state access and is reproduced
        exactly. Template frame: +x along the mission direction (rows), +y
        lateral (columns).
        """
        template = construct_topology_from_spacing(KEEP, n, spacing)
        return np.asarray(
            [role.offset for role in template.roles], dtype=np.float32
        )
        # Lateral sign: the centralized template uses
        # lateral = (corridor_y, -corridor_x), i.e. the mission direction
        # rotated -90 deg, whereas the proper rotation R(psi) maps the template
        # +y axis to +90 deg. Negating the template lateral coordinate makes the
        # two conventions agree, so the decentralized and centralized
        # controllers aim at the *same* geometric formation and the Gate D5
        # comparison is like-for-like. Keeping R a proper rotation (det = +1)
        # rather than folding the flip into R keeps the equivariance argument
        # intact.

    @staticmethod
    def _line_template(ranks: Sequence[int], spacing: float) -> np.ndarray:
        """Single file along the mission direction, ordered by `ranks`."""
        n = len(ranks)
        out = np.zeros((n, 2), dtype=np.float32)
        for robot_id, rank in enumerate(ranks):
            out[robot_id] = ((rank - (n - 1) / 2) * spacing, 0.0)
        return out

    @staticmethod
    def _compact_template(n: int, spacing: float) -> np.ndarray:
        template = construct_topology_from_spacing(COMPACT, n, spacing)
        return np.asarray(
            [role.offset for role in template.roles], dtype=np.float32
        )

    @classmethod
    def from_index(cls, n: int, spacing: float) -> "RoleAssignment":
        """Pure persistent-index roles: robot i takes line rank i.

        The strictest possible reading of "persistent offline role" -- roles
        depend on nothing but the robot ID. Costs nothing at runtime, but if
        the spawn order disagrees with the role order the robots must trade
        places to form the line. Reported as its own arm; not silently
        preferred.
        """
        return cls(
            keep=cls._keep_template(n, spacing),
            line=cls._line_template(list(range(n)), spacing),
            spacing=spacing,
            source="index",
            compact=cls._compact_template(n, spacing),
        )

    @classmethod
    def simulate_mission_setup_from_initial_formation(
            cls, initial_positions: np.ndarray,
            mission_dir: Vec2, spacing: float) -> "RoleAssignment":
        """BOUNDARY: reads the joint state. Mission setup only, never at runtime.

        Carries the `simulate_` prefix deliberately. An audit established that
        this method is the one place in the package that reads an (N, 2)
        all-robot array -- `along = pos @ d` is a sort over the joint state,
        which is the same operation as the centralized assignment service this
        module replaces, merely moved to t = 0. Calling it "offline" does not
        make it local, so it is named and guarded as a boundary rather than
        argued away. `guards.py` asserts no control-loop function calls it.

        Mission-configuration assignment from the known start configuration.

        Called exactly once, before t = 0, as part of configuring the mission --
        the same status as loading the goal or the controller gains. It is NOT
        a runtime service: no control step may call it, and after t = 0 the
        roles are frozen constants on each robot.

        Line rank follows the robots' initial ordering along the mission
        direction, so the template each robot is assigned is the one it is
        already closest to and no crossing manoeuvre is required at t = 0.
        Ties broken by robot ID, so the result is deterministic.
        """
        pos = np.asarray(initial_positions, dtype=np.float32)
        if pos.ndim != 2 or pos.shape[1] != 2:
            raise ValueError("initial_positions must be (N, 2)")
        n = len(pos)
        d = np.asarray(mission_dir, dtype=np.float32)
        along = pos @ d
        order = sorted(range(n), key=lambda i: (float(along[i]), i))
        ranks = [0] * n
        for rank, robot_id in enumerate(order):
            ranks[robot_id] = rank
        return cls(
            keep=cls._keep_template(n, spacing),
            line=cls._line_template(ranks, spacing),
            spacing=spacing,
            source="initial_formation",
            compact=cls._compact_template(n, spacing),
        )


def pairwise_offset(role_i: Vec2, role_j: Vec2, mission_dir: Vec2) -> np.ndarray:
    """d_ij^tau = R(psi_mission) [r_j^tau - r_i^tau], in world coordinates.

    Robot i needs only: its own role, the neighbour's communicated role, and
    the shared mission direction. Exactly antisymmetric, because it is a
    rotation applied to a difference.
    """
    return np.asarray(
        local_pairwise_offset(role_i, role_j, mission_dir), dtype=np.float32
    )


def desired_offset_for_neighbour(view: "RobotView", neighbour: "NeighbourRecord",
                                 mode: int) -> np.ndarray:
    """Convenience wrapper over a RobotView / NeighbourRecord pair.

    The isinstance gate is load-bearing, not defensive style: without it a
    duck-typed object carrying a `positions` array is accepted, which an audit
    demonstrated by smuggling a (6, 2) joint-state array through this exact
    call -- the one the controller uses at `local_controller.py:121`.
    """
    if not isinstance(view, RobotView):
        raise CentralizedAccessError(
            "desired_offset_for_neighbour accepts a RobotView only; a duck-typed "
            "object may carry joint state"
        )
    if not isinstance(neighbour, NeighbourRecord):
        raise CentralizedAccessError(
            "desired_offset_for_neighbour accepts a NeighbourRecord only"
        )
    role_i = view.role_keep if mode == KEEP else view.role_line
    role_j = neighbour.role_keep if mode == KEEP else neighbour.role_line
    return pairwise_offset(role_i, role_j, view.mission_dir)


# ---------------------------------------------------------------------------
# Limitations, stated here so they cannot be lost between documents
# ---------------------------------------------------------------------------
ROLE_LIMITATIONS: Dict[str, str] = {
    "no_reassignment": (
        "Roles are never reassigned at runtime. There is no election, no "
        "bidding, and no assignment service. A robot keeps its role for the "
        "whole mission."
    ),
    "dropout": (
        "If a robot drops out, its slot in the template stays empty. Surviving "
        "robots hold their own roles and the formation retains a gap. No "
        "attrition-resilience claim is made."
    ),
    "missing_neighbour": (
        "A formation neighbour that is stale or out of communication range "
        "simply contributes no formation term; the remaining pairwise terms "
        "still define a consistent geometry, because the constraints are "
        "pairwise rather than centroid-referenced."
    ),
    "shared_frame": (
        "Requires a shared coordinate frame and a shared mission direction, "
        "both explicit assumptions. Without them R(psi_mission) would differ "
        "per robot and the templates would not agree."
    ),
    "rigidity": (
        "Pairwise displacement constraints determine the formation only up to "
        "a common translation. That is sufficient here -- absolute placement "
        "is supplied by the shared goal term, not by the formation term."
    ),
}
