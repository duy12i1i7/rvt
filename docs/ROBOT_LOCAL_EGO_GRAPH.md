# The robot-local ego graph G_i

Code: `rvt_swarm/decentralized/ego_graph.py`
Evidence: `tests/test_ego_graph_locality.py` (12 tests, all passing)
Feature-by-feature audit: `docs/EGO_GRAPH_FEATURE_AUDIT.md`
Contract: `rvt_swarm/decentralized/system_model.py`

Robot *i* scores a candidate formation mode `tau` from a graph it can build
alone, from its own sensors, its own memory, and the beacons of the robots it
can actually hear. This document states what that graph contains, how it is
wired, why one shared-weight GNN can consume it, and why there is no global
pooling operator anywhere in it.

## 1. Structure

`build_ego_graph(view: RobotView, cfg, mode: int) -> EgoGraph`

The **only** data argument is a `RobotView`. `cfg` supplies constants
(`CommParams`, `ConsensusParams`) and `mode` is the candidate `tau` being
scored. Passing the simulator's obs dict, an `(N, 2)` position array, or a list
of robot states raises `CentralizedAccessError`; passing anything else raises
`TypeError`.

```
EgoGraph
  node_x        (V, 28)  float32     V = 1 + |N_i| + |O_i|
  edge_index    (2, E)   int64       E = 2 * (V - 1)
  edge_attr     (E, 9)   float32
  node_kind     (V,)     int64       0 = self, 1 = robot neighbour, 2 = obstacle
  n_nodes       int
  center_index  int                  always 0
  candidate_mode int                 the tau this graph was built for
  node_source_id tuple                neighbour IDs / -1; NEVER a feature
```

Node order is: robot *i* first, then one node per **admitted** one-hop
neighbour in the order the view lists them, then one node per **locally
observed** obstacle. Order carries no meaning -- see §5.

### Node kinds

| Kind | Node exists when | Source of the row |
| --- | --- | --- |
| 0 `self` | always, exactly one, index 0 | robot i's own state, role, memory |
| 1 `robot_neighbour` | the record's link is up **and** its newest message is at most `delta_stale_steps = 3` control steps old | that neighbour's beacon |
| 2 `obstacle` | the obstacle's clearance from robot i is at most `r_obs = 3.0 m` | robot i's own sensor |

Both admission rules are strict gates, not soft weights: a robot outside
`r_comm = 3.0 m` produces **no node**, and an obstacle outside `r_obs`
produces **no node**. There is no "everything else, summarised" node. This is
the structural reason test 1 holds -- an out-of-range robot has no
representation in `G_i` that its motion could perturb.

`NeighbourRecord` stores `rel_position = p_j - p_i` and
`rel_velocity = v_j - v_i`, so a neighbour's absolute position is never
available to this module in the first place. Robot i's own absolute position
is available (it is permitted `self_state`) but is deliberately **not** a
feature: excluding it makes every geometric column translation-invariant.

### Obstacle geometry

`RobotView.obstacles` entries are ego-relative `(ox, oy, radius)` with
`(ox, oy) = o - p_i`, the same convention `local_controller` uses. The node
carries the vector from `p_i` to the **closest point** of the obstacle disc,
`d * max(1 - radius/norm(d), 0)`, and the clearance `max(norm(d) - radius, 0)`.
The bearing is the unit vector toward the obstacle **centre**, not toward the
closest point, so it stays defined at contact where the clearance vector
vanishes. A 5-tuple `(ox, oy, radius, rel_vx, rel_vy)` is accepted for moving
obstacles; the static obstacles in these layouts use the 3-tuple form and get a
zero relative-velocity block.

## 2. Edge construction

Every non-centre node is connected to the centre in **both** directions, and
nothing else is connected to anything:

```
for k in 1 .. V-1:
    edge (0 -> k)   attr = [ delta,  dist,  cos,  sin, 1, 0, kind_onehot ]
    edge (k -> 0)   attr = [-delta,  dist, -cos, -sin, 0, 1, kind_onehot ]
```

`delta` is the node's ego-relative vector, so the forward/reverse pair is
exactly antisymmetric in the geometry and differs only in the direction
one-hot. `kind_onehot` is `[robot_robot, robot_obstacle]`, taken from the node
kind of the non-centre endpoint, so one message function can serve both edge
types. `E = 2(V-1)` exactly; the locality test asserts this and asserts that
every edge has exactly one endpoint at the centre.

