"""Robot-local ego graph G_i and its machine-readable feature audit.

Robot i scores a candidate mode tau from a graph it can build entirely by
itself. The graph has one centre node (robot i), one node per *valid* one-hop
communication neighbour, and one node per obstacle robot i sensed with its own
sensor. Nothing else exists in G_i -- there is no node for a robot outside
R_comm, no node for an obstacle outside R_obs, and no node standing for "the
team", "the centroid", or "the environment".

Input contract
--------------
`build_ego_graph` accepts a `RobotView` and nothing else. It cannot be handed
the simulator's obs dict or an (N, 2) joint-position array: both are rejected
with `CentralizedAccessError`. This module contains no `simulate_` function and
never reads global state; the simulated radio+sensor boundary that manufactures
`RobotView`s lives outside deployable code.

Conventions inherited from the contract
---------------------------------------
* `NeighbourRecord.rel_position` is p_j - p_i and `rel_velocity` is v_j - v_i.
  A neighbour's absolute position never exists in this module.
* `RobotView.obstacles` entries are ego-relative: `(ox, oy, radius)` where
  (ox, oy) = o - p_i, matching `local_controller.local_controller`. A 5-tuple
  `(ox, oy, radius, vx, vy)` is also accepted, where (vx, vy) is the obstacle
  velocity *relative to robot i*; static obstacles use the 3-tuple form and get
  a zero relative-velocity block.
* Robot i's own absolute position is deliberately NOT a feature. It is
  permitted information (`self_state`), but excluding it makes every geometric
  feature translation-invariant, which is what makes the "out-of-range robot
  cannot alter G_i" tests meaningful rather than accidental.
* Robot IDs are deliberately NOT features. IDs enter only as the identity of a
  neighbour record; the network sees the neighbour's *role coordinate*, which
  travels with the physical robot. This is what makes relabelling equivariance
  hold (`tests/test_ego_graph_locality.py::test_id_relabelling_equivariance`).

Shared feature width
--------------------
Self, neighbour and obstacle nodes are encoded into one common width
(`FEATURE_DIM`) with explicit zero blocks, so a single shared-weight GNN layer
consumes all three node kinds. `FEATURE_LAYOUT` documents the exact column
layout; `feature_audit()` is its machine-readable form and is the backing data
for `docs/EGO_GRAPH_FEATURE_AUDIT.md`.

No global pooling
-----------------
Edges connect the centre to every other node, bidirectionally, and nothing
else. The only aggregation any consumer can perform is over edges incident to
the centre -- i.e. over robot i's own one-hop neighbourhood and its own sensed
obstacles. There is no node that reads all other nodes, so there is no place a
graph-wide mean/max could be computed even if a downstream model wanted one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch

from .system_model import (
    KEEP,
    LINE,
    MODES,
    CentralizedAccessError,
    CommParams,
    ConsensusParams,
    PERMITTED_LOCAL_SOURCES,
    PROHIBITED_OBS_KEYS,
    RobotView,
)

# --------------------------------------------------------------------------
# Node kinds
# --------------------------------------------------------------------------
NODE_SELF = 0
NODE_NEIGHBOUR = 1
NODE_OBSTACLE = 2
NODE_KINDS: Tuple[int, int, int] = (NODE_SELF, NODE_NEIGHBOUR, NODE_OBSTACLE)
NODE_KIND_NAME: Dict[int, str] = {
    NODE_SELF: "self",
    NODE_NEIGHBOUR: "robot_neighbour",
    NODE_OBSTACLE: "obstacle",
}

# Mode -> one-hot index. MODES = (KEEP=0, LINE=2); split is removed, so the
# one-hot has width 2 and the raw integer mode id is never used as a feature
# (0 and 2 would otherwise be read as an ordered scalar).
MODE_INDEX: Dict[int, int] = {mode: k for k, mode in enumerate(MODES)}
N_MODES = len(MODES)

_EPS = 1e-9


# --------------------------------------------------------------------------
# Feature layout
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FeatureBlock:
    """One contiguous column block of `node_x`."""

    start: int
    stop: int
    name: str
    node_kinds: Tuple[int, ...]
    permitted_source: Tuple[str, ...]
    justification: str

    @property
    def width(self) -> int:
        return self.stop - self.start

    @property
    def slice(self) -> slice:
        return slice(self.start, self.stop)


def _build_blocks(specs: Sequence[Tuple[str, int, Tuple[int, ...], Tuple[str, ...], str]]
                  ) -> Tuple[FeatureBlock, ...]:
    out: List[FeatureBlock] = []
    cursor = 0
    for name, width, kinds, sources, justification in specs:
        out.append(FeatureBlock(cursor, cursor + width, name, kinds, sources, justification))
        cursor += width
    return tuple(out)


# Blocks shared by more than one node kind come first, then the kind-exclusive
# blocks. A block that does not apply to a node kind is an explicit zero block
# for that kind -- never a reused slot with a different meaning.
FEATURE_BLOCKS: Tuple[FeatureBlock, ...] = _build_blocks((
    (
        "rel_position", 2, (NODE_SELF, NODE_NEIGHBOUR, NODE_OBSTACLE),
        ("self_state", "one_hop_messages", "local_obstacles"),
        "Position of the node relative to p_i. Self is exactly (0, 0); a "
        "neighbour is p_j - p_i straight out of NeighbourRecord; an obstacle "
        "is the vector from p_i to the closest point of its disc. No absolute "
        "position of any robot -- including robot i -- ever enters node_x, so "
        "the whole block is translation-invariant.",
    ),
    (
        "distance", 1, (NODE_SELF, NODE_NEIGHBOUR, NODE_OBSTACLE),
        ("self_state", "one_hop_messages", "local_obstacles"),
        "Range to the node: 0 for self, norm(p_j - p_i) for a neighbour, and "
        "the clearance max(norm(o - p_i) - radius, 0) for an obstacle. "
        "Pairwise range to one observed entity; not a min/mean over the swarm "
        "or over the obstacle field.",
    ),
    (
        "bearing_cos_sin", 2, (NODE_SELF, NODE_NEIGHBOUR, NODE_OBSTACLE),
        ("self_state", "one_hop_messages", "local_obstacles"),
        "Unit vector toward the node (toward the obstacle *centre* for "
        "obstacles, so the bearing stays defined at contact where the "
        "clearance vector vanishes). Encoded as cos/sin rather than a raw "
        "angle so it is continuous at +-pi and rotates consistently with "
        "rel_position. Zero for self, whose bearing is undefined.",
    ),
    (
        "node_kind_onehot", 3, (NODE_SELF, NODE_NEIGHBOUR, NODE_OBSTACLE),
        ("self_state", "one_hop_messages", "local_obstacles"),
        "One-hot [self, robot_neighbour, obstacle]. Lets one shared-weight "
        "encoder disambiguate the zero blocks of the three node kinds without "
        "three separate weight matrices.",
    ),
    (
        "rel_velocity", 2, (NODE_NEIGHBOUR, NODE_OBSTACLE),
        ("one_hop_messages", "local_obstacles"),
        "Velocity of the node relative to robot i: v_j - v_i from the "
        "neighbour beacon, or the obstacle's relative velocity (zeros for the "
        "static obstacles used here). Self is a zero block -- its own velocity "
        "has its own column block, because 'my velocity' and 'their velocity "
        "minus mine' are different quantities and must not share a slot.",
    ),
    (
        "role_candidate", 2, (NODE_SELF, NODE_NEIGHBOUR),
        ("self_id_and_role", "one_hop_messages"),
        "Template-frame role coordinate for the CANDIDATE mode tau: robot i's "
        "own role for the self node, the neighbour's communicated role for a "
        "neighbour node. Roles are mission constants fixed before t=0, not a "
        "runtime assignment service. The pairwise desired offset "
        "d_ij = R(psi)(r_j - r_i) is recoverable by the network from this "
        "block plus self_mission_dir, so no centroid-referenced target is "
        "needed.",
    ),
    (
        "committed_mode_onehot", 2, (NODE_SELF, NODE_NEIGHBOUR),
        ("committed_mode", "one_hop_messages"),
        "Currently committed mode as a one-hot over (KEEP, LINE): robot i's "
        "own commitment from local memory, a neighbour's from its beacon. "
        "This is the *neighbourhood's* commitment state, never a swarm-wide "
        "tally.",
    ),
    (
        "self_velocity", 2, (NODE_SELF,),
        ("self_state",),
        "Robot i's own velocity in the shared frame. Own state, permitted "
        "without qualification.",
    ),
    (
        "self_goal_rel", 2, (NODE_SELF,),
        ("shared_goal", "self_state"),
        "goal - p_i. The goal is a shared mission constant loaded identically "
        "on every robot; subtracting robot i's own position needs no one "
        "else's state. Replaces the centralized 'goal - centroid' progress "
        "direction.",
    ),
    (
        "self_mission_dir", 2, (NODE_SELF,),
        ("shared_frame",),
        "Unit mission/corridor direction (corridor_dx, corridor_dy), a shared "
        "mission constant. Required to interpret template-frame role "
        "coordinates in the world frame via R(psi_mission); identical on "
        "every robot, so no agreement protocol is involved.",
    ),
    (
        "self_steps_since_decision", 1, (NODE_SELF,),
        ("local_memory",),
        "Control steps since robot i's last decision epoch, divided by "
        "ConsensusParams.decision_interval. Robot i's own epoch counter; no "
        "global clock and no synchronisation barrier is assumed beyond the "
        "shared control period already stated in CommParams.",
    ),
    (
        "self_local_progress", 1, (NODE_SELF,),
        ("local_memory",),
        "Robot i's own progress estimate along the mission direction, from its "
        "own odometry and the shared goal. Explicitly NOT obs['progress'], "
        "which is computed from the swarm centroid and is prohibited.",
    ),
    (
        "candidate_mode_onehot", 2, (NODE_SELF,),
        ("model_parameters",),
        "One-hot of the candidate mode tau being scored. G_i is built once per "
        "candidate, so the score head is q_i(tau) = f(G_i(tau)) with shared "
        "weights across tau rather than a two-headed output; the flag is a "
        "query, not an observation, and lives on the centre node only.",
    ),
    (
        "nb_message_age_norm", 1, (NODE_NEIGHBOUR,),
        ("one_hop_messages",),
        "Age of the newest message from this neighbour, divided by "
        "CommParams.delta_stale_steps. Tells the encoder how much to trust a "
        "record under delay/loss. Records older than delta_stale_steps are not "
        "admitted at all, so the value lies in [0, 1].",
    ),
    (
        "nb_link_valid", 1, (NODE_NEIGHBOUR,),
        ("one_hop_messages",),
        "Link-validity flag for the neighbour record. Under the nominal "
        "admission rule (link up AND age <= delta_stale_steps) every admitted "
        "node carries 1.0; the column is retained so a degraded-link variant "
        "that admits stale records with a 0.0 flag has the identical feature "
        "width and can load the same weights. Constant-by-construction here "
        "and asserted as such by the locality tests.",
    ),
    (
        "obs_radius", 1, (NODE_OBSTACLE,),
        ("local_obstacles",),
        "Radius of the sensed obstacle, so the encoder can separate the "
        "clearance from the object size. Per-obstacle, from robot i's own "
        "sensor.",
    ),
    (
        "obs_valid", 1, (NODE_OBSTACLE,),
        ("local_obstacles",),
        "Observation-validity flag for the obstacle record, mirroring "
        "nb_link_valid: constant 1.0 under the nominal rule (only obstacles "
        "within CommParams.r_obs are admitted), retained so a variant that "
        "carries decayed observations keeps the same feature width.",
    ),
))

FEATURE_DIM: int = FEATURE_BLOCKS[-1].stop

# The documented layout, keyed by the half-open column range. (Slice objects
# are unhashable before Python 3.12, so the key is the (start, stop) tuple and
# `FEATURE_SLICES` provides the slice objects by name.)
FEATURE_LAYOUT: Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], Tuple[int, ...]]] = {
    (b.start, b.stop): (b.name, b.permitted_source, b.node_kinds) for b in FEATURE_BLOCKS
}
FEATURE_SLICES: Dict[str, slice] = {b.name: b.slice for b in FEATURE_BLOCKS}


def _blk(name: str) -> FeatureBlock:
    for b in FEATURE_BLOCKS:
        if b.name == name:
            return b
    raise KeyError(name)


# --------------------------------------------------------------------------
# Edge layout
# --------------------------------------------------------------------------
EDGE_BLOCKS: Tuple[Tuple[str, int, str], ...] = (
    ("delta", 2, "Position of the destination node relative to the source node, "
                 "in the shared frame. For a centre->node edge this is the node's "
                 "rel_position; for the node->centre edge it is its negation, so "
                 "the pair is exactly antisymmetric."),
    ("distance", 1, "Range along the edge, identical in both directions."),
    ("bearing_cos_sin", 2, "Unit vector along the edge, negated on the reverse "
                           "edge. cos/sin rather than a raw angle."),
    ("direction_onehot", 2, "[centre_to_node, node_to_centre]. Lets one shared "
                            "message function distinguish the two directions "
                            "without duplicating weights."),
    ("edge_kind_onehot", 2, "[robot_robot, robot_obstacle], taken from the node "
                            "kind of the non-centre endpoint."),
)
EDGE_DIM: int = sum(w for _, w, _ in EDGE_BLOCKS)
EDGE_LAYOUT: Dict[Tuple[int, int], Tuple[str, str]] = {}
_c = 0
for _name, _w, _just in EDGE_BLOCKS:
    EDGE_LAYOUT[(_c, _c + _w)] = (_name, _just)
    _c += _w
del _c, _name, _w, _just


# --------------------------------------------------------------------------
# Global features that were considered and rejected, with their replacements.
# Backing data for the "rejected features" section of the audit document.
# --------------------------------------------------------------------------
REJECTED_GLOBAL_FEATURES: Dict[str, str] = {
    "swarm_centroid": (
        "Rejected: requires every robot's position. Replaced by rel_position on "
        "one-hop neighbour nodes plus the pairwise role difference, which "
        "reproduces the centroid-referenced formation target exactly when N_i "
        "is the whole team (see local_controller docstring)."
    ),
    "global_formation_error": (
        "Rejected: obs['formation_error'] is centroid-derived. Replaced by the "
        "per-neighbour residual the encoder can form from rel_position and "
        "role_candidate, aggregated only over robot i's own neighbours."
    ),
    "graph_wide_mean_or_max_pooling": (
        "Rejected: an all-node readout is a disguised all-reduce. Replaced by "
        "aggregation over edges incident to the centre only; G_i contains no "
        "node that is adjacent to every robot in the team."
    ),
    "global_min_clearance": (
        "Rejected: a min over every robot-obstacle pair in the world. Replaced "
        "by the per-obstacle `distance` column on locally sensed obstacle "
        "nodes; the min over robot i's OWN obstacle nodes is a local quantity "
        "and is left for the encoder to form."
    ),
    "global_bottleneck": (
        "Rejected: obs['bottleneck'] is computed from the joint state. "
        "Replaced by the local obstacle node set: the gap geometry robot i can "
        "actually see, which is what it can actually react to."
    ),
    "global_obstacle_centroid": (
        "Rejected: an average over the whole obstacle field, unbounded by "
        "sensor range. Replaced by one node per obstacle within r_obs; no "
        "summary statistic over unobserved obstacles exists."
    ),
    "out_of_range_robot_state": (
        "Rejected: any robot beyond r_comm. No node is created for it, so its "
        "motion cannot change a single byte of G_i -- asserted directly by "
        "test_out_of_range_robot_cannot_change_graph."
    ),
    "team_progress": (
        "Rejected: obs['progress'] tracks the centroid along the corridor. "
        "Replaced by self_local_progress, robot i's own progress from its own "
        "odometry and the shared goal."
    ),
    "topology_switch_counter": (
        "Rejected: obs['topology_switches'] counts team-level mode changes. "
        "Replaced by committed_mode_onehot on the centre and its neighbours "
        "plus self_steps_since_decision, all robot-local memory."
    ),
    "robot_id_as_feature": (
        "Rejected: not global, but it would break relabelling equivariance and "
        "would let the network memorise slot identity. Replaced by "
        "role_candidate, which travels with the physical robot."
    ),
}


# --------------------------------------------------------------------------
# Config resolution
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class EgoGraphConfig:
    """Constants `build_ego_graph` needs. All are mission constants."""

    comm: CommParams = CommParams()
    consensus: ConsensusParams = ConsensusParams()


def _resolve_cfg(cfg: Optional[object]) -> EgoGraphConfig:
    """Accept an EgoGraphConfig, a CommParams, `None`, or any object carrying
    `.comm` / `.consensus` (e.g. the repo-wide Config once it grows them).
    Missing pieces fall back to the contract defaults in `system_model`."""
    if cfg is None:
        return EgoGraphConfig()
    if isinstance(cfg, EgoGraphConfig):
        return cfg
    if isinstance(cfg, CommParams):
        return EgoGraphConfig(comm=cfg)
    comm = getattr(cfg, "comm", None)
    consensus = getattr(cfg, "consensus", None)
    return EgoGraphConfig(
        comm=comm if isinstance(comm, CommParams) else CommParams(),
        consensus=consensus if isinstance(consensus, ConsensusParams) else ConsensusParams(),
    )


# --------------------------------------------------------------------------
# The ego graph
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class EgoGraph:
    """Robot i's ego graph for one candidate mode.

    `center_index` is always 0. `node_kind[v]` is one of NODE_SELF /
    NODE_NEIGHBOUR / NODE_OBSTACLE. `node_source_id[v]` is the neighbour's
    robot ID for neighbour nodes, robot i's own ID for node 0, and -1 for
    obstacle nodes; it exists for tests and logging and is NEVER a feature.
    """

    node_x: torch.Tensor          # (V, FEATURE_DIM) float32
    edge_index: torch.Tensor      # (2, E) int64
    edge_attr: torch.Tensor       # (E, EDGE_DIM) float32
    n_nodes: int
    node_kind: torch.Tensor       # (V,) int64
    candidate_mode: int
    center_index: int = 0
    node_source_id: Tuple[int, ...] = field(default_factory=tuple)

    @property
    def n_edges(self) -> int:
        return int(self.edge_index.shape[1])

    @property
    def n_neighbour_nodes(self) -> int:
        return int((self.node_kind == NODE_NEIGHBOUR).sum().item())

    @property
    def n_obstacle_nodes(self) -> int:
        return int((self.node_kind == NODE_OBSTACLE).sum().item())

    @property
    def n_robot_nodes(self) -> int:
        """Robot i plus its admitted one-hop neighbours."""
        return 1 + self.n_neighbour_nodes

    def fingerprint(self) -> bytes:
        """Exact byte image of the three tensors, for identity assertions."""
        return (self.node_x.numpy().tobytes()
                + self.edge_index.numpy().tobytes()
                + self.edge_attr.numpy().tobytes()
                + self.node_kind.numpy().tobytes())


def _reject_non_view(view: object) -> None:
    """Refuse anything that is not a RobotView, loudly and by name."""
    if isinstance(view, RobotView):
        return
    if isinstance(view, dict):
        offending = sorted(set(view.keys()) & set(PROHIBITED_OBS_KEYS))
        raise CentralizedAccessError(
            "build_ego_graph received a dict (an obs dict). Deployable code may "
            "not read the simulator observation; only a RobotView is accepted. "
            "Prohibited keys present: {}".format(offending or "none, but a dict "
                                                 "is still not a RobotView")
        )
    if isinstance(view, (np.ndarray, torch.Tensor)):
        raise CentralizedAccessError(
            "build_ego_graph received an array of shape {}. An (N, 2) joint-state "
            "array is exactly the centralized input this module exists to "
            "forbid; pass a RobotView.".format(tuple(view.shape))
        )
    if isinstance(view, (list, tuple)):
        raise CentralizedAccessError(
            "build_ego_graph received a {}; a sequence of robot states is joint "
            "state. Pass a single RobotView.".format(type(view).__name__)
        )
    raise TypeError(
        "build_ego_graph accepts a RobotView only, got {}".format(type(view).__name__)
    )


def _mode_onehot(mode: int) -> List[float]:
    out = [0.0] * N_MODES
    idx = MODE_INDEX.get(int(mode))
    if idx is None:
        raise ValueError("mode {} is not in {} (split is removed)".format(mode, MODES))
    out[idx] = 1.0
    return out


def _kind_onehot(kind: int) -> List[float]:
    out = [0.0] * len(NODE_KINDS)
    out[kind] = 1.0
    return out


def _unit(dx: float, dy: float) -> Tuple[float, float]:
    norm = math.hypot(dx, dy)
    if norm < _EPS:
        return (0.0, 0.0)
    return (dx / norm, dy / norm)


def _role_for(role_keep: Sequence[float], role_line: Sequence[float], mode: int) -> Tuple[float, float]:
    src = role_keep if mode == KEEP else role_line
    return (float(src[0]), float(src[1]))


def _neighbour_admitted(nb, comm: CommParams) -> bool:
    """Nominal admission rule for N_i: link up and message not stale.

    `delta_stale_steps` comes from the contract; a record older than that is
    excluded from N_i entirely (system_model.CommParams).
    """
    if not bool(nb.link_valid):
        return False
    age = int(nb.message_age_steps)
    return 0 <= age <= int(comm.delta_stale_steps)


def _obstacle_fields(entry: Sequence[float]) -> Tuple[float, float, float, float, float]:
    """(ox, oy, radius, rel_vx, rel_vy) from a 3- or 5-tuple obstacle record."""
    if len(entry) == 3:
        ox, oy, radius = entry
        return float(ox), float(oy), float(radius), 0.0, 0.0
    if len(entry) == 5:
        ox, oy, radius, vx, vy = entry
        return float(ox), float(oy), float(radius), float(vx), float(vy)
    raise ValueError(
        "obstacle record must be (dx, dy, radius) or (dx, dy, radius, rel_vx, "
        "rel_vy), got length {}".format(len(entry))
    )


def build_ego_graph(view: RobotView, cfg: Optional[object] = None,
                    mode: int = LINE) -> EgoGraph:
    """Build G_i(tau) for robot i alone.

    Parameters
    ----------
    view : RobotView
        Robot i's own view. The ONLY data input. Anything else raises.
    cfg :
        Source of `CommParams` / `ConsensusParams`; `None` uses the contract
        defaults. Constants only -- never data.
    mode : int
        The candidate mode tau being scored (KEEP or LINE).

    Nodes: [robot i] + [admitted one-hop neighbours, in view order] +
    [locally sensed obstacles, in view order]. Edges: centre <-> every other
    node, both directions, and nothing else.
    """
    _reject_non_view(view)
    if int(mode) not in MODE_INDEX:
        raise ValueError("mode {} is not in {} (split is removed)".format(mode, MODES))
    conf = _resolve_cfg(cfg)
    comm, consensus = conf.comm, conf.consensus

    rows: List[List[float]] = []
    kinds: List[int] = []
    source_ids: List[int] = []
    # Per-node edge geometry: (delta_x, delta_y, distance, cos, sin, kind)
    geom: List[Tuple[float, float, float, float, float, int]] = []

    # ---- node 0: robot i ------------------------------------------------
    p_i = (float(view.position[0]), float(view.position[1]))
    goal_rel = (float(view.goal[0]) - p_i[0], float(view.goal[1]) - p_i[1])
    mission = _unit(float(view.mission_dir[0]), float(view.mission_dir[1]))
    denom_epoch = float(max(int(consensus.decision_interval), 1))

    self_row = [0.0] * FEATURE_DIM
    self_row[_blk("rel_position").slice] = [0.0, 0.0]          # literally (0, 0)
    self_row[_blk("distance").slice] = [0.0]
    self_row[_blk("bearing_cos_sin").slice] = [0.0, 0.0]
    self_row[_blk("node_kind_onehot").slice] = _kind_onehot(NODE_SELF)
    self_row[_blk("role_candidate").slice] = list(
        _role_for(view.role_keep, view.role_line, int(mode)))
    self_row[_blk("committed_mode_onehot").slice] = _mode_onehot(int(view.committed_mode))
    self_row[_blk("self_velocity").slice] = [float(view.velocity[0]), float(view.velocity[1])]
    self_row[_blk("self_goal_rel").slice] = [goal_rel[0], goal_rel[1]]
    self_row[_blk("self_mission_dir").slice] = [mission[0], mission[1]]
    self_row[_blk("self_steps_since_decision").slice] = [
        float(int(view.steps_since_decision)) / denom_epoch]
    self_row[_blk("self_local_progress").slice] = [float(view.local_progress)]
    self_row[_blk("candidate_mode_onehot").slice] = _mode_onehot(int(mode))
    rows.append(self_row)
    kinds.append(NODE_SELF)
    source_ids.append(int(view.robot_id))

    # ---- neighbour nodes -------------------------------------------------
    age_denom = float(max(int(comm.delta_stale_steps), 1))
    for nb in view.neighbours:
        if not _neighbour_admitted(nb, comm):
            continue
        dx, dy = float(nb.rel_position[0]), float(nb.rel_position[1])
        dist = math.hypot(dx, dy)
        cos_b, sin_b = _unit(dx, dy)

        row = [0.0] * FEATURE_DIM
        row[_blk("rel_position").slice] = [dx, dy]
        row[_blk("distance").slice] = [dist]
        row[_blk("bearing_cos_sin").slice] = [cos_b, sin_b]
        row[_blk("node_kind_onehot").slice] = _kind_onehot(NODE_NEIGHBOUR)
        row[_blk("rel_velocity").slice] = [float(nb.rel_velocity[0]), float(nb.rel_velocity[1])]
        row[_blk("role_candidate").slice] = list(
            _role_for(nb.role_keep, nb.role_line, int(mode)))
        row[_blk("committed_mode_onehot").slice] = _mode_onehot(int(nb.committed_mode))
        row[_blk("nb_message_age_norm").slice] = [float(int(nb.message_age_steps)) / age_denom]
        row[_blk("nb_link_valid").slice] = [1.0]
        rows.append(row)
        kinds.append(NODE_NEIGHBOUR)
        source_ids.append(int(nb.robot_id))
        geom.append((dx, dy, dist, cos_b, sin_b, NODE_NEIGHBOUR))

    # ---- obstacle nodes --------------------------------------------------
    for entry in view.obstacles:
        ox, oy, radius, rvx, rvy = _obstacle_fields(entry)
        center_dist = math.hypot(ox, oy)
        clearance = max(center_dist - radius, 0.0)
        if clearance > float(comm.r_obs):
            # Outside robot i's own sensor footprint: not observed, no node.
            continue
        # Vector from p_i to the closest point of the obstacle disc.
        scale = 0.0 if center_dist < _EPS else max(1.0 - radius / center_dist, 0.0)
        cx, cy = ox * scale, oy * scale
        cos_b, sin_b = _unit(ox, oy)   # bearing toward the centre: defined at contact

        row = [0.0] * FEATURE_DIM
        row[_blk("rel_position").slice] = [cx, cy]
        row[_blk("distance").slice] = [clearance]
        row[_blk("bearing_cos_sin").slice] = [cos_b, sin_b]
        row[_blk("node_kind_onehot").slice] = _kind_onehot(NODE_OBSTACLE)
        row[_blk("rel_velocity").slice] = [rvx, rvy]
        row[_blk("obs_radius").slice] = [radius]
        row[_blk("obs_valid").slice] = [1.0]
        rows.append(row)
        kinds.append(NODE_OBSTACLE)
        source_ids.append(-1)
        geom.append((cx, cy, clearance, cos_b, sin_b, NODE_OBSTACLE))

    # ---- edges: centre <-> every other node, both directions -------------
    edge_src: List[int] = []
    edge_dst: List[int] = []
    edge_rows: List[List[float]] = []
    for offset, (dx, dy, dist, cos_b, sin_b, kind) in enumerate(geom):
        node = 1 + offset
        kind_oh = [1.0, 0.0] if kind == NODE_NEIGHBOUR else [0.0, 1.0]
        edge_src.append(0)
        edge_dst.append(node)
        edge_rows.append([dx, dy, dist, cos_b, sin_b, 1.0, 0.0] + kind_oh)
        edge_src.append(node)
        edge_dst.append(0)
        edge_rows.append([-dx, -dy, dist, -cos_b, -sin_b, 0.0, 1.0] + kind_oh)

    node_x = torch.tensor(rows, dtype=torch.float32).reshape(len(rows), FEATURE_DIM)
    if edge_rows:
        edge_index = torch.tensor([edge_src, edge_dst], dtype=torch.int64)
        edge_attr = torch.tensor(edge_rows, dtype=torch.float32)
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.int64)
        edge_attr = torch.zeros((0, EDGE_DIM), dtype=torch.float32)

    return EgoGraph(
        node_x=node_x,
        edge_index=edge_index,
        edge_attr=edge_attr,
        n_nodes=len(rows),
        node_kind=torch.tensor(kinds, dtype=torch.int64),
        candidate_mode=int(mode),
        center_index=0,
        node_source_id=tuple(source_ids),
    )


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------
def feature_audit() -> List[Dict[str, object]]:
    """One row per feature block: the machine-readable decentralization audit.

    Columns: index_range, name, node_kind, permitted_source, justification.
    Consumed by `tests/test_ego_graph_locality.py` and by
    `docs/EGO_GRAPH_FEATURE_AUDIT.md`.
    """
    rows: List[Dict[str, object]] = []
    for b in FEATURE_BLOCKS:
        rows.append({
            "index_range": (b.start, b.stop),
            "name": b.name,
            "node_kind": tuple(NODE_KIND_NAME[k] for k in b.node_kinds),
            "node_kind_ids": tuple(b.node_kinds),
            "permitted_source": tuple(b.permitted_source),
            "justification": b.justification,
        })
    return rows


def audit_markdown() -> str:
    """Render the audit table exactly as it appears in the audit document."""
    lines = [
        "| Columns | Feature | Node kinds | Permitted source | Justification |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in feature_audit():
        start, stop = row["index_range"]           # type: ignore[misc]
        lines.append("| `[{}:{}]` | `{}` | {} | {} | {} |".format(
            start, stop, row["name"],
            ", ".join(row["node_kind"]),           # type: ignore[arg-type]
            ", ".join("`{}`".format(s) for s in row["permitted_source"]),  # type: ignore[arg-type]
            row["justification"],
        ))
    return "\n".join(lines)


def audit_is_complete() -> bool:
    """True iff the audit tiles [0, FEATURE_DIM) with no gap or overlap and
    every source it names is in PERMITTED_LOCAL_SOURCES."""
    covered: List[int] = []
    for row in feature_audit():
        start, stop = row["index_range"]           # type: ignore[misc]
        covered.extend(range(start, stop))
        for src in row["permitted_source"]:        # type: ignore[union-attr]
            if src not in PERMITTED_LOCAL_SOURCES:
                return False
    return covered == list(range(FEATURE_DIM))
