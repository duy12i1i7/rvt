# Decentralized Reconfiguration Headroom Protocol (Task 5-1)

**Predeclared before any layout was generated or evaluated.**

Scenario qualification uses **only fixed diagnostic policies**. No learned
selector is trained, loaded, or consulted at any point, and no layout is
retained, removed or modified according to learned-model output.

## Scope limitation

**N = 6 only.** N = 3 and N = 4 are excluded because their KEEP and LINE tubes
overlap under Metric V3 (`delta_N` = 0.6708 and 1.0062 against the 1.10
threshold), so a configuration can satisfy both simultaneously and `always_line`
could meet the recovery requirement without ever leaving line. This is a real
restriction on the pilot's generality and is stated here rather than hidden.

## Diagnostic policies

| | policy | deployable? |
|---|---|---|
| P1 | always KEEP | yes |
| P2 | always LINE | yes |
| P3 | scripted KEEP→LINE→KEEP at the known geometric entry/exit planes | **no** — uses global position |
| P4 | scripted KEEP→LINE, no return | **no** |
| P5 | decentralized geometric event-triggered KEEP→LINE→KEEP | **yes** |
| P6 | best fixed mode per episode | **no** — diagnostic only |
| P7 | centralized scripted transition timing | **no** — upper reference only |

Every deployable policy uses the same robot-local controller. No policy uses a
learned selector, Recovery Event labels at runtime, future trajectory
information, global joint control, or centralized formation commands.
