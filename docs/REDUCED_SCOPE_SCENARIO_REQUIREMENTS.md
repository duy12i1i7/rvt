# Reduced-Scope Scenario Requirements

## Selection Rule

Future primary scenarios must expose genuine recoverability headroom between
the distinct COMPACT and LINE geometries. Scenario inclusion, geometry,
initial-condition seeds and communication settings must be frozen before
learned-model results are observed. No scenario may be selected because a
future checkpoint performs well on it.

The minimum required scenario types are:

| type | required mechanical outcome |
|---|---|
| A | COMPACT succeeds and LINE is unnecessarily conservative |
| B | LINE succeeds while COMPACT fails or becomes unsafe |
| C | one episode requires `COMPACT -> LINE -> COMPACT` |
| D | both candidates succeed |
| E | both candidates fail |
| F | communication degradation affects agreement while respecting the declared contract |
| G | a false bottleneck must not cause an unnecessary LINE commitment |

Each family must state physical validity, obstacle geometry, start topology,
success metrics, seed ownership and the expected distinction between candidate
outcomes before data generation.

## Exclusions

Primary scenarios do not require KEEP recovery and cannot rely on a KEEP edge
as their only successful solution. KEEP fixed-baseline episodes may be run on
the same frozen geometry as a diagnostic reference, but they do not become
primary candidate labels.

Final-test layouts remain inaccessible during scenario construction, target
generation, training and model selection. Experimental claims remain limited
to `N in {5, 6, 8, 12, 16, 24}`; no result may be described as arbitrary-team-
size validation.
