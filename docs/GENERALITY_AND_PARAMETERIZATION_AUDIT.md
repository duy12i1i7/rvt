# Generality and Parameterization Audit

Scope: every numeric literal in **deployable** runtime code — i.e. every module
in `rvt_swarm/decentralized/` except those registered in
`guards.OFFLINE_MODULES` (`env_geometry`, `qualification_fixtures`,
`formation_metric_v3`, `reconfiguration_metrics`, `training`, `comm_cost`) and
except `simulate_`-prefixed boundary functions.

---

## 1. Verdict

> ### **STOP. Four unexplained runtime magic numbers affect mode selection, and one communication constant is provably incorrect for the declared topology.**

The contract's stop condition is met, so Tasks 6S-1 … 6S-10 are **not** started.

## 2. The blocking findings

### B1 — `FORWARD_SECTOR_HALF_WIDTH = 1.2` (`epoch.py:1405`) — mode selection

Gates `forward_opening_evidence`, which is the entire RECOVERY event. Its own
comment claims it is "the line formation's lateral extent (0 m) plus the
robot-obstacle threshold" — that quantity is **0.550 m**, not 1.2. Checked
against every plausible derivation:

| candidate | value | matches 1.2? |
|---|---|---|
| line lateral/2 + `min_ro` | 0.550 | no |
| `nominal_spacing` | 0.900 | no |
| `2 × min_ro` | 1.100 | no |
| `robot_radius + min_ro` | 0.730 | no |
| `h_keep` (required keep half-separation) | 1.450 | no |

**Classification: 7 — unexplained magic number.** The documented rationale is
also factually wrong, which is worse than an undocumented constant.

### B2 — `PEER_SUPPORT_FRACTION = 0.5` (`epoch.py`) — mode selection

No derivation given. Determines whether a robot may arm a RECOVERY event.
**Classification: 7.**

### B3 — `REARM_OPEN_STEPS = 25` (`epoch.py:139`) — mode selection

Comment says only "long enough that the tail of one passage cannot re-arm the
entry trigger for the same passage" — no quantity is computed from passage
length, speed or formation extent. **Classification: 7.**

### B4 — `2.0 × nominal_spacing` (`runtime.py:92`) — mode selection

The factor 2.0 in the geometric proposal's clearance test. Undocumented and not
derived. It also duplicates, with a different value, the threshold logic in
`TriggerThresholds`. **Classification: 7.**

### B5 — `k_trigger = 4` (`system_model.py:144`) — communication, **correctness**

Not merely unexplained: **provably insufficient** for the declared team size.
A connected N-robot chain has diameter N−1, so:

| N | chain diameter | covered by `k_trigger = 4`? |
|---|---|---|
| 4 | 3 | yes |
| 5 | 4 | yes |
| **6** | **5** | **NO** |
| 7 | 6 | no |

At N = 6 an originator at one end of a chain reaches five of six robots. This is
the finding already recorded in the Task 6RR follow-up and raised by Task 6S-7.
It does not bind in the *current* fixtures (measured degree 5 of 5 — the graph is
complete), but the deployable claim as written is unsound.

## 3. Full classification of non-trivial runtime literals

