# Local Exit Observability Audit (Task 6-1)

Line-requiring band, N = 6, 5 seeds per cell, scripted K→L→K with the
known-good return at step 55. Raw: `results/local_exit_observability_audit/`

The centroid and the global exit plane appear **only** in this audit. Nothing
here is deployable.

---

## 1. Measured event times

| cell | h | first local **EXIT** | forward **OPENING** | majority exit | last exit | centroid exit (offline) |
|---|---|---|---|---|---|---|
| α 0.25 | 0.775 | 67.4 | **46.4** | 92 | 105 | 87 |
| α 0.35 | 0.865 | 57.6 | **44.0** | 80 | 91 | 77 |
| α 0.45 | 0.955 | 53.6 | **42.8** | 77 | 87 | 73 |

Lead time against the command step that is known to succeed (55):

| cell | Option A lead (first exit) | Option B lead (forward opening) |
|---|---|---|
| α 0.25 | **−12.4** | **+8.6** |
| α 0.35 | **−2.6** | **+11.0** |
| α 0.45 | +1.4 | **+12.2** |

## 2. Answers

1. **At the successful command time, has any robot direct local evidence of the
   exit?** Only in the widest cell. At α 0.25 and α 0.35 the first robot does not
   physically exit until step 67.4 and 57.6 — *after* the command is needed.
2. **Is the command at or after the first local exit detection?** **No**, for two
   of three cells. Option A is structurally too late.
3. **Can local forward sensing detect the opening before physical exit?**
   **Yes** — at steps 42.8–46.4, i.e. 11–21 steps before the first robot exits.
4. **Required forward sensing distance?** Within **3.0 m**. The corridor is 1.0 m
   long, so a robot approaching or inside it sees both side walls terminate well
   inside its sensor range.
5. **Within the declared R_obs?** **Yes** — `R_obs = 3.0 m = lidar_range`, already
   frozen. No sensing assumption is changed.
6. **Could a peer message from a front robot supply the lead?** It could, but it
   is not needed, and it could not be *earlier*: a front robot's message cannot
   precede its own detection, and forward sensing already fires 11–21 steps
   before any robot exits.
7. **Does recovery need information unavailable to every robot?** **No.**

## 3. Conclusion

The successful recovery timing **is** locally observable — but not through exit
detection. It requires **forward opening** evidence, obtained from a robot's own
obstacle returns while it is still inside the passage.

`first_local_reopen = 21` in the raw data is an artefact: at step 21 the team is
still in the open approach and has not entered the corridor, so its clearance is
trivially large. It is not a recovery signal and is not used.
