# Decentralized Event Protocol V3 — Report and Verdict

Branch `research/decentralized-event-protocol-v3` from tag
`decentralized-reconfiguration-headroom-diagnosis-v1`.
N = 6 · diagnostic policies only · **no learned selector** · **no final-test
layouts** · `epsilon_form` and `L_recover` unchanged · 601 tests pass ·
`guards.audit()` 0 violations.

---

## 1. Verdict

> ### **B — Local recovery evidence IS available, but the event protocol remains mechanically unreliable.**

Task 6-1 settled the observability question decisively in the affirmative, and
that is the phase's main result. The V3 event fires, both transitions occur
exactly once, and crossing reaches 1.00 — but the implemented trigger commands
the return at step **114–124** where the audit predicts **≈ 56**, and full
reconfiguration success remains **0.00**.

Not A: the timing *is* locally observable (§2).
Not C: epoch counts improved and are no longer the binding failure.
Not D: no line-requiring cell achieves full success.
Not E: geometry, metric and guards are validated; the defect is localised to the
trigger's firing time, and it is named rather than hidden (§4).

## 2. Was the recovery timing locally observable? — **Yes, but not by exit detection**

Measured lead against the known-good command step (55):

| cell | h | first local **EXIT** | forward **OPENING** | lead(exit) | lead(opening) |
|---|---|---|---|---|---|
| α 0.25 | 0.775 | 67.4 | 46.4 | **−12.4** | **+8.6** |
| α 0.35 | 0.865 | 57.6 | 44.0 | **−2.6** | **+11.0** |
| α 0.45 | 0.955 | 53.6 | 42.8 | +1.4 | **+12.2** |

**Which robots first obtained valid evidence, and how?** Whichever robot is
foremost in the line at the time — not a designated role. The evidence is
**direct local sensing**: the disappearance of its own forward obstacle returns,
within the already-declared `R_obs = 3.0 m`. No peer message is required, and
none could be earlier, since a front robot's message cannot precede its own
detection.

**Did any runtime path read the global exit plane?** **No.** The V3 event
functions are asserted free of `exit_x` / `exit_plane` / `centroid` / `positions`
by test, and `guards.audit()` reports zero violations.

## 3. What improved

| | Task 5 | V3 |
|---|---|---|
| median epochs per traversal | 8 | **5** |
| successful K→L epochs | 1 | **1** |
| successful L→K epochs | 1 | **1** |
| open-field epochs | 0 | **0** |
| crossing (α 0.35, α 0.45) | 1.00 | **1.00** |

Both transitions now occur exactly once per traversal, and the open-field
control still opens no epochs at all.

## 4. Why the verdict is B — the unresolved discrepancy

The audit says a robot has forward-opening evidence at step ≈ 44. The runtime
commands the return at step **114–124**:

| seed | K→L | L→K | crossing | min `E_inf` after |
|---|---|---|---|---|
| 0 | 30 | **118** | 126 | 0.494 |
| 1 | 30 | **124** | 124 | 0.600 |
| 2 | 30 | **114** | 115 | 0.667 |

The return therefore lands essentially *at* the crossing — exactly the late
timing Task 5 already showed to be insufficient. Two contributions are known and
one is not:

- **Known.** The geometric entry policy commits to LINE at step 30, whereas the
  audit scripted it at step 18. That shifts everything downstream by ~12 steps.
- **Known.** The arming rule adds `L_TRIGGER = 3` steps of persistence.
- **NOT EXPLAINED.** Those two account for ~15 steps, not the ~60 observed. The
  remaining gap between the audit's predicted firing time and the runtime's
  actual firing time is **not diagnosed**, and I did not resolve it within this
  phase.

Reporting an unexplained ~45-step discrepancy is the honest position. Declaring
success on the strength of the audit alone would assert a mechanism the runtime
does not yet demonstrate.

## 5. Answers to the remaining questions

- **Does V3 trigger recovery early enough?** In principle yes (§2); in the
  implemented runtime **no** (§4).
- **Collision-free when recovery begins before the whole swarm exits?** Yes —
  collision-free 1.00 in every V3 cell measured.
- **Did simultaneous triggers coalesce?** Both transitions occur exactly once per
  traversal, so the entry and recovery events each produce a single
  component-wide epoch. Full min-token coalescing (Task 6-4) was **not
  implemented** in this phase.
- **Why did the previous runtime create ~8 epochs?** The entry condition stays
  true for every step inside the corridor, so the trigger refired whenever the
  commitment lock expired. The passage latch, narrowed entry reasons and no-op
  pre-arm check reduced it to 5.
- **New median epoch count?** **5** (predeclared target ≤ 3: still **FAIL**).
- **Under delay and loss?** **Not run.** Task 6-10 is gated on the nominal gates
  passing, and they did not.
- **Still fully decentralized and leaderless?** **Yes** — 0 guard violations, no
  exit-plane or centroid access on any runtime path, no leader or coordinator.

## 6. Gate results

| gate | result |
|---|---|
| **P1** local information validity | **PASS** — 0 guard violations; no runtime exit plane or centroid |
| **P2** positive reconfiguration | **FAIL** — V3 full success 0.00 |
| **P3** scripted reference gap | **FAIL** — 0.00 vs scripted 1.00 |
| **P4** safety | **PASS** — collision-free 1.00, no degradation |
| **P5** open field | **PASS** — 0 epochs, no unnecessary transitions |
| **P6** epoch control | **PARTIAL** — successful epochs exactly 2; median 5 > 3 |
| **P7** communication | reported in §3 and the churn report |
| **P8** infeasible control | **PASS** (carried from Task 5: crossing 0.00) |

## 7. Not done in this phase

Tasks 6-4 (min-token coalescing), 6-5 (full peer-support arming sweep — a single
justified setting was used instead), 6-6 (the ten-state lifecycle as a distinct
type), 6-8 (the complete mechanical qualification set) and 6-10 (delay/loss
sanity check) were **not completed**. The phase stopped once the trigger-timing
discrepancy showed the nominal gates could not pass.

## 8. Required next

1. **Diagnose the ~45-step gap** between the audit's predicted firing time and
   the runtime's actual firing time. Instrument `recovery_armable` per robot per
   step and compare directly against the audit trace on the same seed. This is
   the single blocking item.
2. Only then re-run the qualification set and re-evaluate P2/P3/P6.
