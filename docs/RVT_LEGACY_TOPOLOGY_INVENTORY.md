# RVT Legacy Topology Inventory

## 1. Scope and provenance

This inventory was completed against Phase 2 commit
`37519253f2b92bca824d39729093f7427190f106` before any Phase 3 topology code
was modified. It covers deployable runtime, centralized legacy simulation,
evaluation, ROS 2, scripts, stored artifacts, checkpoints, and manuscript text.

The repository contains three incompatible historical vocabularies:

1. the selected decentralized base uses `KEEP=0` and `LINE=2`, with numeric
   value `1` reserved as a retired SPLIT mode;
2. the legacy centralized action vocabulary uses `0=keep`, `1=compress`,
   `2=line`, `3=split_hint`, and `4=recover`;
3. older models and manuscript sections use the structural set
   `{keep, line, split}`, while binary checkpoints imply `{keep, line}` only.

Numeric topology values therefore cannot be migrated without a declared source
vocabulary/version.

## 2. Representation inventory

| Name or ID | Definition location | Use sites | Geometry source | Variable-N support | Controller support | Metric support | Transition support | Physical status | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|
| Decentralized `KEEP=0` | `decentralized/system_model.py` | epoch, consensus, runtime, comms, ego graph, local controller, tests | `RoleAssignment._keep_template` | Algorithmic square-like grid | Verified local pairwise base | Metric V3 | KEEP/LINE epoch protocol | Approved existing primary topology | Preserve ID and exact geometry semantics; move construction to registry |
| Decentralized `LINE=2` | `decentralized/system_model.py` | same deployable modules | `RoleAssignment._line_template` | Algorithmic single file | Verified local pairwise base | Metric V3 | KEEP/LINE epoch protocol | Approved existing primary topology | Preserve ID and exact persistent-rank geometry; move construction to registry |
| Retired decentralized `SPLIT=1` | wire/confirmation tests and historical comments | codec rejection tests | None in selected base | No | Explicitly unsupported | No | Explicitly unreachable | Retired after failed qualification | Reserve legacy meaning; never reinterpret silently as COMPACT |
| Legacy action `keep=0` | `config.TOPOLOGY_ACTIONS` | environment, controller, safety, datasets, evaluation, visualization, scripts | default grid branch | Yes, formula-based | Centralized expert and simulator | legacy form RMS | adaptive latent state | Historical action and grid anchor | Compatibility migration only; distinguish action from topology ID |
| Legacy action `compress=1` | `config.TOPOLOGY_ACTIONS` | environment/controller apply-state logic | scaled KEEP grid, not a separate template | Inherits KEEP | Centralized legacy only | legacy metrics through scale | continuous scale contraction | Not a structural topology; same geometry family as KEEP | Map only as legacy action metadata; do not alias to new COMPACT |
| Legacy action `line=2` | `config.TOPOLOGY_ACTIONS` | environment, controller, ROS, scripts | state-sorted line along inferred corridor | Formula supports N, but assignment is runtime-global | Centralized/ROS controller | legacy metrics | latent action update | Geometry shape matches LINE, role mapping does not | Preserve historical reader; registry LINE uses persistent roles |
| Legacy action `split_hint=3` / `split=3` | `config.py`, environment, controller, ROS, scripts | legacy learned vocabulary `[0,2,3]`, safety and studies | two state-sorted lanes | Formula-based | Centralized/ROS only | legacy metrics | no valid merge protocol | Mechanically infeasible at compression floor and never completed task in frozen qualification | Retire from primary study; preserve explicit legacy migration only |
| Legacy action `recover=4` | `config.TOPOLOGY_ACTIONS` | environment/controller/ROS latent update | expansion back toward KEEP grid | Inherits KEEP | Centralized legacy only | legacy metrics | procedural scale/merge action | Not a topology | Preserve as historical action, never register as primary topology |
| New primary `COMPACT` | Phase 3 request | none before Phase 3 | absent | absent | absent | absent | absent | Not implemented at inventory time | Add a new stable canonical ID that does not collide semantically with legacy values |
| `WEDGE` | requested audit term | no code, config, script, artifact, ROS, or active manuscript topology definition found | absent | No | No | No | No | Nonexistent in this repository | Do not register; reject as unknown legacy value |
| Manuscript `KEEP` | `latex/access.tex` | method description | called a "nominal compact formation" and later a corridor-aligned grid | Formula implied | centralized formulation | centroid formation cost | latent topology selector | Terminology conflicts with a distinct COMPACT topology | Revise only in later manuscript phase; migration docs must disambiguate adjective "compact" from canonical COMPACT |
| Manuscript `LINE` | `latex/access.tex` | method equations | 1-D corridor lattice | Formula implied | centralized formulation | centroid formation cost | latent selector | Same shape family as existing LINE | Preserve semantic shape, not state-sorted runtime reassignment |
| Manuscript `SPLIT` | `latex/access.tex` | old admissible set and latent geometry section | two corridor lanes | Formula implied | centralized formulation | centroid formation cost | selection without valid merge | Contradicted by frozen SPLIT qualification | Historical text only; excluded from Phase 3 primary set |
| Manuscript `COMPRESS/RECOVER` | `latex/access.tex` | latent mode family | continuous grid scale updates | Inherits grid | centralized formulation | legacy metrics | procedural latent updates | Actions, not distinct templates | Do not expose as registry topologies |
| ROS numeric modes `0/2/3` | `ros2_ws/.../formation.py` | ROS agent policy observation and formation state | copied grid, state-sorted line, state-sorted split tables | Formula-based | ROS centralized peer snapshot path | ROS monitor only | copied action-state update | Legacy production prototype; topology logic duplicated | Deprecate as independent authority; no production adapter work in Phase 3 |
| Offline Metric V3 templates | `decentralized/formation_metric_v3.py` | recovery and tube diagnostics | delegates to `RoleAssignment.coords` | Yes | N/A | Authoritative selected metric | KEEP recovery only | Correct source but separate adapter | Make registry template adapter the shared source without changing epsilon or formula |
| Environment geometry templates | `environment.desired_offsets` | observations and legacy simulator | copied grid/line/split logic | Formula-based | legacy centralized | legacy metrics | latent state | Diverges from persistent LINE role assignment | Retain for historical simulator reproducibility; isolate as legacy |
| Central expert templates | `controllers._desired_offsets` | legacy expert and rollout labels | another copied grid/line/split implementation | Formula-based | centralized expert | downstream legacy metrics | action-conditioned | Duplicates environment; LINE depends on current joint-state sort | Retain compatibility, but primary registry adapters must not copy templates |
| Role beacon fields | `system_model.RobotView`, `NeighbourRecord`; `comms.Beacon` | deployable local controller and ego graph | two copied coordinates: `role_keep`, `role_line` | Team-size agnostic wire shape | Selected base | N/A | binary modes only | Valid but fixed to two named modes | Add versioned role/topology-local adapter; do not require global template at runtime |
| Model action heads, 5-way lineage | `models.RVTSwarmPolicy`, `config.TOPOLOGY_ACTIONS` | old training/evaluation | no direct geometry; index interpreted by legacy action list | Tensor output fixed by configured count | learned centralized action residual | rollout labels | selector | Historical only | Require source vocabulary when loading; no silent primary-registry reinterpretation |
| Model action heads, 3-way lineage | `LEARNED_TOPOLOGY_IDS=[0,2,3]`, older `score_head` checkpoints | old studies/checkpoints | `{keep,line,split}` by code convention | Tensor width 3 | learned centralized | old recovery studies | selector | SPLIT now retired | Preserve with explicit `legacy-structural-v1` vocabulary |
| Model action heads, binary lineage | `models.BINARY_MODES`, `binary_pilot.MODES`, decentralized selectors | binary checkpoints and dry runs | `{keep,line}` by code convention | Tensor width 2 | binary model or fixed local controller | binary labels | binary selector | Historical selected base vocabulary | Preserve with explicit `binary-keep-line-v1` adapter; shape alone is insufficient provenance |
| Script-local mode maps | `recovery_v2_study.py`, `validate_split_mode.py`, `qualify_scenarios.py`, `recovery_event_sensitivity.py`, `generate_binary_labels.py`, `make_smoke_diagnostics.py` | offline studies | delegates to legacy env/controller or selected roles | Mixed | Offline only | Mixed | Mixed | Duplicate names/IDs | Freeze as historical script semantics; new scripts must import registry/migration API |
| Result/manifests and traces | `results/**` | historical audit and regression readers | source-commit-specific | Mostly N=4/6; some broader legacy studies | N/A | stored metrics | stored mode IDs/names | Immutable historical evidence | Preserve files; readers require source commit/schema and must not relabel values |