Consequence: there is **no neighbour-to-neighbour edge**. Two of robot i's
neighbours cannot exchange a message inside `G_i`. Any relation between them
that robot i wants must be formed at the centre, from quantities robot i
itself holds. That is a deliberate restriction of expressiveness in exchange
for a checkable locality claim.

Multi-hop information is not obtained by making `G_i` deeper. It is obtained
by the consensus rounds over the real radio (`k_score`, `k_trigger`,
`k_confirm` in `ConsensusParams`), where each hop costs a real message. A
2-hop GNN over a graph built from one-hop data would fake a second hop for
free; the ego graph makes that impossible by construction.

## 3. Features and the shared-weight GNN argument

The three node kinds hold different quantities but are written into **one**
28-column layout with explicit zero blocks
(`FEATURE_LAYOUT`, `FEATURE_SLICES`, and the generated table in
`docs/EGO_GRAPH_FEATURE_AUDIT.md`). Summary:

| Block | Columns | Kinds |
| --- | --- | --- |
| `rel_position`, `distance`, `bearing_cos_sin`, `node_kind_onehot` | 0:8 | all three |
| `rel_velocity` | 8:10 | neighbour, obstacle |
| `role_candidate`, `committed_mode_onehot` | 10:14 | self, neighbour |
| `self_velocity`, `self_goal_rel`, `self_mission_dir`, `self_steps_since_decision`, `self_local_progress`, `candidate_mode_onehot` | 14:24 | self |
| `nb_message_age_norm`, `nb_link_valid` | 24:26 | neighbour |
| `obs_radius`, `obs_valid` | 26:28 | obstacle |

Why one shared weight matrix instead of three per-kind encoders:

1. **A column means the same thing on every kind that uses it.** `rel_position`
   is "where this thing is, relative to me" for a neighbour and for an
   obstacle; `distance` is "how far", `bearing_cos_sin` is "in which
   direction". A shared `W` therefore learns one geometric primitive rather
   than three copies of it, and the sample budget is not split three ways.
2. **Where the meaning would differ, the column does not.** Robot i's own
   velocity lives in `self_velocity`, *not* in `rel_velocity`, because "my
   velocity" and "their velocity minus mine" are different quantities. Reusing
   one slot for both would be the exact kind of silent conflation this design
   is trying to avoid.
3. **The zero blocks are disambiguated by `node_kind_onehot`.** A shared linear
   layer applied to a padded row is equivalent to a per-kind layer plus a
   per-kind bias, because the kind one-hot is in the input; the padding costs
   parameters, not expressiveness.
4. **The claim is tested, not asserted.** For every node in a real graph, every
   column whose audit row does not list that node's kind is asserted to be
   exactly zero
   (`test_every_feature_traces_to_a_permitted_local_source`, part d).

Rotation consistency: bearings are stored as `cos`/`sin`, never as a raw angle.
A raw angle is discontinuous at +-pi and does not transform the same way as the
`rel_position` vector next to it; the unit vector does.

Identity is not a feature: no robot ID, no node index, and no slot number
enters `node_x`. What identifies a neighbour to the network is its **role
coordinate**, which is a mission constant attached to the physical vehicle.
This is what makes relabelling an equivariance (test 5) rather than a
distribution shift.

## 4. The candidate mode `tau`

`G_i` is built once per candidate. The candidate one-hot rides on the centre
node only (`candidate_mode_onehot`), so the score is
`q_i(tau) = f(build_ego_graph(view, cfg, tau))` with the *same* weights for
both candidates, rather than a two-headed output. The neighbours' *committed*
modes are a separate block (`committed_mode_onehot`) on the self and neighbour
nodes: what the neighbourhood is doing now, versus what robot i is currently
scoring. Note that the `role_candidate` block also depends on `tau`, so the two
candidate graphs differ in the role geometry as well as in the query flag --
which is the point: scoring `LINE` should look at the line template.

## 5. Why there is no global pooling

Three independent barriers, in increasing order of strength:

1. **Input.** `build_ego_graph` accepts only a `RobotView`. There is no
   argument through which the joint state could arrive, and dicts / arrays /
   sequences are rejected by name with `CentralizedAccessError` (test 8, driven
   by a real `SwarmFormationEnv` observation).
2. **Node set.** `V = 1 + |N_i| + |O_i|`, and both `N_i` and `O_i` are range
   gated. In the partially connected fixture (four robots on a path, two pairs
   beyond `r_comm`) **no ego graph contains all N robots**, so a swarm-wide
   mean or max is not merely discouraged, it is not expressible: the operands
   are not present (test 7).
