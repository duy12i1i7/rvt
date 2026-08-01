# Parameter Semantics Repair — Report and Verdict

Branch `research/parameter-semantics-repair-v1` from tag
`decentralized-generality-audit-v1`. **633 tests pass**, `guards.audit()` **0
violations**. No learned selector; no final-test access; no frozen physical
value altered.

---

## 1. Verdict

> ### **C — The runtime is configuration-driven and mechanically general enough to resume the safe-expansion study.**

All four class-7 constants are replaced by derivations with stated physical
meaning, the propagation-correctness defect is repaired, and an executable
guard now rejects unexplained decision thresholds.

Not A: zero unexplained thresholds remain, enforced by
`test_no_unexplained_runtime_constants.py`, which catches four injected
thresholds and does not cry wolf on legitimate literals.
Not B: propagation correctness is repaired and tested on four topologies.
Not D: the audit and repair are backed by 633 passing tests and 0 guard
violations.

## 2. What each constant meant, and what replaced it

| constant | actual meaning (audited, not assumed) | replacement |
|---|---|---|
| `FORWARD_SECTOR_HALF_WIDTH = 1.2` | lateral band searched ahead for wall material — must cover the region the robot's own KEEP role will occupy | `\|lat(r_i^KEEP) − lat(r_i^LINE)\| + clearance + margin`; **role-dependent**: 0.550 m centre, 1.450 m outer at N=6 |
| `PEER_SUPPORT_FRACTION = 0.5` | three semantics conflated into one number | Option A: no support gate on origination; the three concerns are now separate mechanisms |
| `REARM_OPEN_STEPS = 25` | dwell before the same physical event may re-arm | lifecycle condition + `ceil(rearm_inactive_seconds / T_ctrl)` |
| `2.0 × nominal_spacing` | lookahead distance, conflated with formation pitch | `min(R_obs, v²/2a + v·T_protocol + margin)` = 1.755 m |
| `k_trigger = 4` | **unsound**, not merely unexplained | `D_max = max_team_size − 1 = 5` |

The old 1.2 m under-covered the N = 6 outer roles by **0.25 m** — the α 0.25
premature-expansion mechanism was a magic number, not physics.

## 3. Answers

3. **Which values remain protocol assumptions?** `max_team_size`,
   `max_component_diameter`, `max_message_age_seconds`,
   `evidence_persistence_seconds`, `commitment_seconds`,
   `rearm_inactive_seconds`, `communication_range`, and the connectivity
   assumption. Each is declared in `ProtocolParams` with the correctness
   property it protects. `k_score` remains selected on validation from a
   predeclared grid — a separate, already-declared procedure.
4. **Which time values are now in seconds?** All of them: recovery dwell (3.0),
   persistence (0.45), commitment (1.5), message age (0.45), event collection
   (0.0), re-arm dwell (3.75). Every step count is `ceil(seconds / period)` and
   every one reproduces its frozen value at `T_ctrl = 0.15 s`.
5. **What propagation guarantee is implemented?** Finite-time agreement within
   any component of diameter ≤ `D_max`, under bounded message delay and
   per-epoch internal connectivity. Verified on path, ring, star and complete
   graphs at N = 6. Arbitrary-diameter connected graphs are **not** claimed.
6. **Algorithmically supported team sizes?** N ≥ 5 — templates build and the
   KEEP/LINE disjointness certificate passes (δ_N = 1.610 at N=5 rising to
   3.530 at N=10). N = 3 and N = 4 fail explicitly via `check_team_size`.
7. **Experimentally validated?** **N = 6 only.** The two are separate code
   paths, not a comment.
8. **Any unexplained decision threshold left?** **No** — the G8 guard reports
   zero and is verified non-vacuous in both directions.
9. **What prevents claiming universality?** The diameter bound `D_max`; the
   frozen ε_form = 0.55 m and L_recover = 3.0 s; the point-obstacle sensor
   model; the shared mission frame and shared goal; the single-simulator
   collision model; and validation at N = 6 in one corridor family.

## 4. Repair that went beyond the audit

Extending the diameter argument to `k_confirm` eliminated a **safety** defect a
previous audit had pinned as an accepted limitation: a robot five hops from a
dissenter used to commit while the rest retained. Unsafe commits went **1 → 0**
and overall confirmation correctness **0.9896 → 1.0000** over the same
deterministic 96-outcome grid. Four tests that had encoded the old behaviour
were rewritten to assert the repair.

## 5. Scope honesty

Moving values into a config file does not make them explained, and this report
does not claim it does. Each of the four constants has a stated geometric or
temporal derivation and a sensitivity test; the remaining protocol assumptions
are declared as assumptions, with the correctness property each protects.
Closed-loop success was **not** re-measured and nothing was tuned against it —
that is Task 6S's business, not this repair's.
