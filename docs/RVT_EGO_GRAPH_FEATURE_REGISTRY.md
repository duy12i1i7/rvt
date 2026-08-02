# RVT Ego Graph Feature Registry

## Included node features

`current consumer` is `V2 serialization/tests` for every included feature. No
learned Phase 5 consumer exists yet. Future consumers are candidate
recoverability and robot-action heads unless narrowed during Phase 5.

| Feature | Node/edge type | Units | Normalization | Runtime source | Locality proof | Missing behavior | Current consumer | Future consumer | Status/reason |
|---|---|---|---|---|---|---|---|---|---|
| node kind one-hot | all nodes | one-hot | none | local schema | assigned during local construction | always valid | V2 | both heads | included: type distinction |
| relative position | all nodes | dimensionless | nominal spacing | own origin, peer message, local obstacle | every non-self vector is locally received/sensed | self exact zero | V2 | both | included |
| relative velocity | peer, obstacle | dimensionless | maximum speed | fresh message or local tracker | no simulator recovery path | zero plus false mask | V2 | both | included |
| class-specific distance | all nodes | dimensionless | `R_comm` or `R_obs` | local geometry | range-gated input only | self exact zero | V2 | both | included |
| bearing `(cos,sin)` | peer, obstacle | dimensionless | unit vector | local relative vector | derived per admitted local entity | zero plus false mask at zero range | V2 | both | included |
| committed topology one-hot | self, peer | one-hot | KEEP/COMPACT/LINE | local memory or peer message | no complete vote | invalid self rejects graph; invalid peer omitted | V2 | recoverability | included |
| candidate topology one-hot | self | one-hot | KEEP/COMPACT/LINE | candidate query | one local query only | always valid | V2 | recoverability | included |
| candidate role offset | self, nominal observed peer | dimensionless | nominal spacing | robot-local topology slice | slice contains only observer and its nominal relations | peer masked unless currently observed nominal neighbour | V2 | both | included |
| own candidate displacement | self | dimensionless | nominal spacing | two own local role offsets | no all-role table | always valid | V2 | both | included |
| transition magnitude | self | dimensionless | nominal spacing | own displacement | own geometry only | always valid | V2 | both | included |
| transition observation extent | self | dimensionless | `R_obs` | own displacement and immutable safety/controller bounds | role-dependent local geometry only | unsupported config rejects upstream | V2 | recoverability | included |
| relative goal vector | self | dimensionless | nominal spacing | own pose and shared goal | approved shared mission input | always valid | V2 | both | included |
| goal distance | self | dimensionless | nominal spacing | own pose and shared goal | norm of local goal vector | always valid | V2 | both | included |
| own velocity | self | dimensionless | maximum speed | own odometry | self state | always valid | V2 | both | included |
| local progress | self | dimensionless | nominal spacing | local lifecycle memory | no centroid/team progress | zero valid | V2 | recoverability | included |
| decision age | self | dimensionless | configured reference steps | local lifecycle memory | self counter only | clamped to `[0,1]` | V2 | recoverability | included |
| peer message age | peer | dimensionless | stale-round limit | received message | one-hop record only | stale peer omitted | V2 | both | included |
| peer role known | peer | Boolean | none | local candidate slice | tests nominal membership for admitted peer only | false when non-nominal | V2 | both | included |
| peer topology conflict | peer | Boolean | none | own and sender commitment | pairwise comparison only | false when equal | V2 | recoverability | included |
| obstacle radius | obstacle | dimensionless | `R_obs` | local primitive | sensor record only | invalid radius omits node | V2 | both | included |
| obstacle confidence | obstacle | probability | none | local sensor | no map confidence | invalid confidence omits node | V2 | both | included |
| obstacle age | obstacle | dimensionless | control period | local sensor | local timestamp only | stale node omitted | V2 | both | included |

## Included edge features

