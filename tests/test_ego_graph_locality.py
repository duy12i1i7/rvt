"""Locality evidence for the robot-local ego graph.

Eight required properties, each asserted against the real `build_ego_graph`:

1. an out-of-range robot cannot change a single byte of G_i;
2. an out-of-range robot cannot change the score q_i(tau);
3. removing a one-hop neighbour changes only the robots that observed it;
4. node ordering does not change the readout (sum aggregation at the centre);
5. robot-ID relabelling with consistent role relabelling is an equivariance;
6. every feature column is traceable to a PERMITTED_LOCAL_SOURCE;
7. no global pooling operator exists in G_i;
8. no tensor containing the joint state can reach the graph builder.

Plus two supporting tests: the builder runs on views manufactured from a real
`SwarmFormationEnv` observation, and the audit document has not drifted from
`feature_audit()`.

THE SIMULATION BOUNDARY IN THIS FILE
------------------------------------
`simulate_robot_views` and `simulate_robot_views_from_obs` below are the
test-side stand-in for the radio+sensor boundary. They read the joint state on
purpose -- that is what a simulated radio does -- and they are NOT deployable
code: they live in the test tree, nothing in `rvt_swarm.decentralized` imports
them, and `simulate_robot_views_from_obs` is the only function here that reads
the simulator's obs dict. Everything downstream of them sees a `RobotView` and
nothing else.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pytest
import torch

from rvt_swarm.config import Config
from rvt_swarm.decentralized.ego_graph import (
    EDGE_DIM,
    FEATURE_DIM,
    FEATURE_LAYOUT,
    NODE_KINDS,
    NODE_KIND_NAME,
    NODE_NEIGHBOUR,
    NODE_OBSTACLE,
    NODE_SELF,
    EgoGraph,
    EgoGraphConfig,
    audit_markdown,
    build_ego_graph,
    feature_audit,
)
from rvt_swarm.decentralized.roles import RoleAssignment
from rvt_swarm.decentralized.system_model import (
    KEEP,
    LINE,
    MODES,
    CentralizedAccessError,
    CommParams,
    ConsensusParams,
    NeighbourRecord,
    PERMITTED_LOCAL_SOURCES,
    PROHIBITED_OBS_KEYS,
    RobotView,
)

COMM = CommParams()
CONS = ConsensusParams()
CFG = EgoGraphConfig(comm=COMM, consensus=CONS)
GOAL = (12.0, 0.0)
MISSION = (1.0, 0.0)


# ---------------------------------------------------------------------------
# Simulation boundary (test-side only -- see module docstring)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SimRobot:
    """Ground-truth state of one robot, as only the simulator knows it."""

    robot_id: int
    position: Tuple[float, float]
    velocity: Tuple[float, float]
    role_keep: Tuple[float, float]
    role_line: Tuple[float, float]
    committed_mode: int


def simulate_robot_views(
    team: Sequence[SimRobot],
    obstacles: Sequence[Tuple[float, float, float]] = (),
    comm: CommParams = COMM,
    goal: Tuple[float, float] = GOAL,
    mission_dir: Tuple[float, float] = MISSION,
    epoch_id: int = 3,
    steps_since_decision: int = 7,
    message_age: Optional[Dict[Tuple[int, int], int]] = None,
) -> Dict[int, RobotView]:
    """SIMULATION BOUNDARY -- not deployable code.

    Reads the joint state (every robot's absolute position and velocity, and
    the world obstacle list) and emits, per robot, only what that robot could
    have obtained itself: its own state, ego-relative records for robots inside
    `r_comm`, and ego-relative records for obstacles inside `r_obs`.
    """
    ages = message_age or {}
    obstacles_world = [(float(x), float(y), float(r)) for x, y, r in obstacles]
    by_id = {r.robot_id: r for r in team}

    def degree_of(rid: int) -> int:
        me = by_id[rid]
        return sum(
            1 for other in team
            if other.robot_id != rid
            and math.dist(me.position, other.position) <= comm.r_comm
        )

    views: Dict[int, RobotView] = {}
    for me in team:
        nbs: List[NeighbourRecord] = []
        for other in team:
            if other.robot_id == me.robot_id:
                continue
            if math.dist(me.position, other.position) > comm.r_comm:
                continue          # beyond the radio: this robot does not exist for me
            nbs.append(NeighbourRecord(
                robot_id=other.robot_id,
                rel_position=(other.position[0] - me.position[0],
                              other.position[1] - me.position[1]),
                rel_velocity=(other.velocity[0] - me.velocity[0],
                              other.velocity[1] - me.velocity[1]),
                role_keep=other.role_keep,
                role_line=other.role_line,
                committed_mode=other.committed_mode,
                epoch_id=epoch_id,
                message_age_steps=int(ages.get((me.robot_id, other.robot_id), 0)),
                degree=degree_of(other.robot_id),
                link_valid=True,
            ))
        local_obs: List[Tuple[float, float, float]] = []
        for ox, oy, radius in obstacles_world:
            dx, dy = ox - me.position[0], oy - me.position[1]
            if max(math.hypot(dx, dy) - radius, 0.0) > comm.r_obs:
                continue          # beyond the sensor: this obstacle does not exist for me
            local_obs.append((dx, dy, radius))
        # Local progress: robot i's own displacement toward the shared goal,
        # from its own odometry. Not obs['progress'] (centroid-derived).
        along = (goal[0] - me.position[0]) * mission_dir[0] + (goal[1] - me.position[1]) * mission_dir[1]
        views[me.robot_id] = RobotView(
            robot_id=me.robot_id,
            position=me.position,
            velocity=me.velocity,
            role_keep=me.role_keep,
            role_line=me.role_line,
            committed_mode=me.committed_mode,
            epoch_id=epoch_id,
            steps_since_decision=steps_since_decision,
            local_progress=float(-along),
            goal=goal,
            mission_dir=mission_dir,
            neighbours=tuple(nbs),
            obstacles=tuple(local_obs),
        )
    return views


def simulate_robot_views_from_obs(obs: dict, roles: RoleAssignment,
                                  obstacle_radius: float,
                                  comm: CommParams = COMM) -> Dict[int, RobotView]:
    """SIMULATION BOUNDARY -- the only function in this file that reads the
    simulator's obs dict. Not deployable code."""
    positions = np.asarray(obs["positions"], dtype=np.float32)
    velocities = np.asarray(obs["velocities"], dtype=np.float32)
    world_obs = np.asarray(obs["obstacles"], dtype=np.float32).reshape(-1, 2)
    team = [
        SimRobot(
            robot_id=i,
            position=(float(positions[i, 0]), float(positions[i, 1])),
            velocity=(float(velocities[i, 0]), float(velocities[i, 1])),
            role_keep=roles.role_of(i, KEEP),
            role_line=roles.role_of(i, LINE),
            committed_mode=KEEP,
        )
        for i in range(len(positions))
    ]
    return simulate_robot_views(
        team,
        obstacles=[(float(o[0]), float(o[1]), float(obstacle_radius)) for o in world_obs],
        comm=comm,
        goal=(float(obs["goal"][0]), float(obs["goal"][1])),
        mission_dir=(float(obs["corridor_dx"]), float(obs["corridor_dy"])),
    )


