# Topology Transition Admissibility

Admissibility is derived from the authoritative topology registry and immutable
runtime configuration.  It is evaluated before lifecycle creation.

The six candidate pairs are KEEP to COMPACT, COMPACT to KEEP, KEEP to LINE,
LINE to KEEP, COMPACT to LINE, and LINE to COMPACT.  For each role the registry
provides source/target offsets, displacement, longitudinal/lateral components,
swept segment, and required local observation extent.  Pair reports also carry
maximum/RMS displacement, nominal graph change, intended mechanical use, and
limitations.

A request is rejected when source equals target, a topology ID is unknown, the
source does not equal the robot's committed topology, persistent role sets are
invalid or differ, either template is mechanically unsupported, or the dynamic
local observation contract cannot represent the transition.  A rejected or
source-equals-target request creates no lifecycle and no mode epoch.

All registry-supported pairs through N=24 are candidates for mechanical Phase 7
qualification.  Admissibility does not assert local safety or mission success;
score, readiness, and confirmation remain mandatory.

## Frozen geometry audit

Values are meters.  `distribution` is minimum/median/maximum persistent-role
displacement.  The table shows the approved experimental N=6 and mechanical
upper-scope N=24 endpoints; intermediate team sizes are serialized in the
qualification records.

| pair | N | displacement distribution | max longitudinal | max lateral | static observation extent | source/target graph diameter | admitted |
|---|---:|---:|---:|---:|---:|---:|---|
| KEEP -> COMPACT | 6 | 0.636 / 0.636 / 1.423 | 0.450 | 1.350 | 1.900 | 3 / 3 | yes |
| KEEP -> COMPACT | 24 | 0.645 / 2.384 / 3.468 | 3.225 | 2.325 | 2.875 | 8 / 12 | yes |
| COMPACT -> KEEP | 6 | 0.636 / 0.636 / 1.423 | 0.450 | 1.350 | 1.900 | 3 / 3 | yes |
| COMPACT -> KEEP | 24 | 0.645 / 2.384 / 3.468 | 3.225 | 2.325 | 2.875 | 12 / 8 | yes |
| KEEP -> LINE | 6 | 0.900 / 0.900 / 2.012 | 1.800 | 0.900 | 1.450 | 3 / 5 | yes |
| KEEP -> LINE | 24 | 0.382 / 4.589 / 8.796 | 8.625 | 1.875 | 2.425 | 8 / 23 | yes |
| LINE -> KEEP | 6 | 0.900 / 0.900 / 2.012 | 1.800 | 0.900 | 1.450 | 5 / 3 | yes |
| LINE -> KEEP | 24 | 0.382 / 4.589 / 8.796 | 8.625 | 1.875 | 2.425 | 23 / 8 | yes |
| COMPACT -> LINE | 6 | 0.636 / 0.636 / 1.423 | 1.350 | 0.450 | 1.000 | 3 / 5 | yes |
| COMPACT -> LINE | 24 | 0.450 / 2.737 / 5.419 | 5.400 | 0.450 | 1.000 | 12 / 23 | yes |
| LINE -> COMPACT | 6 | 0.636 / 0.636 / 1.423 | 1.350 | 0.450 | 1.000 | 5 / 3 | yes |
| LINE -> COMPACT | 24 | 0.450 / 2.737 / 5.419 | 5.400 | 0.450 | 1.000 | 23 / 12 | yes |

The nominal graph edge set changes for every pair, including KEEP/COMPACT pairs
whose diameters happen to match at N=6.  Maximum required observation extent is
2.875 m, below `R_obs = 3.0 m`.  The known limitation remains that registry
admission proves representable geometry, not safe closed-loop role motion.

Expected use is wider-to-narrower access, narrower-to-wider recovery, or a
mechanically forced diagnostic.  A nominal graph change is static mission
metadata only; it does not authorize communication links or topology selection.
