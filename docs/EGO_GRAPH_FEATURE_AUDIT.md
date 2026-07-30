# Ego-graph feature audit

Machine-readable source: `rvt_swarm.decentralized.ego_graph.feature_audit()`.
This file is **generated** by `scripts/generate_ego_graph_audit_doc.py`; the
table below is the exact output of `ego_graph.audit_markdown()`, and
`tests/test_ego_graph_locality.py::test_audit_document_matches_code` fails if
the two drift apart. Do not hand-edit the table.

Every row states which columns of `node_x` it owns, which node kinds carry a
non-zero value there, and which entry of
`system_model.PERMITTED_LOCAL_SOURCES` the number comes from. The audit tiles
`[0, 28)` exactly: no column is unattributed and no two rows claim
the same column
(`tests/test_ego_graph_locality.py::test_every_feature_traces_to_a_permitted_local_source`
asserts both, and additionally checks the zero-block claim on real tensors --
for a node of kind k, every column whose row does not list k is exactly zero).

* `FEATURE_DIM` = 28
* `EDGE_DIM` = 9
* permitted sources actually used: `committed_mode`, `local_memory`, `local_obstacles`, `model_parameters`, `one_hop_messages`, `self_id_and_role`, `self_state`, `shared_frame`, `shared_goal`
* permitted sources deliberately unused by the feature builder: `controller_parameters`

## Node feature table

| Columns | Feature | Node kinds | Permitted source | Justification |
| --- | --- | --- | --- | --- |
| `[0:2]` | `rel_position` | self, robot_neighbour, obstacle | `self_state`, `one_hop_messages`, `local_obstacles` | Position of the node relative to p_i. Self is exactly (0, 0); a neighbour is p_j - p_i straight out of NeighbourRecord; an obstacle is the vector from p_i to the closest point of its disc. No absolute position of any robot -- including robot i -- ever enters node_x, so the whole block is translation-invariant. |
| `[2:3]` | `distance` | self, robot_neighbour, obstacle | `self_state`, `one_hop_messages`, `local_obstacles` | Range to the node: 0 for self, norm(p_j - p_i) for a neighbour, and the clearance max(norm(o - p_i) - radius, 0) for an obstacle. Pairwise range to one observed entity; not a min/mean over the swarm or over the obstacle field. |
| `[3:5]` | `bearing_cos_sin` | self, robot_neighbour, obstacle | `self_state`, `one_hop_messages`, `local_obstacles` | Unit vector toward the node (toward the obstacle *centre* for obstacles, so the bearing stays defined at contact where the clearance vector vanishes). Encoded as cos/sin rather than a raw angle so it is continuous at +-pi and rotates consistently with rel_position. Zero for self, whose bearing is undefined. |
| `[5:8]` | `node_kind_onehot` | self, robot_neighbour, obstacle | `self_state`, `one_hop_messages`, `local_obstacles` | One-hot [self, robot_neighbour, obstacle]. Lets one shared-weight encoder disambiguate the zero blocks of the three node kinds without three separate weight matrices. |
| `[8:10]` | `rel_velocity` | robot_neighbour, obstacle | `one_hop_messages`, `local_obstacles` | Velocity of the node relative to robot i: v_j - v_i from the neighbour beacon, or the obstacle's relative velocity (zeros for the static obstacles used here). Self is a zero block -- its own velocity has its own column block, because 'my velocity' and 'their velocity minus mine' are different quantities and must not share a slot. |
| `[10:12]` | `role_candidate` | self, robot_neighbour | `self_id_and_role`, `one_hop_messages` | Template-frame role coordinate for the CANDIDATE mode tau: robot i's own role for the self node, the neighbour's communicated role for a neighbour node. Roles are mission constants fixed before t=0, not a runtime assignment service. The pairwise desired offset d_ij = R(psi)(r_j - r_i) is recoverable by the network from this block plus self_mission_dir, so no centroid-referenced target is needed. |
| `[12:14]` | `committed_mode_onehot` | self, robot_neighbour | `committed_mode`, `one_hop_messages` | Currently committed mode as a one-hot over (KEEP, LINE): robot i's own commitment from local memory, a neighbour's from its beacon. This is the *neighbourhood's* commitment state, never a swarm-wide tally. |
| `[14:16]` | `self_velocity` | self | `self_state` | Robot i's own velocity in the shared frame. Own state, permitted without qualification. |
| `[16:18]` | `self_goal_rel` | self | `shared_goal`, `self_state` | goal - p_i. The goal is a shared mission constant loaded identically on every robot; subtracting robot i's own position needs no one else's state. Replaces the centralized 'goal - centroid' progress direction. |
| `[18:20]` | `self_mission_dir` | self | `shared_frame` | Unit mission/corridor direction (corridor_dx, corridor_dy), a shared mission constant. Required to interpret template-frame role coordinates in the world frame via R(psi_mission); identical on every robot, so no agreement protocol is involved. |
| `[20:21]` | `self_steps_since_decision` | self | `local_memory` | Control steps since robot i's last decision epoch, divided by ConsensusParams.decision_interval. Robot i's own epoch counter; no global clock and no synchronisation barrier is assumed beyond the shared control period already stated in CommParams. |
| `[21:22]` | `self_local_progress` | self | `local_memory` | Robot i's own progress estimate along the mission direction, from its own odometry and the shared goal. Explicitly NOT obs['progress'], which is computed from the swarm centroid and is prohibited. |
| `[22:24]` | `candidate_mode_onehot` | self | `model_parameters` | One-hot of the candidate mode tau being scored. G_i is built once per candidate, so the score head is q_i(tau) = f(G_i(tau)) with shared weights across tau rather than a two-headed output; the flag is a query, not an observation, and lives on the centre node only. |
| `[24:25]` | `nb_message_age_norm` | robot_neighbour | `one_hop_messages` | Age of the newest message from this neighbour, divided by CommParams.delta_stale_steps. Tells the encoder how much to trust a record under delay/loss. Records older than delta_stale_steps are not admitted at all, so the value lies in [0, 1]. |
| `[25:26]` | `nb_link_valid` | robot_neighbour | `one_hop_messages` | Link-validity flag for the neighbour record. Under the nominal admission rule (link up AND age <= delta_stale_steps) every admitted node carries 1.0; the column is retained so a degraded-link variant that admits stale records with a 0.0 flag has the identical feature width and can load the same weights. Constant-by-construction here and asserted as such by the locality tests. |
| `[26:27]` | `obs_radius` | obstacle | `local_obstacles` | Radius of the sensed obstacle, so the encoder can separate the clearance from the object size. Per-obstacle, from robot i's own sensor. |
| `[27:28]` | `obs_valid` | obstacle | `local_obstacles` | Observation-validity flag for the obstacle record, mirroring nb_link_valid: constant 1.0 under the nominal rule (only obstacles within CommParams.r_obs are admitted), retained so a variant that carries decayed observations keeps the same feature width. |