# ---------------------------------------------------------------------------
# A deterministic shared-weight ego GNN, used only to turn a graph into a number
# ---------------------------------------------------------------------------
class TinyEgoGNN:
    """One message-passing layer with weights SHARED across all node kinds.

    Readout = [h_centre , SUM over edges incident to the centre]. The sum is
    what makes the readout invariant to node ordering (test 4), and the fact
    that only centre-incident edges are aggregated is what makes it a local
    operator rather than a global pooling operator (test 7).
    """

    def __init__(self, seed: int = 20260730, hidden: int = 8) -> None:
        g = torch.Generator().manual_seed(seed)
        self.hidden = hidden
        self.w_node = torch.randn(FEATURE_DIM, hidden, generator=g, dtype=torch.float64)
        self.w_msg = torch.randn(2 * hidden + EDGE_DIM, hidden, generator=g, dtype=torch.float64)
        self.w_out = torch.randn(2 * hidden, 1, generator=g, dtype=torch.float64)

    def __call__(self, graph: EgoGraph) -> torch.Tensor:
        h = torch.tanh(graph.node_x.double() @ self.w_node)      # shared weights
        src, dst = graph.edge_index[0], graph.edge_index[1]
        if graph.n_edges:
            m = torch.tanh(
                torch.cat([h[src], h[dst], graph.edge_attr.double()], dim=1) @ self.w_msg)
            incoming = m[dst == graph.center_index]
            agg = incoming.sum(dim=0) if incoming.numel() else torch.zeros(self.hidden, dtype=torch.float64)
        else:
            agg = torch.zeros(self.hidden, dtype=torch.float64)
        return (torch.cat([h[graph.center_index], agg]) @ self.w_out).squeeze()