## 3. Geometry duplication and divergence

### KEEP

The selected decentralized KEEP template is a deterministic square-like grid:

```text
columns = max(2, ceil(sqrt(N)))
rows = ceil(N / columns)
slot i = divmod(i, columns)
```

`RoleAssignment`, `controllers._desired_offsets`, `environment.desired_offsets`,
and ROS `desired_offsets` independently implement this rule. Their lateral-axis
sign conventions differ by frame representation, but the selected decentralized
tests establish world-frame equivalence for the existing mission direction.
For incomplete final rows the raw legacy table is not centered; Metric V3
centers it before evaluation while pairwise control is translation invariant.

### LINE

Two geometries share the name LINE:

- selected decentralized LINE assigns a persistent rank at mission setup and
  never changes it at runtime;
- centralized environment/controller/ROS LINE sorts current joint positions
  along the corridor on each construction call.

The unlabelled set of geometric slots is the same. The robot-to-slot mapping is
not semantically equivalent once robots exchange order. Only the persistent
mapping satisfies the Phase 3 runtime contract.

### SPLIT

The centralized environment, expert, and ROS copy the same two-lane idea, but
all depend on centralized state sorting and subteam reassignment. The frozen
`SPLIT_MODE_VALIDATION.md` found the template infeasible at its compression
floor and no successful merge behavior. SPLIT is not eligible for the primary
registry.

