# Formation Recovery Metric V3

Implementation `rvt_swarm/decentralized/formation_metric_v3.py` ·
Tests `tests/test_formation_recovery_metric_v3.py` (17)

Supersedes the max-over-pairwise metric used in the invalidated Task 4 run
(`docs/TASK4_INVALID_EVALUATION_NOTICE.md`).

---

## 1. Definition

With `c(t) = (1/N) sum_i p_i(t)` and `R(psi_goal)` the shared mission-frame
rotation:

```
e_i^tau(t) = || [p_i(t) - c(t)] - R(psi_goal) r_i^tau ||
E_inf^tau  = max_i  e_i^tau          <- tube membership
E_rms^tau  = sqrt( mean_i (e_i^tau)^2 )   <- descriptive ONLY
```

```
InKeepTube(t)  <=>  E_inf^KEEP(t) <= epsilon_form
InLineTube(t)  <=>  E_inf^LINE(t) <= epsilon_form
NominalKeepRecovered  <=>  InKeepTube holds for >= L_recover consecutive
                           steps after the exit plane is crossed
```

`epsilon_form = 0.55 m`, unchanged from `EnvConfig`. `L_recover = 20` steps
(3.0 s). **Neither was recalibrated using the rerun results**, and no test in
this repair sweeps epsilon.

## 2. Why the old metric was wrong

It used `max over pairs ||(p_j - p_i) - d_ij^tau||` against the same 0.55 m.
A pairwise residual accumulates two robots' deviations, so it is roughly twice
as strict as a per-robot criterion. Measured on one open-field episode with
always-keep, which never leaves the nominal formation:

| criterion | median |
|---|---|
| max-over-pairwise (old) | 0.861 m — **outside** the 0.55 tube |
| `E_inf` per-robot (V3) | 0.435 m — **inside** the 0.55 tube |

The old criterion could not be satisfied by any policy, which is why every arm
scored `keep_recovered = 0.000`.

## 3. Template centring

The evaluator centres the role template (`T - mean(T)`) before comparing.
Necessary because the keep grid does not sum to zero when N does not fill its
rows: at N = 3 the 2×2 grid leaves a hole and the offsets sum to
`(-0.45, +0.45)`, so an exact template would score a non-zero error purely from
that offset.

Centring is a **common translation**, so every pairwise offset `d_ij` is
unchanged and the deployable controller is completely unaffected. It changes
`delta_3` from 0.6364 to 0.6708 and leaves N = 4 and N = 6 untouched (those
templates already sum to zero).

## 4. The centroid, and where it may appear

`c(t)` is computed in this module and nowhere else. This is an offline
evaluator that reads the joint state after the fact — an explicitly permitted
use — and it is registered in `guards.OFFLINE_MODULES`.

`test_08` asserts the deployable controller never receives it: `local_controller`
takes a `RobotView` as its first parameter, contains no `.mean(axis=0)`, and
`runtime.py` does not import this module at all.

## 5. Test evidence

Exact templates score zero for both modes and all N; translation invariance
holds to 1e-9 under dyadic shifts (avoiding float-associativity artefacts);
rotating the mission frame is tracked, and scoring in the wrong frame gives
> 0.5; permuting storage order **together with** the role table leaves the
metric unchanged, while permuting positions alone changes it by > 0.5
(non-vacuity for the invariance claim); a single robot displaced by `d` moves
its own error to `d(1 - 1/N)` and every other robot's to `d/N`, matching the
centroid shift exactly; `E_rms <= E_inf` always; the evaluator is deterministic
over repeated calls; and an AST check confirms the superseded pairwise function
is neither imported nor called.