MODEL = TinyEgoGNN()


# ---------------------------------------------------------------------------
# Fixtures: teams whose communication graph is deliberately NOT complete
# ---------------------------------------------------------------------------
def _roles(n: int) -> RoleAssignment:
    return RoleAssignment.from_index(n, spacing=0.9)


def chain_team(tail: Tuple[float, float] = (6.0, 0.1)) -> List[SimRobot]:
    """Four robots strung along x. With r_comm = 3.0 the comm graph is the path
    0-1-2-3: robots 0 and 2 are 4 m apart, 0 and 3 are 6 m apart."""
    roles = _roles(4)
    positions = [(0.0, 0.0), (2.0, 0.3), (4.0, -0.2), tail]
    velocities = [(0.1, 0.0), (0.2, -0.05), (0.15, 0.02), (0.05, 0.01)]
    modes = [KEEP, KEEP, LINE, LINE]
    return [
        SimRobot(i, positions[i], velocities[i], roles.role_of(i, KEEP),
                 roles.role_of(i, LINE), modes[i])
        for i in range(4)
    ]


CHAIN_OBSTACLES: Tuple[Tuple[float, float, float], ...] = (
    (1.0, 1.2, 0.35),      # near robots 0 and 1
    (2.6, -1.4, 0.35),     # near robot 1
    (30.0, 30.0, 0.35),    # far away: must never appear in any view
)


def star_team() -> List[SimRobot]:
    """Centre robot with three neighbours inside r_comm -- enough neighbours to
    make permutation and relabelling non-trivial."""
    roles = _roles(4)
    positions = [(0.0, 0.0), (1.1, 0.4), (-0.9, 1.0), (0.3, -1.2)]
    velocities = [(0.2, 0.05), (-0.1, 0.2), (0.05, -0.3), (0.11, 0.07)]
    modes = [KEEP, LINE, KEEP, LINE]
    return [
        SimRobot(i, positions[i], velocities[i], roles.role_of(i, KEEP),
                 roles.role_of(i, LINE), modes[i])
        for i in range(4)
    ]


STAR_OBSTACLES: Tuple[Tuple[float, float, float], ...] = (
    (1.4, 1.4, 0.35),
    (-1.6, -0.6, 0.5),
)


def _graphs(view: RobotView) -> Dict[int, EgoGraph]:
    return {mode: build_ego_graph(view, CFG, mode) for mode in MODES}


def _assert_identical(a: EgoGraph, b: EgoGraph, what: str) -> None:
    assert a.fingerprint() == b.fingerprint(), what + " (byte image differs)"
    assert torch.equal(a.node_x, b.node_x), what + " (node_x)"
    assert torch.equal(a.edge_index, b.edge_index), what + " (edge_index)"
    assert torch.equal(a.edge_attr, b.edge_attr), what + " (edge_attr)"
    assert torch.equal(a.node_kind, b.node_kind), what + " (node_kind)"
    assert a.n_nodes == b.n_nodes


# ---------------------------------------------------------------------------
# 1. An out-of-range robot cannot change G_i
# ---------------------------------------------------------------------------
def test_out_of_range_robot_cannot_change_graph():
    before = chain_team()
    after = chain_team(tail=(9.0, 4.0))       # robot 3 moves, stays out of range of 0

    # Pre-conditions: the move is real, and robot 3 is out of range of robot 0
    # both before and after, so the test cannot pass vacuously.
    assert before[3].position != after[3].position
    for team in (before, after):
        assert math.dist(team[0].position, team[3].position) > COMM.r_comm

    v_before = simulate_robot_views(before, CHAIN_OBSTACLES)
    v_after = simulate_robot_views(after, CHAIN_OBSTACLES)
    assert 3 not in v_before[0].neighbour_ids()
    assert 3 not in v_after[0].neighbour_ids()

    for mode in MODES:
        g0 = build_ego_graph(v_before[0], CFG, mode)
        g1 = build_ego_graph(v_after[0], CFG, mode)
        _assert_identical(g0, g1, "moving out-of-range robot 3 changed G_0 for mode {}".format(mode))

    # Non-vacuity: the move DID change the graph of the robot that observed it.
    assert 3 in v_before[2].neighbour_ids()
    g2_before = build_ego_graph(v_before[2], CFG, LINE)
    g2_after = build_ego_graph(v_after[2], CFG, LINE)
    assert g2_before.fingerprint() != g2_after.fingerprint()