| Feature | Node/edge type | Units | Normalization | Runtime source | Locality proof | Missing behavior | Current consumer | Future consumer | Status/reason |
|---|---|---|---|---|---|---|---|---|---|
| edge type one-hot | all four directed edge types | one-hot | none | local construction | each edge is root incident | always valid | V2 | both | included |
| directed relative position | all edges | dimensionless | nominal spacing | admitted node geometry | local node endpoints only | always valid | V2 | both | included |
| directed relative velocity | all edges | dimensionless | maximum speed | admitted node velocity | no hidden recovery | zero plus false mask | V2 | both | included |
| directed distance | all edges | dimensionless | `R_comm` or `R_obs` | local geometry | same admitted relation | always valid | V2 | both | included |
| directed bearing | all edges | dimensionless | unit vector | local edge vector | same admitted relation | zero plus false mask at zero range | V2 | both | included |
| nominal formation relation | robot edges | Boolean | none | local candidate slice | evaluated only for admitted peer | false for non-nominal | V2 | both | included |
| desired pairwise offset | nominal robot edges | dimensionless | nominal spacing | local candidate slice | observer-to-peer relation only | false mask for non-nominal peer | V2 | both | included |
| local formation residual | nominal robot edges | dimensionless | nominal spacing | peer observation minus local desired offset | uses no complete template | false mask for non-nominal peer | V2 | both | included |
| candidate topology one-hot | robot edges | one-hot | KEEP/COMPACT/LINE | candidate query | graph-local scalar | masked on obstacle edge | V2 | recoverability | included |

## Rejected features

| Feature | Type | Units | Normalization | Runtime source | Locality proof | Missing behavior | Current consumer | Future consumer | Status/reason |
|---|---|---|---|---|---|---|---|---|---|
| swarm centroid | self | m | none | joint state | impossible locally | N/A | none | none | rejected: global state |
| team-average velocity | self | m/s | speed | joint state | impossible locally | N/A | legacy only | none | rejected: global statistic |
| global formation error | self | m | tolerance | full template and joint state | impossible locally | N/A | legacy only | none | rejected: global statistic |
| global minimum clearance/TTC | self | m/s | ranges | all robots/obstacles | impossible locally | N/A | legacy only | none | rejected: global statistic |
| complete topology vote/score | self | scalar | learned | all robots | impossible locally | N/A | none | none | rejected: consensus/global data |
| global goal progress/exit-plane distance | self | m | layout scale | centroid/layout | impossible locally | N/A | legacy metric | none | rejected: evaluation geometry |
| corridor alpha/scenario family | self | label | none | scenario definition | not sensed locally | N/A | evaluation | none | rejected: label leak |
| rollout success/future recovery/final outcome | self | label | none | future evaluator | future information | N/A | training labels | none | rejected: outcome leak |
| complete candidate template/width/length | self | m | spacing | full registry | exceeds local slice | N/A | offline registry | none | rejected: global candidate geometry |
| all team role offsets | self | m | spacing | full registry | exceeds local slice | N/A | offline registry | none | rejected: global role table |
| peer raw obstacle observations | peer | mixed | mixed | another robot | not in current message contract | N/A | none | none | rejected: transitive sensing |
| peer complete ego graph/history | peer | mixed | mixed | another robot | not one-hop physical state | N/A | none | none | rejected: transitive/global reconstruction |
| global rank/centrality/leader status | peer | scalar | team size | complete graph | impossible locally | N/A | none | none | rejected: global graph shortcut |
| global obstacle ID/polygon vertices | obstacle | ID/m | none | simulator map | outside local primitive contract | N/A | environment | none | rejected: map shortcut/unseen geometry |
| dataset mean/std normalization | all | mixed | dataset statistics | complete dataset | can leak final test | N/A | none | none | rejected: non-physical normalization |
| raw robot-array index | all | index | N | simulator ordering | not persistent identity | N/A | none | none | rejected: permutation dependence |

## Registry authority

The executable `NODE_FEATURE_DEFINITIONS` and `EDGE_FEATURE_DEFINITIONS` tuples
are the source of truth. Their ordered canonical JSON is hashed into
`EGO_GRAPH_FEATURE_SCHEMA_SHA256`. A semantic or ordering change therefore
requires a new graph or normalization version and new Phase 5 model artifacts.
