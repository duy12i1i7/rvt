# Post-Repair Recovery Delay Decomposition (Task 6RR-2)

Traces from the repaired runtime, strict decentralized mode enabled:
`results/recovery_propagation_latency/alpha_0{25,35,45}_trace.jsonl`
(3 cells × 5 seeds). The pre-repair trace was **not** reused.

---

## 1. Event steps (seed 0, first robot to obtain evidence)

| cell | first raw evidence | persistence satisfied | commit KEEP |
|---|---|---|---|
| α 0.25 | 44 | 46 | **46** |
| α 0.35 | 44 | 46 | **46** |
| α 0.45 | 43 | 45 | **45** |

## 2. Decomposition — sums exactly

```
commit − first raw evidence = 46 − 44 = 2 steps      (α 0.25, α 0.35)
                            = 45 − 43 = 2 steps      (α 0.45)

  local persistence (L_TRIGGER = 3)   = 2
  token collection                    = 0
  token propagation                   = 0   (same control step)
  token adoption                      = 0
  lifecycle eligibility               = 0
  score consensus                     = 0
  confirmation                        = 0
  commitment barrier                  = 0
  other confirmed delay               = 0
  ---------------------------------------
  total                               = 2   ✓ EXACT
```

The protocol itself contributes **zero** steps beyond persistence: trigger
propagation, score consensus and confirmation all complete within the control
step in which the event fires.

## 3. The residual defect that the traces exposed

The traced protocol commits at 45–46. The *deployed* `runtime.py` was committing
at 73–88. The difference was a single line — the **no-op pre-arm check** added
in Task 5-7:

```python
qk, ql = _robot_decision(views[i], cfg, selector, mode_rule)   # lagging signal
own = LINE if ql > qk else KEEP
if own == e.committed_mode:
    fired = False          # arming cancelled
```

This re-introduced the *exact* defect Task 6R repaired, one layer earlier. A
robot with valid forward-opening evidence at step 46 had its arming cancelled
because `nearest_obstacle_clearance` (0.872 m, still between the walls) said
LINE — the mode it already held. The event never reached the epoch machinery at
all, which is why the earlier decomposition attributed nothing to the protocol.

**Repair:** the pre-arm check now uses `requested_mode_for(e)`, the same
event-derived quantity the proposal uses.

## 4. The all-robots-evidence hypothesis (Task 6RR-3)

**Rejected.** In the pre-repair trace, per-robot first evidence was
44, 59, 72, 84, 93, 103 and commitment fell at 111 — i.e. it tracked the **last**
robot. After the repair, commitment occurs at 45–46, before any robot other than
the originator has accumulated evidence at all.

Adopting robots derive `requested_mode = KEEP` from their own lifecycle state
(committed LINE + latch inside the passage ⇒ the only legal transition is to
KEEP). They do **not** reproduce the originator's sensor evidence, and
confirmation does not require them to.