# ---------------------------------------------------------------------------
# 2. An out-of-range robot cannot change q_i(tau)
# ---------------------------------------------------------------------------
def test_out_of_range_robot_cannot_change_score():
    v_before = simulate_robot_views(chain_team(), CHAIN_OBSTACLES)
    v_after = simulate_robot_views(chain_team(tail=(9.0, 4.0)), CHAIN_OBSTACLES)

    for mode in MODES:
        q_before = MODEL(build_ego_graph(v_before[0], CFG, mode))
        q_after = MODEL(build_ego_graph(v_after[0], CFG, mode))
        assert torch.equal(q_before, q_after), (
            "q_0(tau={}) changed when an out-of-range robot moved: {} -> {}".format(
                mode, float(q_before), float(q_after))
        )

    # Non-vacuity: the model is not a constant function of the graph.
    q_obs = MODEL(build_ego_graph(v_before[2], CFG, LINE))
    q_obs_moved = MODEL(build_ego_graph(v_after[2], CFG, LINE))
    assert not torch.equal(q_obs, q_obs_moved)


# ---------------------------------------------------------------------------
# 3. Removing a neighbour touches only the robots that observed it
# ---------------------------------------------------------------------------
def test_neighbour_removal_affects_only_observers():
    full = chain_team()
    dropped = [r for r in full if r.robot_id != 3]      # robot 3 leaves the team

    v_full = simulate_robot_views(full, CHAIN_OBSTACLES)
    v_drop = simulate_robot_views(dropped, CHAIN_OBSTACLES)

    observers = {i for i in (0, 1, 2) if 3 in v_full[i].neighbour_ids()}
    assert observers == {2}, "fixture broken: expected only robot 2 to observe robot 3"

    for i in (0, 1):
        for mode in MODES:
            _assert_identical(
                build_ego_graph(v_full[i], CFG, mode),
                build_ego_graph(v_drop[i], CFG, mode),
                "removing robot 3 changed G_{} which never observed it".format(i),
            )
            assert torch.equal(MODEL(build_ego_graph(v_full[i], CFG, mode)),
                               MODEL(build_ego_graph(v_drop[i], CFG, mode)))

    g_full = build_ego_graph(v_full[2], CFG, LINE)
    g_drop = build_ego_graph(v_drop[2], CFG, LINE)
    assert g_full.n_neighbour_nodes == g_drop.n_neighbour_nodes + 1
    assert g_full.fingerprint() != g_drop.fingerprint()


# ---------------------------------------------------------------------------
# 4. Node ordering does not change the readout
# ---------------------------------------------------------------------------
def test_node_ordering_does_not_change_readout():
    """Invariance mechanism, stated explicitly: the readout aggregates the
    per-edge messages of the edges INCOMING TO THE CENTRE with a SUM. A sum
    over a set is independent of the order in which the graph builder happened
    to emit the neighbour and obstacle nodes, so permuting `view.neighbours`
    (and `view.obstacles`) permutes the rows of node_x and the columns of
    edge_index but cannot move the readout beyond float round-off.
    """
    view = simulate_robot_views(star_team(), STAR_OBSTACLES)[0]
    assert view.degree == 3 and len(view.obstacles) == 2

    permuted = replace(
        view,
        neighbours=tuple(reversed(list(view.neighbours))),
        obstacles=tuple(reversed(list(view.obstacles))),
    )

    for mode in MODES:
        g_a = build_ego_graph(view, CFG, mode)
        g_b = build_ego_graph(permuted, CFG, mode)

        # The graphs really are different tensors -- only the readout matches.
        assert not torch.equal(g_a.node_x, g_b.node_x)
        assert g_a.n_nodes == g_b.n_nodes
        # Same multiset of node rows.
        rows_a = sorted(tuple(r.tolist()) for r in g_a.node_x)
        rows_b = sorted(tuple(r.tolist()) for r in g_b.node_x)
        assert rows_a == rows_b

        q_a, q_b = MODEL(g_a), MODEL(g_b)
        assert torch.allclose(q_a, q_b, rtol=0.0, atol=1e-12), (
            "readout is order dependent: {} vs {}".format(float(q_a), float(q_b)))


