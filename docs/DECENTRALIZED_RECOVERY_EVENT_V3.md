# Decentralized Recovery Event V3 (Task 6-2)

## Selected: **OPTION B — FORWARD OPENING EVENT**

Chosen on the Task 6-1 evidence, not by preference.

- **Option A (first local exit) is rejected**: its lead time against the
  known-good command step is **−12.4 and −2.6** steps in two of three
  line-requiring cells. The first robot leaves the passage *after* the moment
  the return must already be commanded.
- **Option B is selected**: lead **+8.6 / +11.0 / +12.2** steps, using only the
  robot's own forward obstacle returns within the already-declared
  `R_obs = 3.0 m`. No sensing assumption is changed.
- **Option C is not needed**: the recovery region is not the binding constraint
  once the event fires early enough.
- **Option D does not apply**: the information *is* available locally.

## Implementation

`epoch.forward_opening_evidence(view, cfg)` — true when no obstacle return lies
in robot i's forward sector (`ox > 0`, `|oy| ≤ 1.2 m`). It inspects
`view.obstacles`, which the simulation boundary has already gated to `r_obs`
around robot i.

**The globally known exit plane is never read.** A robot fires on the
disappearance of its own forward returns — evidence it can obtain while still
inside the passage, which is precisely why the lead time is positive.

Parameters, fixed before the rerun:

| parameter | value | justification |
|---|---|---|
| forward sector half-width | 1.2 m | wider than the line template's lateral extent plus the obstacle threshold, so side walls stay visible until the corridor truly ends |
| `L_TRIGGER` persistence | 3 steps | 0.45 s = 0.405 m of travel, far inside the +8.6-step minimum measured lead, so persistence does not consume the margin |
| peer-support fraction | 0.5 | of one-hop neighbours reporting LINE; an isolated robot returns 1.0 rather than being frozen |
