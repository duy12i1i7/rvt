# Recovery Trigger Delay Decomposition (Task 6R-3)

One episode, one trace: `results/recovery_timing_repair/golden_episode_trace.jsonl`
(cell α 0.35, h = 0.865, seed 0, 180 steps). The detector and the deployable
trigger were evaluated **on the same `RobotView` objects, inside the same
episode loop**. Neither re-ran the environment; neither read simulator obstacle
arrays.

---

## 1. Event steps (robot 4, the first to obtain evidence)

| event | step |
|---|---|
| K→L commit | 30 |
| **first raw forward-opening evidence while in LINE** | **44** |
| persistence streak reaches `L_TRIGGER = 3` | 46 |
| **first `recovery_armable` = True** | **46** |
| …and armable **continuously** thereafter (47, 48, 49, …) | — |
| **L→K commit** | **111** |

## 2. Decomposition — sums exactly

```
observed  commit − first valid evidence  = 111 − 44 = 67 steps

  sensor / detector delay                        =  0
  persistence delay (L_TRIGGER = 3)              =  2
  peer-support delay                             =  0   (support 1.0 throughout)
  lifecycle-gating delay                         =  0   (latch INSIDE from step 31,
                                                         recovery_allowed from 31,
                                                         locked = 0 from step 41)
  trigger-collection delay                       =  0
  propagation / score / confirm / commit delay   =  0
  PROPOSAL DEFECT                                = 65
  ------------------------------------------------------
  total                                          = 67   ✓ EXACT
```

**65 of 67 steps are a single defect.** Everything else contributes 2.

## 3. The defect

The robot armed a RECOVERY epoch at step 46 on valid forward-opening evidence.
The *proposal* was then re-derived from a different signal —
`nearest_obstacle_clearance` — which at that moment read **0.872 m**, below the
1.8 m threshold, so the robot proposed **LINE**: the mode it already held.

The no-op guard correctly discarded the epoch. This repeated **25 times**, once
per armable step, until the lagging clearance signal finally crossed its
threshold near step 111.

```
step  46 armable=1 fwd_obst=0 nearest_clearance=0.872 -> proposal = LINE   noop
step  47 armable=1 fwd_obst=0 nearest_clearance=0.879 -> proposal = LINE   noop
step  48 armable=1 fwd_obst=0 nearest_clearance=0.886 -> proposal = LINE   noop
   ...
```

The trigger and the proposal were answering different questions with different
evidence. The trigger asked "is the passage ending ahead of me?" (yes, at 44).
The proposal asked "am I in open space?" (no, still between the walls).

## 4. Answers to the Task 6R-4 checklist

| candidate | present? |
|---|---|
| recovery detection evaluated only after physical exit | **no** — evidence at 44, physical exit at 69 |
| recovery detection disabled during LINE commitment | **no** — `locked = 0` from step 41 |
| commitment duration exceeding available lead | **no** — `h_commit = 10`, released at 41 |
| persistence reset by obstacle flicker | **no** — streak rose 1,2,3,…,14 without a reset |
| **using the current mode proposal instead of the requested next mode** | **YES — the entire residual delay** |
| lifecycle requiring crossing before enabling the detector | **no** — latch INSIDE from step 31 |
| coordinate-frame defect | **no** — detector and audit share one function and one frame |
