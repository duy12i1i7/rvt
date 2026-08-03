# Generic Role-Space Transition Path Diagnostic

One predeclared rest-to-rest triangular/trapezoidal profile is used for all pairs and N. Duration is derived from maximum static role displacement, physical maximum speed, maximum acceleration and the control period; no duration grid, scenario result or per-N value is used. Target dwell starts only after `s=1`.

| pair | N | ideal min clearance | static path safe | success | episodes |
|---|---|---|---|---|---|
| KEEP -> COMPACT | 5 | 0.285 | False | 0 | 4 |
| KEEP -> COMPACT | 6 | 0.285 | False | 0 | 4 |
| KEEP -> COMPACT | 8 | 0.285 | False | 0 | 4 |
| KEEP -> COMPACT | 12 | 0.402 | True | 0 | 4 |
| KEEP -> COMPACT | 16 | 0.402 | True | 0 | 4 |
| KEEP -> COMPACT | 24 | 0.177 | False | 0 | 4 |
| KEEP -> LINE | 5 | 0.636 | True | 4 | 4 |
| KEEP -> LINE | 6 | 0.636 | True | 4 | 4 |
| KEEP -> LINE | 8 | 0.636 | True | 4 | 4 |
| KEEP -> LINE | 12 | 0.636 | True | 4 | 4 |
| KEEP -> LINE | 16 | 0.636 | True | 4 | 4 |
| KEEP -> LINE | 24 | 0.636 | True | 4 | 4 |
| COMPACT -> KEEP | 5 | 0.285 | False | 0 | 4 |
| COMPACT -> KEEP | 6 | 0.285 | False | 0 | 4 |
| COMPACT -> KEEP | 8 | 0.285 | False | 0 | 4 |
| COMPACT -> KEEP | 12 | 0.402 | True | 0 | 4 |
| COMPACT -> KEEP | 16 | 0.402 | True | 0 | 4 |
| COMPACT -> KEEP | 24 | 0.177 | False | 0 | 4 |
| COMPACT -> LINE | 5 | 0.636 | True | 4 | 4 |
| COMPACT -> LINE | 6 | 0.636 | True | 4 | 4 |
| COMPACT -> LINE | 8 | 0.636 | True | 4 | 4 |
| COMPACT -> LINE | 12 | 0.636 | True | 4 | 4 |
| COMPACT -> LINE | 16 | 0.636 | True | 4 | 4 |
| COMPACT -> LINE | 24 | 0.636 | True | 4 | 4 |
| LINE -> KEEP | 5 | 0.636 | True | 0 | 4 |
| LINE -> KEEP | 6 | 0.636 | True | 4 | 4 |
| LINE -> KEEP | 8 | 0.636 | True | 4 | 4 |
| LINE -> KEEP | 12 | 0.636 | True | 4 | 4 |
| LINE -> KEEP | 16 | 0.636 | True | 4 | 4 |
| LINE -> KEEP | 24 | 0.636 | True | 4 | 4 |
| LINE -> COMPACT | 5 | 0.636 | True | 4 | 4 |
| LINE -> COMPACT | 6 | 0.636 | True | 4 | 4 |
| LINE -> COMPACT | 8 | 0.636 | True | 4 | 4 |
| LINE -> COMPACT | 12 | 0.636 | True | 4 | 4 |
| LINE -> COMPACT | 16 | 0.636 | True | 4 | 4 |
| LINE -> COMPACT | 24 | 0.636 | True | 4 | 4 |

The profile improves completion from 47/144 to 92/144 and projection aborts from 97 to 52. KEEP/COMPACT straight paths cross the 0.4 m clearance at N=5, 6, 8 and 24; no slower duration can repair those static swept-path intersections. N=12 and N=16 retain only about 0.0025 m ideal margin and also fail under the predeclared profile.