# ---------------------------------------------------------------------------
# 5. Robot-ID relabelling with consistent role relabelling
# ---------------------------------------------------------------------------
def _relabel(team: Sequence[SimRobot], perm: Dict[int, int]) -> List[SimRobot]:
    """New IDs, same physical robots. Roles travel with the robot, which is
    what 'consistent role relabelling' means: role coordinates are a property
    of the physical vehicle, not of its index in an array."""
    return [replace(r, robot_id=perm[r.robot_id]) for r in team]


def test_id_relabelling_equivariance():
    perm = {0: 5, 1: 9, 2: 2, 3: 7}
    base = star_team()
    relabelled = _relabel(base, perm)

    v_base = simulate_robot_views(base, STAR_OBSTACLES)
    v_relab = simulate_robot_views(relabelled, STAR_OBSTACLES)

    centre_before, centre_after = v_base[0], v_relab[perm[0]]
    assert centre_before.robot_id != centre_after.robot_id
    assert set(centre_after.neighbour_ids()) == {perm[i] for i in centre_before.neighbour_ids()}

    for mode in MODES:
        g_a = build_ego_graph(centre_before, CFG, mode)
        g_b = build_ego_graph(centre_after, CFG, mode)
        # IDs are not features, so with the physical ordering preserved the
        # feature tensors are byte-identical; only node_source_id changes.
        _assert_identical(g_a, g_b, "ID relabelling changed G_i for mode {}".format(mode))
        assert g_a.node_source_id != g_b.node_source_id

    # Relabelling plus a reordering of the neighbour list (what a real radio
    # would produce once IDs change) still leaves the readout unchanged.
    reordered = replace(
        centre_after,
        neighbours=tuple(sorted(centre_after.neighbours, key=lambda nb: nb.robot_id)),
    )
    assert [nb.robot_id for nb in reordered.neighbours] != [nb.robot_id for nb in centre_after.neighbours]
    for mode in MODES:
        assert torch.allclose(MODEL(build_ego_graph(centre_before, CFG, mode)),
                              MODEL(build_ego_graph(reordered, CFG, mode)),
                              rtol=0.0, atol=1e-12)

    # Non-vacuity: an INCONSISTENT relabelling -- IDs permuted but the role
    # coordinates left attached to the old indices -- must change the graph,
    # otherwise roles would not be entering the features at all.
    swapped = list(base)
    a, b = swapped[1], swapped[2]
    swapped[1] = replace(a, role_keep=b.role_keep, role_line=b.role_line)
    swapped[2] = replace(b, role_keep=a.role_keep, role_line=a.role_line)
    v_swapped = simulate_robot_views(swapped, STAR_OBSTACLES)
    changed = [mode for mode in MODES
               if build_ego_graph(v_base[0], CFG, mode).fingerprint()
               != build_ego_graph(v_swapped[0], CFG, mode).fingerprint()]
    assert changed == list(MODES), (
        "swapping two neighbours' roles left G_0 unchanged for modes {}".format(
            [m for m in MODES if m not in changed]))