## Edge attribute table

Edges exist only between the centre and another node, in both directions.

| Columns | Attribute | Justification |
| --- | --- | --- |
| `[0:2]` | `delta` | Position of the destination node relative to the source node, in the shared frame. For a centre->node edge this is the node's rel_position; for the node->centre edge it is its negation, so the pair is exactly antisymmetric. |
| `[2:3]` | `distance` | Range along the edge, identical in both directions. |
| `[3:5]` | `bearing_cos_sin` | Unit vector along the edge, negated on the reverse edge. cos/sin rather than a raw angle. |
| `[5:7]` | `direction_onehot` | [centre_to_node, node_to_centre]. Lets one shared message function distinguish the two directions without duplicating weights. |
| `[7:9]` | `edge_kind_onehot` | [robot_robot, robot_obstacle], taken from the node kind of the non-centre endpoint. |

## What is *not* in the features, and what replaced it

Each row is a quantity that a centralized selector would use and that this
design refuses. `ego_graph.REJECTED_GLOBAL_FEATURES` is the machine-readable
form of this table.

| Rejected feature | Why, and what replaced it |
| --- | --- |
| `swarm_centroid` | Rejected: requires every robot's position. Replaced by rel_position on one-hop neighbour nodes plus the pairwise role difference, which reproduces the centroid-referenced formation target exactly when N_i is the whole team (see local_controller docstring). |
| `global_formation_error` | Rejected: obs['formation_error'] is centroid-derived. Replaced by the per-neighbour residual the encoder can form from rel_position and role_candidate, aggregated only over robot i's own neighbours. |
| `graph_wide_mean_or_max_pooling` | Rejected: an all-node readout is a disguised all-reduce. Replaced by aggregation over edges incident to the centre only; G_i contains no node that is adjacent to every robot in the team. |
| `global_min_clearance` | Rejected: a min over every robot-obstacle pair in the world. Replaced by the per-obstacle `distance` column on locally sensed obstacle nodes; the min over robot i's OWN obstacle nodes is a local quantity and is left for the encoder to form. |
| `global_bottleneck` | Rejected: obs['bottleneck'] is computed from the joint state. Replaced by the local obstacle node set: the gap geometry robot i can actually see, which is what it can actually react to. |
| `global_obstacle_centroid` | Rejected: an average over the whole obstacle field, unbounded by sensor range. Replaced by one node per obstacle within r_obs; no summary statistic over unobserved obstacles exists. |
| `out_of_range_robot_state` | Rejected: any robot beyond r_comm. No node is created for it, so its motion cannot change a single byte of G_i -- asserted directly by test_out_of_range_robot_cannot_change_graph. |
| `team_progress` | Rejected: obs['progress'] tracks the centroid along the corridor. Replaced by self_local_progress, robot i's own progress from its own odometry and the shared goal. |
| `topology_switch_counter` | Rejected: obs['topology_switches'] counts team-level mode changes. Replaced by committed_mode_onehot on the centre and its neighbours plus self_steps_since_decision, all robot-local memory. |
| `robot_id_as_feature` | Rejected: not global, but it would break relabelling equivariance and would let the network memorise slot identity. Replaced by role_candidate, which travels with the physical robot. |

## Two features that are constant by construction

`nb_link_valid` and `obs_valid` are 1.0 on every admitted node under the
nominal admission rule, because a record that fails the rule produces no node
at all. They are kept as explicit columns so that a degraded-link variant --
one that admits a stale record with the flag set to 0.0 instead of dropping it
-- has the identical feature width and can load the same weights. This is
stated rather than hidden: they carry no information in the nominal
configuration, and `test_stale_and_dead_links_produce_no_node` asserts exactly
that.

## Sources that exist in the contract but are not used here

Permitted sources that do not appear in `node_x`: `controller_parameters`.
`controller_parameters` belongs to `local_controller`, not to the graph
builder. `self_state` contributes robot i's velocity and the origin of the ego
frame, but robot i's **absolute position is deliberately excluded** even though
it is permitted: leaving it out makes every geometric column
translation-invariant, which is what makes the out-of-range-robot tests
meaningful instead of accidental. Robot IDs are excluded for the analogous
reason -- see `robot_id_as_feature` in the rejected table.
