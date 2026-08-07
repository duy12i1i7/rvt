"""Mission-staged topology transition (Phase 8E-MC, decisions 1 and 2).

Owner decision 1: a changed-topology transition is a mission-staged operation.
While a robot participates in an active transition intent it locally suppresses
**only** its ordinary mission-progression contribution. Formation/transition
tracking, damping, local obstacle response, the local safety projection and the
normal dynamics all continue; simulator time continues; velocity is never zeroed
and no robot is teleported. There is no global pause.

Why staging is needed
---------------------
The frozen `generic_role_space_profile` and the Phase 7R reference were
qualified from the exact source template **at rest** (minimum robot-robot
clearance 0.5247 m against the frozen 0.4000 m requirement). Publication
execution previously ran the same transition while the team carried forward
momentum, and minimum separation fell to 0.3979 m. Holding position, goal and
obstacles fixed and zeroing only velocity restored 0.4166 m, which established
the coupling as velocity-dependent rather than a frame error.

No new numerical constant
-------------------------
`v_settle` is derived, not chosen:

    v_settle = a_max * dt

the speed that the frozen acceleration bound can remove within one frozen
control interval. Both factors are read from the authoritative runtime
configuration; nothing here is written as a literal.
"""

from __future__ import annotations

import math
from typing import Tuple

# Frozen Phase 7 lifecycle states during which a robot is mission-staged. These
# are the existing repository state names; no new state is invented.
MISSION_STAGED_STATES: Tuple[str, ...] = (
    "INTENT_ACTIVE",
    "CANDIDATE_SCORE_AGREEMENT",
    "WAITING_FOR_LOCAL_READINESS",
    "ALL_READY_AGREEMENT",
    "TOPOLOGY_CONFIRMATION",
    "TOPOLOGY_COMMITTED",
    "TRANSITION_EXECUTION",
    "TARGET_DWELL",
)

# States on which the ordinary mission-progression contribution resumes.
MISSION_RESUMED_STATES: Tuple[str, ...] = (
    "STABLE_TOPOLOGY", "COMPLETE", "ABORTED", "REARMED",
)


def settle_speed_threshold(runtime_config) -> float:
    """`v_settle = a_max * dt`, derived from the authoritative configuration."""
    return float(
        runtime_config.physical.maximum_acceleration_meters_per_second_squared
    ) * float(runtime_config.physical.control_period_seconds)


def motion_settled(robot, runtime_config) -> bool:
    """Robot-local predicate: own speed only, plus frozen local config.

    Uses the same Euclidean speed convention as the rest of the runtime. No
    scaling coefficient, epsilon or tuning factor is applied.
    """
    return math.hypot(*robot.velocity) <= settle_speed_threshold(runtime_config)


def mission_staged(robot) -> bool:
    """True when this robot suppresses its own mission-progression term.

    Decided from the robot's own frozen lifecycle state alone. A hold candidate
    never creates an intent, so it can never stage.
    """
    if robot.protocol_node.active_intent is None:
        return False
    return robot.protocol_node.state in MISSION_STAGED_STATES