# ---------------------------------------------------------------------------
# 6. Every feature is traceable to an allowed local source
# ---------------------------------------------------------------------------
def test_every_feature_traces_to_a_permitted_local_source():
    rows = feature_audit()
    assert rows, "feature_audit() is empty"

    # (a) every named source is in the contract's permitted list
    named = set()
    for row in rows:
        assert isinstance(row["permitted_source"], tuple) and row["permitted_source"]
        named.update(row["permitted_source"])
    assert named <= PERMITTED_LOCAL_SOURCES, (
        "audit names non-permitted sources: {}".format(sorted(named - PERMITTED_LOCAL_SOURCES)))

    # (b) the audit tiles every column of node_x -- no gaps, no overlaps
    covered: List[int] = []
    for row in rows:
        start, stop = row["index_range"]
        assert stop > start
        covered.extend(range(start, stop))
    assert covered == list(range(FEATURE_DIM)), (
        "audit does not tile [0, {}): {}".format(FEATURE_DIM, covered))
    assert len(set(covered)) == len(covered), "audit rows overlap"
    assert set(FEATURE_LAYOUT) == {row["index_range"] for row in rows}

    # (c) required columns are present and every row is attributed to real kinds
    for row in rows:
        assert set(row["node_kind_ids"]) <= set(NODE_KINDS)
        assert row["node_kind"] == tuple(NODE_KIND_NAME[k] for k in row["node_kind_ids"])
        assert isinstance(row["justification"], str) and len(row["justification"]) > 40
        assert row["name"] not in PROHIBITED_OBS_KEYS
        low = row["name"].lower()
        for banned in ("centroid", "global", "swarm", "team", "all_robots", "bottleneck"):
            assert banned not in low, "feature name {} looks global".format(row["name"])

    # (d) the zero-block claim is not documentation-only: for a node of kind k,
    # every column whose audit row does not list k must be exactly zero.
    view = simulate_robot_views(star_team(), STAR_OBSTACLES)[0]
    graph = build_ego_graph(view, CFG, LINE)
    assert set(int(k) for k in graph.node_kind.tolist()) == set(NODE_KINDS)
    for v in range(graph.n_nodes):
        kind = int(graph.node_kind[v])
        for row in rows:
            if kind in row["node_kind_ids"]:
                continue
            start, stop = row["index_range"]
            block = graph.node_x[v, start:stop]
            assert torch.count_nonzero(block) == 0, (
                "node {} of kind {} has non-zero values in {}, which the audit "
                "attributes only to kinds {}".format(v, kind, row["name"], row["node_kind"]))


# ---------------------------------------------------------------------------
# 7. No global pooling operator
# ---------------------------------------------------------------------------
def test_no_global_pooling_operator():
    team = chain_team()
    views = simulate_robot_views(team, CHAIN_OBSTACLES)
    n_robots = len(team)

    max_robot_nodes = 0
    for i, view in views.items():
        for mode in MODES:
            g = build_ego_graph(view, CFG, mode)

            # (a) the graph never exceeds 1 + degree + locally sensed obstacles
            budget = 1 + view.degree + len(view.obstacles)
            assert g.n_nodes <= budget, (
                "G_{} has {} nodes but the local budget is {}".format(i, g.n_nodes, budget))
            assert g.n_nodes == 1 + g.n_neighbour_nodes + g.n_obstacle_nodes

            # (b) every edge is incident to the centre; there is no node-to-node
            # edge, so no message can travel between two non-centre nodes and no
            # graph-wide statistic can be formed inside G_i.
            src = g.edge_index[0].tolist()
            dst = g.edge_index[1].tolist()
            assert all((s == g.center_index) != (d == g.center_index)
                       for s, d in zip(src, dst))
            assert g.n_edges == 2 * (g.n_nodes - 1)

            # (c) the far obstacle at (30, 30) is in no one's graph
            assert g.n_obstacle_nodes <= len(view.obstacles) <= len(CHAIN_OBSTACLES) - 1

            max_robot_nodes = max(max_robot_nodes, g.n_robot_nodes)

    # (d) two robots are out of range of robot 0, so no ego graph in this team
    # contains all N robots -- an all-reduce over the team is not expressible.
    assert max_robot_nodes < n_robots, (
        "some ego graph held all {} robots; the fixture is not partially "
        "connected".format(n_robots))
    out_of_range_pairs = [(i, j) for i in range(n_robots) for j in range(i + 1, n_robots)
                          if math.dist(team[i].position, team[j].position) > COMM.r_comm]
    assert len(out_of_range_pairs) >= 2


# ---------------------------------------------------------------------------
# 8. Joint-state inputs are rejected
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real_env_obs():
    from rvt_swarm.environment import SwarmFormationEnv
    from rvt_swarm.layouts import build_layouts

    cfg = Config()
    cfg.train.device = "cpu"
    cfg.env.scenarios = ["cluttered"]
    env = SwarmFormationEnv(cfg)
    layout = [l for l in build_layouts("val") if l.family == "line_corridor"][0]
    obs = env.reset(4, "cluttered", seed=20000001, layout=layout)
    return cfg, obs