3. **Edge set.** Every edge is incident to the centre. The only aggregation a
   consumer can perform is over robot i's own one-hop neighbourhood, which is
   precisely the set robot i can hear. There is no node with degree V-1 other
   than the centre, and the centre is robot i itself.

The readout used by the tests makes the aggregation explicit:

```
h_v   = tanh(node_x[v] @ W_node)                       # shared over all kinds
m_e   = tanh([h_src, h_dst, edge_attr[e]] @ W_msg)     # shared over all edges
q_i   = [h_centre, SUM_{e : dst(e) = centre} m_e] @ W_out
```

The **sum** over centre-incoming edges is what makes the readout invariant to
the order in which neighbours and obstacles happened to be listed (test 4:
permuting the neighbour and obstacle lists changes `node_x` and `edge_index`
but leaves `q_i` unchanged to `1e-12` in float64). A mean over the same set
would be equally acceptable; a mean or max over *all* nodes of the graph would
not be, because it would mix robot i's own features into a pooled statistic
with no local meaning -- and in the multi-robot limit it is the operator that
turns a "local" model into a disguised all-reduce.

## 6. What this design gives up

* No neighbour-to-neighbour relation can be computed inside `G_i`.
* Robot i cannot see the geometry of a gap it has not sensed; a corridor
  narrower than its own sensor footprint is invisible until it is close.
* The two constant-by-construction flags (`nb_link_valid`, `obs_valid`) carry
  no information under the nominal admission rule. They are kept so a
  degraded-link variant has the identical feature width; this is stated in the
  audit rather than hidden.
* The graph is rebuilt per candidate mode, so scoring both modes costs two
  forward passes. That is the price of shared weights across `tau`.

## 7. Test map

| Test | Property |
| --- | --- |
| `test_out_of_range_robot_cannot_change_graph` | moving a robot outside `r_comm` leaves `node_x`, `edge_index`, `edge_attr`, `node_kind` byte-identical; the robot that *did* observe it does change |
| `test_out_of_range_robot_cannot_change_score` | same move leaves `q_i(tau)` exactly equal for both candidates |
| `test_neighbour_removal_affects_only_observers` | dropping robot 3 leaves `G_0`, `G_1` byte-identical and changes `G_2` |
| `test_node_ordering_does_not_change_readout` | permuting neighbours/obstacles permutes the rows but not the sum-aggregated readout |
| `test_id_relabelling_equivariance` | consistent ID+role relabelling is byte-identical; an *inconsistent* role swap is not (non-vacuity) |
| `test_every_feature_traces_to_a_permitted_local_source` | audit tiles all 28 columns, names only permitted sources, and the zero blocks hold on real tensors |
| `test_no_global_pooling_operator` | `V <= 1 + degree + local obstacles`, every edge touches the centre, `E = 2(V-1)`, no graph holds all N robots |
| `test_joint_state_inputs_are_rejected` | obs dict, numpy `(N,2)`, torch `(N,2)`, list of views, and `None` all raise |
| `test_builds_on_real_environment_views` | the builder runs on views manufactured from a real `SwarmFormationEnv` reset |
| `test_candidate_mode_conditions_role_block_and_query_flag` | `role_candidate` holds the role for the queried `tau`, not a fixed mode |
| `test_stale_and_dead_links_produce_no_node` | stale / dead-link neighbours and out-of-`r_obs` obstacles produce no node; the boundary cases (`age == delta_stale_steps`, clearance just inside `r_obs`) are still admitted |
| `test_audit_document_matches_code` | `docs/EGO_GRAPH_FEATURE_AUDIT.md` has not drifted from `feature_audit()` |

The suite was checked against six deliberate mutations of `ego_graph.py`, each
of which must break at least one test: leaking the node index into an
obstacle-only column, adding a neighbour-to-neighbour edge, deleting the
joint-state input guard, deleting the `r_obs` gate, ignoring `tau` when picking
the role coordinate, and writing robot i's absolute position into the self
node. The first four were caught immediately; the last two initially survived
and the two supporting tests above were added to catch them.

The simulated radio+sensor boundary used by those tests
(`simulate_robot_views`, `simulate_robot_views_from_obs`) lives in the test
file, is prefixed `simulate_`, is documented as non-deployable, and is the only
place the joint state is read. Nothing in `rvt_swarm/decentralized/` imports
it.