| literal | location | classification | source | derived? | limitation |
|---|---|---|---|---|---|
| `1.2` forward sector | `epoch.py:1405` | **7 unexplained** | none | no | **B1** |
| `0.5` peer support | `epoch.py` | **7 unexplained** | none | no | **B2** |
| `25` rearm steps | `epoch.py:139` | **7 unexplained** | none | no | **B3** |
| `2.0×spacing` | `runtime.py:92` | **7 unexplained** | none | no | **B4** |
| `k_trigger=4` | `system_model.py:144` | **4 protocol, INCORRECT** | none | no | **B5** |
| `L_TRIGGER=3` | `epoch.py:1411` | 5 experimentally selected | measured lead ≥ 8.6 steps | partly | value itself is a choice |
| `recovery_clearance_m = 2.0×spacing` | `epoch.py` | 5 experimentally selected | — | partly | `h_keep = 1.45` would be the derived value; 1.8 is not it |
| `clearance_m = max(spacing, min_ro)` | `epoch.py` | 2 physical | `EnvConfig` | **yes** | — |
| `progress_m = 0.135` | `epoch.py` | 3 mission | `max_speed×dt×5×0.2` | **yes** | the 0.2 fraction is a choice |
| `h_commit = 10` | `system_model.py:138` | 4 protocol | matches `recovery_v2.rollout` | **yes** | — |
| `k_score = k_confirm = 4` | `system_model.py:144` | 4 protocol | — | no | same diameter argument as B5 |
| `r_comm = 3.0` | `system_model.py:54` | 4 protocol | documented vs N=6 line span 4.5 m | **yes** | tied to N=6 |
| `r_obs = 3.0` | `system_model.py:64` | 2 physical | `lidar_range` | **yes** | — |
| `r_sense = 4.0` | `system_model.py:60` | 2 physical | `sensing_radius` | **yes** | — |
| `delta_stale_steps = 3` | `system_model.py` | 4 protocol | 0.45 s = 0.405 m at `max_speed` | **yes** | — |
| `t_comm = t_ctrl = 0.15` | `system_model.py:74` | 2 physical | `EnvConfig.dt` | **yes** | — |
| `decision_interval = 25` | `system_model.py:139` | 4 protocol | — | no | now unused for triggering |
| 49/21/20/16 byte counts | `comms.py`, `epoch.py:175-177` | 2 physical | `struct` wire schema | **yes** | verified by `assert_schema_sizes` |
| `65535`, `4294967295`, `255` | `comms.py`, `epoch.py` | 1 mathematical | field-width masks | **yes** | — |
| `1e-9`, `1e-6` | several | 1 mathematical | numerical guards | **yes** | — |
| `hidden=96`, `passes=3`, `0.2` | `models.py` | 5 hyperparameter | architecture | no | learned-model only; no selector trained |

## 4. What is algorithmically general

**Formation templates and the role protocol are genuinely general.** Built and
checked at N = 3, 4, 5, 6, 7, 8, 10 — every template constructs, and the
KEEP/LINE disjointness certificate evaluates:

| N | `delta_N` | disjoint (`> 2ε = 1.10`) |
|---|---|---|
| 3 | 0.6708 | **no** |
| 4 | 1.0062 | **no** |
| 5 | 1.6100 | yes |
| 6 | 2.0125 | yes |
| 7 | 2.1970 | yes |
| 8 | 2.4903 | yes |
| 10 | 3.5296 | yes |

There is **no hard-coded team size, robot ID, corridor coordinate, map
coordinate, transition step, exit-plane coordinate or seed** in any deployable
path. The `6` literals the scan flagged are all in comments or docstrings.
Algorithmic support is therefore N ≥ 5; **experimentally validated scope is
N = 6 only**, and those two are already separate.

## 5. What is configuration-dependent, and what is not yet

Already in typed immutable config objects: `CommParams`, `ConsensusParams`,
`TriggerThresholds`, `LocalGains`, `RuntimeFlags` — all frozen dataclasses.

**Not yet parameterized:** B1–B4 are module-level constants in `epoch.py` and a
literal in `runtime.py`, not fields of any config object. Moving them is
necessary but **not sufficient** — the contract is explicit that relocating a
value into a config file does not make it explained.

## 6. Normalized ratios

Reported alongside absolute SI values, at N = 6:

| ratio | value |
|---|---|
| `sensor_range_ratio = R_obs / spacing` | 3.0 / 0.9 = **3.33** |
| `communication_range_ratio = R_comm / spacing` | 3.0 / 0.9 = **3.33** |
| `corridor_width_ratio = free_width / required_keep_width` (α 0.25 / 0.35 / 0.45) | 1.550/2.900 = **0.534**, 1.730/2.900 = **0.597**, 1.910/2.900 = **0.659** |
| `recovery_length_ratio` | reported per fixture in the geometry contract |

## 7. Defensible claims for the paper

**Defensible:** the runtime is fully decentralized and leaderless (0 guard
violations, no exit plane, no centroid, no coordinator, each robot computes only
its own action); the role/template machinery is general in N with an explicit
supported-configuration check; message schemas are byte-exact and verified.

**Not defensible as written:** any claim of parameter-independence or of
finite-time agreement on arbitrary connected graphs. B5 makes the latter false
as configured, and B1–B4 mean the recovery event's sensitivity is uncharacterised.

## 8. Required before Task 6S resumes

1. Derive or predeclare B1–B4 with an explicit formula and a sensitivity test
   each, or replace them with derived quantities.
2. Resolve B5 by the Task 6S-7 contract — Option 2 (`k_trigger = N_max − 1`) is
   the graph-theoretic repair, and it is a correctness fix, not tuning.
3. Re-run the audit and confirm zero class-7 literals remain in deployable code.

Only then do the 6S-1 failure attribution and the safe-expansion work become
meaningful, because the α 0.25 failure they investigate is gated by B1 — the
very constant that decides when the recovery event fires.