def test_joint_state_inputs_are_rejected(real_env_obs):
    _cfg, obs = real_env_obs
    positions = np.asarray(obs["positions"], dtype=np.float32)
    assert positions.shape == (4, 2)

    with pytest.raises((TypeError, CentralizedAccessError)):
        build_ego_graph(obs, CFG, LINE)                      # the raw obs dict
    with pytest.raises((TypeError, CentralizedAccessError)):
        build_ego_graph(positions, CFG, LINE)                # (N, 2) joint state
    with pytest.raises((TypeError, CentralizedAccessError)):
        build_ego_graph(torch.from_numpy(positions), CFG, LINE)
    with pytest.raises((TypeError, CentralizedAccessError)):
        build_ego_graph(list(simulate_robot_views(chain_team()).values()), CFG, LINE)
    with pytest.raises((TypeError, CentralizedAccessError)):
        build_ego_graph({"positions": positions}, CFG, LINE)
    with pytest.raises((TypeError, CentralizedAccessError)):
        build_ego_graph(None, CFG, LINE)

    # The error names the violation rather than failing incidentally.
    with pytest.raises(CentralizedAccessError) as excinfo:
        build_ego_graph(obs, CFG, LINE)
    assert "RobotView" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Supporting: the builder runs on views taken from a real environment
# ---------------------------------------------------------------------------
def test_builds_on_real_environment_views(real_env_obs):
    cfg, obs = real_env_obs
    roles = RoleAssignment.from_index(4, spacing=cfg.env.nominal_spacing)
    views = simulate_robot_views_from_obs(obs, roles, cfg.env.obstacle_radius)
    assert len(views) == 4

    n_world_obstacles = len(np.asarray(obs["obstacles"]).reshape(-1, 2))
    for i, view in views.items():
        for mode in MODES:
            g = build_ego_graph(view, CFG, mode)
            assert g.node_x.shape == (g.n_nodes, FEATURE_DIM)
            assert g.edge_attr.shape == (g.n_edges, EDGE_DIM)
            assert g.node_x.dtype == torch.float32
            assert torch.isfinite(g.node_x).all() and torch.isfinite(g.edge_attr).all()
            assert int(g.node_kind[0]) == NODE_SELF
            assert torch.count_nonzero(g.node_x[0, 0:2]) == 0     # self rel_position is (0, 0)
            assert g.n_obstacle_nodes <= n_world_obstacles
            assert float(MODEL(g)) == float(MODEL(g))
        # sensing is a strict gate, not a copy of the world obstacle list
        assert len(view.obstacles) <= n_world_obstacles


# ---------------------------------------------------------------------------
# Supporting: the candidate mode really conditions the graph
# ---------------------------------------------------------------------------
def test_candidate_mode_conditions_role_block_and_query_flag():
    """`role_candidate` must hold the role for the CANDIDATE tau, not a fixed
    mode. Without this the two candidate graphs would differ only by the query
    one-hot and the scorer would be blind to the line template."""
    from rvt_swarm.decentralized.ego_graph import FEATURE_SLICES

    view = simulate_robot_views(star_team(), STAR_OBSTACLES)[0]
    assert view.role_keep != view.role_line, "fixture broken: roles coincide"

    g_keep = build_ego_graph(view, CFG, KEEP)
    g_line = build_ego_graph(view, CFG, LINE)
    role = FEATURE_SLICES["role_candidate"]
    query = FEATURE_SLICES["candidate_mode_onehot"]

    assert not torch.equal(g_keep.node_x[0, role], g_line.node_x[0, role]), (
        "self role block is identical for both candidates")
    assert not torch.equal(g_keep.node_x[:, role], g_line.node_x[:, role]), (
        "neighbour role blocks are identical for both candidates")
    assert not torch.equal(g_keep.node_x[0, query], g_line.node_x[0, query])
    assert g_keep.candidate_mode == KEEP and g_line.candidate_mode == LINE

    # The role block matches the view's own role table for the queried mode.
    assert g_keep.node_x[0, role].tolist() == pytest.approx(list(view.role_keep))
    assert g_line.node_x[0, role].tolist() == pytest.approx(list(view.role_line))
    for v, nb in zip(range(1, 1 + view.degree), view.neighbours):
        assert g_keep.node_x[v, role].tolist() == pytest.approx(list(nb.role_keep))
        assert g_line.node_x[v, role].tolist() == pytest.approx(list(nb.role_line))


