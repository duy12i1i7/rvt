# Trigger Propagation Contract (Task G6)

## Selected: OPTION A — bounded-diameter configuration

```
D_max      = ProtocolParams.max_component_diameter
             or (max_team_size − 1)        # worst case: a chain
k_trigger  = D_max
k_confirm  = D_max
```

Max-consensus propagates **exactly one hop per round**, so covering a component
of diameter D requires D rounds. At `max_team_size = 6` this gives
`k_trigger = k_confirm = 5`. The integer is derived by
`parameters.derived_k_trigger`; it is never written down.

## What this repairs

`k_trigger = 4` was **unsound for N = 6**, whose worst-case chain diameter is 5:
an originator at one end of a chain reached only five of six robots.

`k_confirm = 4` was worse. A previous audit had already pinned the consequence
as an accepted limitation — on a 6-node path, robot 5 sat five hops from a
dissenter, never witnessed the disagreement, and **committed LINE while robots
0–4 retained**. The claim "confirmation implies agreement" was false whenever
diameter > `k_confirm`. Min/max confirmation propagates one hop per round
exactly as the trigger does, so the same bound applies and the unsafe commit is
now eliminated:

| metric | before | after |
|---|---|---|
| unsafe commits (16 synthetic scenarios, 96 robot-outcomes) | **1** | **0** |
| refuse-when-disagreed | 38/39 = 0.9744 | **39/39 = 1.0000** |
| overall correct decisions | 95/96 = 0.9896 | **96/96 = 1.0000** |

## Assumptions required for correctness

Finite-time agreement is claimed **only** for communication components whose
diameter is at most `D_max`, under bounded message delay
(`max_message_age_seconds`) and per-epoch internal connectivity. A connected
graph of *unknown* diameter with unbounded delay is explicitly **not** claimed.
When the declared bound cannot be guaranteed, `check_team_size` reports the
configuration unsupported.

Tested at N = 6 on path, ring, star and complete graphs: all reach every robot
with a single shared epoch id.

Option B (asynchronous flooding with termination detection) is documented but
not implemented; it would remove the diameter assumption at the cost of a
redesign.
