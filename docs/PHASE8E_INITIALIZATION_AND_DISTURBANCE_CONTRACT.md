# Phase 8E Initialization and Disturbance Contract

## Initial state

For every family, team size and S0-S5 source, persistent roles are generated from
sorted canonical integer robot keys. Initial topology is COMPACT. KEEP is
prohibited; no frozen v1 layout declares the narrow-start LINE exception.

Nominal role pose is

`p_i = start_center_meters + R(mission_heading) * compact_role_offset_i`.

The initial-condition seed is the existing source-job
`seeds.initial_condition`. Draws use
`sha256-canonical-counter-uint64/v1`: the first 64 SHA-256 bits of canonical
`[version,seed,process,*counter]`, divided by `2^64`. Draw keys never contain
worker order or an outcome.

| State | Process | Bounds/frame | Draw key | Clipping |
|---|---|---|---|---|
| position | independent component uniform | `[-spacing_margin,+spacing_margin]` m in mission frame | `initial_position,robot_id,axis` | none |
| velocity | independent component uniform | `[-v_max*dt,+v_max*dt]` m/s in mission frame | `initial_velocity,robot_id,axis` | reject if vector norm exceeds `v_max` |
| acceleration | deterministic zero | world frame | none | none |
| controller memory | newly constructed | per robot | none | none |
| protocol | `STABLE_TOPOLOGY`, COMPACT, no intent, epoch count zero | per robot | none | none |
| message state | empty queues/tables, sequence zero | per directed link | none | none |
| dynamic phase | absolute episode time zero | simulator | none | none |
| mission progress | zero at fitted initial topology origin | simulator/local history | none | none |

Position and velocity bounds reuse physical spacing and one-step speed scales;
they are not inherited silently from a mechanical fixture. Draw once. Any
collision, bounds violation, invalid speed, invalid role assignment or nonfinite
state records `INITIALIZATION_INVALID`; the scientific slot is not replaced.

S2 is the sole source-policy initialization specialization: the offline forced
topology interface initializes LINE role targets at time zero without creating a
source-equals-target epoch. This is a diagnostic source policy, not publication
initialization. All other sources begin COMPACT.

## Executable disturbance processes

Disabled processes are explicit and cannot be enabled by a simulator default.

| Process | Source trajectory | Counterfactual | Update/correlation | Seed/snapshot | Matching |
|---|---|---|---|---|---|
| robot acceleration | disabled except S5 | uniform disk, max `0.05*a_max`, before safety projection | every control step, counter-key independent | matched disturbance seed, step and robot | identical vector for paired candidate/replica |
| runtime velocity | disabled | disabled | none | none | exact |
| robot sensing noise | disabled | disabled | none | none | exact |
| obstacle position/velocity noise | disabled | disabled | none | none | exact |
| obstacle observation delay | disabled | disabled | zero | none | exact |
| communication delay/loss | family F8 contract only | same F8 contract | communication tick | communication seed, link sequence and queues | same PRF schedule; physical range may diverge |
| dynamic uncertainty | disabled | disabled | timestamped deterministic path | dynamic snapshot and seed identity | exact |
| S5 acceleration | one robot, uniform disk, max `0.25*a_max` | not added again | one control period at first tick at/after `0.40H` | initial-condition seed, robot selected by seed modulo N | source-only |

Uniform-disk mapping is `r=r_max*sqrt(u_r)`, `theta=2*pi*u_theta`. Generated
accelerations are additive command disturbances before the unchanged safety
projection. Nonfinite or out-of-bound output is typed generation invalid.

Candidate clones carry the seed identity and counter coordinates, not a shared
mutable RNG object. Candidate code therefore cannot advance the other stream.
Snapshot restoration reproduces every vector by key. Job order has no effect.

Rejected alternatives were Gaussian unbounded noise, simulator-default sensor
noise, candidate-specific random streams, resampling invalid starts, and repeated
S5 perturbations until a useful state appears. They violate bounded physical
semantics, matching, or outcome independence.