# ---------------------------------------------------------------------------
# Supporting: the admission rule the documents claim is the one that runs
# ---------------------------------------------------------------------------
def test_stale_and_dead_links_produce_no_node():
    from rvt_swarm.decentralized.ego_graph import FEATURE_SLICES

    fresh = simulate_robot_views(star_team(), STAR_OBSTACLES)[0]
    assert fresh.degree == 3

    # A record older than delta_stale_steps is excluded from N_i entirely.
    stale = replace(fresh, neighbours=tuple(
        replace(nb, message_age_steps=COMM.delta_stale_steps + 1) if k == 0 else nb
        for k, nb in enumerate(fresh.neighbours)))
    # A record whose link is down is excluded as well.
    dead = replace(fresh, neighbours=tuple(
        replace(nb, link_valid=False) if k == 1 else nb
        for k, nb in enumerate(fresh.neighbours)))
    # A record at exactly delta_stale_steps is still admitted (boundary is <=).
    boundary = replace(fresh, neighbours=tuple(
        replace(nb, message_age_steps=COMM.delta_stale_steps) if k == 0 else nb
        for k, nb in enumerate(fresh.neighbours)))

    g_fresh = build_ego_graph(fresh, CFG, LINE)
    assert build_ego_graph(stale, CFG, LINE).n_neighbour_nodes == g_fresh.n_neighbour_nodes - 1
    assert build_ego_graph(dead, CFG, LINE).n_neighbour_nodes == g_fresh.n_neighbour_nodes - 1
    assert build_ego_graph(boundary, CFG, LINE).n_neighbour_nodes == g_fresh.n_neighbour_nodes

    # The two constant-by-construction flags are exactly 1.0 on admitted nodes,
    # as the audit document states, and the age column is normalised into [0, 1].
    g = build_ego_graph(boundary, CFG, LINE)
    for v in range(g.n_nodes):
        kind = int(g.node_kind[v])
        if kind == NODE_NEIGHBOUR:
            assert float(g.node_x[v, FEATURE_SLICES["nb_link_valid"]]) == 1.0
            age = float(g.node_x[v, FEATURE_SLICES["nb_message_age_norm"]])
            assert 0.0 <= age <= 1.0
        elif kind == NODE_OBSTACLE:
            assert float(g.node_x[v, FEATURE_SLICES["obs_valid"]]) == 1.0

    # The r_obs gate inside the builder is defence in depth: the boundary
    # already filters, so this hands the builder an obstacle it should refuse
    # anyway. Without this case the gate is unreachable in tests.
    far = replace(fresh, obstacles=tuple(fresh.obstacles) + ((COMM.r_obs + 5.0, 0.0, 0.35),))
    assert len(far.obstacles) == len(fresh.obstacles) + 1
    assert (build_ego_graph(far, CFG, LINE).n_obstacle_nodes
            == build_ego_graph(fresh, CFG, LINE).n_obstacle_nodes)
    # ... and an obstacle just inside the gate IS admitted, so the gate is not
    # simply rejecting everything.
    near = replace(fresh, obstacles=tuple(fresh.obstacles) + ((COMM.r_obs - 0.5, 0.0, 0.35),))
    assert (build_ego_graph(near, CFG, LINE).n_obstacle_nodes
            == build_ego_graph(fresh, CFG, LINE).n_obstacle_nodes + 1)

    # split (mode 1) is removed and must not be silently accepted.
    with pytest.raises(ValueError):
        build_ego_graph(fresh, CFG, 1)


# ---------------------------------------------------------------------------
# Supporting: the audit document is generated from the code and has not drifted
# ---------------------------------------------------------------------------
def test_audit_document_matches_code():
    import pathlib

    doc = pathlib.Path(__file__).resolve().parents[1] / "docs" / "EGO_GRAPH_FEATURE_AUDIT.md"
    assert doc.exists(), "missing {}".format(doc)
    text = doc.read_text()
    assert audit_markdown() in text, (
        "docs/EGO_GRAPH_FEATURE_AUDIT.md has drifted from feature_audit(); "
        "regenerate it from audit_markdown()")