### COMPRESS and RECOVER

Both are procedural updates of a scale attached to the KEEP grid. Neither owns
a distinct immutable template, persistent role mapping, graph, or tube. Treating
either as canonical COMPACT would silently change historical semantics.

## 4. Fixed-size and runtime-global findings

- No active selected KEEP/LINE generator uses a fixed six-row table.
- Many fixtures contain N=6 arrays, but they are tests or frozen traces rather
  than runtime construction sources.
- Legacy centralized and ROS LINE/SPLIT generators sort a full `(N,2)` position
  array at runtime. They violate the selected robot-local role contract.
- `RobotView` and the beacon wire schema carry only KEEP and LINE role
  coordinates. Extending deployable wire protocols is outside Phase 3; the
  registry must expose a local view without introducing a new protocol.
- Model heads have fixed output widths of two or three for their checkpoint
  vocabulary. They are architecture artifacts, not generic registry iterators.

## 5. Checkpoint and manifest provenance

Inspected `.pt` files contain method/source metadata and state dictionaries but
no explicit `topology_ids`, `modes`, or versioned topology vocabulary field.
Binary heads have output width two and older RVT score heads width three. Width
does not safely identify semantics because numeric ID `1` means retired SPLIT in
the decentralized lineage and COMPRESS action in the five-action lineage.

Compatibility loading must therefore require one of:

- an explicit versioned vocabulary;
- a recognized historical method/dataset/source-commit mapping;
- an explicit caller-supplied legacy vocabulary.

Otherwise migration must fail rather than infer semantics from tensor width.
Historical files remain unchanged and traceable to their original commits.

## 6. Required Phase 3 disposition

| Finding class | Disposition |
|---|---|
| Duplicate KEEP construction | Registry becomes primary source; legacy simulator paths remain isolated for reproducibility |
| Duplicate/dynamic LINE assignment | Preserve persistent selected semantics; compare slot geometry separately from legacy dynamic assignment |
| Conflicting numeric ID `1` | Never migrate without source vocabulary; reserve a new non-conflicting COMPACT ID |
| SPLIT/SPLIT_HINT | Explicit legacy-only migration, not a primary topology |
| COMPRESS/RECOVER | Legacy action metadata only, not topology aliases |
| WEDGE | Explicit unknown/unsupported result |
| Model/checkpoint vocabularies | Versioned compatibility adapters; no silent reinterpretation |
| Metric/controller template ownership | Both primary adapters consume the registry; epsilon and gains remain frozen |
| ROS topology tables | Deprecated independent implementation; production migration remains a later phase |

No scientific experiment, learned model, final-test layout, or closed-loop
comparison was run while producing this inventory.
