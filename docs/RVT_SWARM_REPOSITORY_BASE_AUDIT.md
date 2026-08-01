# RVT-Swarm Repository Base Audit

**Phase:** 0 only - repository and provenance audit
**Audit date:** 2026-08-02 (Asia/Ho_Chi_Minh)
**Repository:** `/Users/udy/rvt`
**Remote:** `https://github.com/duy12i1i7/rvt.git`
**Selected base:** `1795809bcb2025bf9777cf08a5f6b287082732a6`
**Base tag:** `rvt-swarm-reconstruction-base-v1`
**Reconstruction branch:** `research/rvt-swarm-fd24-v1`

## 1. Decision

Use commit `1795809bcb2025bf9777cf08a5f6b287082732a6` as the reconstruction base.
This is not an automatic choice of the newest commit. It is the earliest local
tip that simultaneously preserves:

1. the original RVT whole-graph model, candidate-conditioned action bank, and
   2-to-24-robot benchmark code;
2. Evaluation Protocol V2 repairs and the method/action-learning audits;
3. the dense KEEP/LINE action dataset and Recovery Event V2 labels;
4. the robot-local ego graph, communication, leaderless consensus, local
   controller, strict decentralization guards, and integrated event protocol;
5. Formation Recovery Metric V3 and the role/template construction;
6. the parameter-semantics repair at `cec0b40`; and
7. the frozen post-repair regression proving that the corrected detector alone
   does not make common KEEP commitment safe.

The post-repair regression is load-bearing negative evidence. Starting at
`cec0b40` would omit the measured cross-role safety failure and make it easier to
repeat an already-refuted architecture. Starting from public `main` would lose
40 research commits. No candidate newer than `1795809` existed after fetching
the remote refs; `origin/main` only adds the merge commit for the prescreen audit.

This base is a **reconstruction base, not a method freeze**. It does not yet
implement the intended RVT-FD24 method.

## 2. Freeze Record

The working tree was clean before either ref was created.

| Item | Exact value | Verification |
|---|---|---|
| Selected source commit | `1795809bcb2025bf9777cf08a5f6b287082732a6` | `git rev-parse HEAD` before branching |
| Immutable base tag | `rvt-swarm-reconstruction-base-v1` | dereferences to the selected source commit |
| New branch | `research/rvt-swarm-fd24-v1` | created directly from the selected source commit |
| Previous branch | `research/post-parameter-repair-regression-v1` | preserved at `1795809` |
| Legacy refs | unchanged | no branch, tag, commit, report, result, or checkpoint deleted |
| Runtime/model edits in Phase 0 | none | this audit document is the only tracked file added |

## 3. Git Provenance Inventory

### 3.1 Local branches

| Local branch | Tip | Role in history |
|---|---:|---|
| `main` | `fab222b` | original public implementation before the prescreen merge |
| `docs/prescreen-redesign-audit` | `3bb1c61` | prescreen diagnosis and redesign audit |
| `fix/benchmark-validity` | `3e93d95` | benchmark metric, split, seed, budget, and provenance repairs |
| `research/method-audit-v2` | `c9f84e6` | architecture and learning audit |
| `research/scenario-headroom-v1` | `d703511` | scenario headroom study; recovery label later invalidated |
| `research/recovery-event-v2` | `4b21585` | corrected separated recovery events |
| `research/binary-mode-pilot-v1` | `0cdf35e` | dense action-learning repair and seed-0 binary diagnosis |
| `research/fully-decentralized-selector-v1` | `02d443b` | local ego graph, communication, consensus, selector dry run |
| `research/decentralized-reconfiguration-v2` | `e284742` | integrated protocol and reconfiguration qualification |
| `research/decentralized-event-protocol-v3` | `56d6c5f` | local forward-opening event V3 |
| `research/recovery-trigger-timing-repair-v1` | `e6ecbec` | recovery proposal/timing repair |
| `research/recovery-propagation-latency-repair-v1` | `26f07c9` | propagation and latency repair |
| `research/distributed-safe-expansion-v1` | `9163292` | generality audit STOP; no safe-expansion protocol implemented |
| `research/parameter-semantics-repair-v1` | `cec0b40` | configuration and parameter semantics repair |
| `research/post-parameter-repair-regression-v1` | `1795809` | frozen three-cell regression, Verdict B |
| `research/rvt-swarm-fd24-v1` | `1795809` at creation | selected reconstruction branch |

All research tips descend from the original code line. They are not competing
independent implementations. The useful work is cumulative, with `1795809`
containing the content of the earlier research tips.

### 3.2 Remote branches

`git fetch --all --tags --prune` was run during this audit.

| Remote ref | Tip | Relation to selected base |
|---|---:|---|
| `origin/HEAD -> origin/main` | `bb1f11c` | remote default |
| `origin/main` | `bb1f11c` | merge of `3bb1c61`; 1 unique merge commit vs selected base |
| `origin/docs/prescreen-redesign-audit` | `3bb1c61` | content already present in selected base |

`origin/main...1795809` is `1/40` commits. Its merge base is `3bb1c61`; the
remote-only commit adds no code beyond the already-preserved audit document.

### 3.3 Tags

| Tag | Commit | Meaning |
|---|---:|---|
| `benchmark-protocol-v2-smoke` | `3e93d95` | mechanically validated benchmark smoke state |
| `method-audit-v2-complete` | `c9f84e6` | method audit complete |
| `scenario-headroom-v1-invalid-recovery-label` | `d703511` | explicitly invalid recovery-label state |
| `recovery-event-v2-complete` | `4b21585` | Recovery Event V2 freeze |
| `binary-mode-end-to-end-diagnosis-v1` | `0cdf35e` | binary action/controller diagnosis |
| `fully-decentralized-seed0-diagnosis-v1` | `02d443b` | decentralized seed-0 diagnosis |
| `decentralized-reconfiguration-mechanics-v1` | `b4f6286` | scripted KEEP-LINE-KEEP mechanics |
| `decentralized-reconfiguration-headroom-diagnosis-v1` | `e284742` | reconfiguration headroom diagnosis |
| `decentralized-recovery-timing-discrepancy-v1` | `56d6c5f` | V3 timing discrepancy |
| `decentralized-recovery-proposal-repair-v1` | `e6ecbec` | proposal repair |
| `decentralized-recovery-propagation-v1` | `26f07c9` | propagation/latency repair |
| `decentralized-generality-audit-v1` | `9163292` | STOP before parameter repair |
| `decentralized-parameter-semantics-v1` | `cec0b40` | accepted parameter repair |
| `rvt-swarm-reconstruction-base-v1` | `1795809` | Phase 0 selected base |

### 3.4 Recent research chronology

| Commit | Content and disposition |
|---:|---|
| `7ab106f` | corrected benchmark validity defects |
| `c08a0c1` | Evaluation Protocol V2 semantics, split, seed, and budget repairs |
| `3e93d95` | validated smoke/provenance freeze |
| `095ec5c`, `c9f84e6` | learning sanity and method audit; full architecture unsupported |
| `d703511` | first headroom study; recovery label invalid |
| `5e377a0`, `4b21585` | separated local progress, formation recovery, and task recovery |
| `3f881e0`, `9bb24b0` | binary pilot and Recovery Event V2 labels |
| `c74f0c9` | decentralized system model, radio, ego graph, roles, consensus, controller, guards |
| `ffa70fa` | epoch protocol, selector models, communication accounting, gates |
| `02d443b` | decentralized seed-0 dry run and stress report |
| `7b7dd06` | deployable runtime routed through the real decentralized protocol |
| `af1d2b3`, `b4f6286` | Metric V3 and valid scripted reconfiguration mechanics |
| `e284742` | reconfiguration headroom qualification |
| `56d6c5f` | forward-opening event V3 |
| `e6ecbec`, `347ceeb`, `26f07c9` | trigger, proposal, propagation, and latency repairs |
| `9163292` | generality audit STOP on four magic values and an unsound diameter bound |
| `cec0b40` | role-dependent detector and parameter-semantics repair |
| `1795809` | frozen post-repair regression; distributed readiness remains necessary |

### 3.5 Working tree and object database

- The selected base checkout was clean before documentation work.
- Ignored checkpoints and build/cache files are not uncommitted source changes.
- `git fsck --full --no-reflogs` exited successfully: no corrupt or missing
  reachable object was reported.
- Repository hygiene debt remains: 941 unreachable objects (172 blobs, 763
  trees, 6 commits) and 83 `tmp_obj_*` files totalling 36.73 MiB. They were not
  pruned because Phase 0 preserves all legacy material.

## 4. Candidate Base Matrix

Historical test counts below come from the report at that candidate. Only the
selected base was rerun from a clean checkout during this audit.

| Branch or commit | Useful components | Known defects | Decentralization status | Action-learning status | Variable-N status | Test status | Recommended disposition |
|---|---|---|---|---|---|---|---|
| `main` / `fab222b` | original RVT, topology action bank, simulator, 2-24 benchmark, ROS 2 scaffold | invalid episode metrics, benchmark fairness/provenance defects, stale paper claims | centralized whole-team graph and selector | learned action heads exist; weak closed loop | configured N=2..24, no held-out-N claim | pre-repair; not rerun | reject as base; preserve as origin |
| `docs/prescreen-redesign-audit` / `3bb1c61` | adds decisive scientific diagnosis | no implementation repair | same as `main` | same as `main` | same as `main` | documentation-only tip | preserve; content already inherited |
| `origin/main` / `bb1f11c` | public merge of prescreen audit | no research implementation beyond `3bb1c61` | centralized | unchanged | unchanged | not rerun | reject; remote is 40 research commits behind |
| `fix/benchmark-validity` / `3e93d95` | Evaluation Protocol V2, split/seed/budget/provenance repairs | original method remains global; method evidence weak | centralized | action heads retained | original 2-24 sweep; validation split repaired | 108 passed in smoke report | preserve as benchmark milestone |
| `research/method-audit-v2` / `c9f84e6` | micro-overfit, attribution, simplified-model evidence | topology selector and safety filter inert; behavior-cloning shift; no headroom | centralized whole graph | action imitation works open loop; no isolated action-bank support | original configuration only | audit checks reported; no clean rerun here | preserve evidence; not a reconstruction base |
| `research/scenario-headroom-v1` / `d703511` | disjoint layouts and mode-headroom apparatus | recovery label invalid; several qualification gates fail | centralized label/evaluation path | no new deployable action solution | pilot N=4,6 | invalid-state tag exists | never reuse labels/results; preserve diagnostic |
| `research/recovery-event-v2` / `4b21585` | valid task/formation/local event separation | still no decentralized runtime; binary scope emerging | labels may use centralized simulation as allowed | no action repair yet | pilot-specific | report gates include remaining stability limitations | preserve label semantics |
| `research/binary-mode-pilot-v1` / `0cdf35e` | dense actions, BCE recovery model, decisive metric, selected engineering checkpoints | learned LINE head gives 0 closed-loop success; whole-graph input; KEEP/LINE only | centralized graph/runtime | dense nRMSE 0.190, but learned low-level controller unusable in LINE | data only N=4,6 | 20 pilot checks pass | preserve dense-data/action-learning assets; not deployable base alone |
| `research/fully-decentralized-selector-v1` / `02d443b` | RobotView, ego graph, P2P radio, MH consensus, guards, local controller | periodic protocol hurts; delay defect at K=1; no scenario headroom; runtime integration was incomplete at this point | local/leaderless components pass guards | selector only; explicitly no action head | construction tested around N=4,6 | 330 passed; 0 guard violations | preserve architecture; use descendants with integration repairs |
| `research/decentralized-reconfiguration-v2` / `e284742` | real protocol integration, Metric V3, scripted KEEP-LINE-KEEP mechanics, valid fixtures | selector headroom remains weak; closed loop experimentally N=6 | fully decentralized deployable path under stated boundary | fixed local controller, no learned residual | role construction general; experiments N=6 | 591 passed in qualification report; 0 guards | strong intermediate milestone, superseded |
| `research/decentralized-event-protocol-v3` / `56d6c5f` | local exit observability and forward-opening recovery event | detector/timing discrepancy remains | fully decentralized and leaderless | no learned action | mechanically general, closed loop N=6 | 601 passed; 0 guards | preserve event history; superseded |
| `research/recovery-trigger-timing-repair-v1` / `e6ecbec` | same-trace proposal/timing repair | later propagation/parameter issues remain | fully decentralized | no learned action | closed loop N=6 | 604 passed; 0 guards | preserve; superseded |
| `research/recovery-propagation-latency-repair-v1` / `26f07c9` | propagation and latency repair | unexplained detector constants and k-trigger defect remain | fully decentralized | no learned action | N=6 evidence | 604 passed; 0 guards | preserve; superseded |
| `research/distributed-safe-expansion-v1` / `9163292` | generality and literal audit | four unexplained mode constants; k-trigger unsound; despite name, no readiness certificate exists | guards clean, parameter claim unsound | no learned action | templates general; N>=5 tubes, N=6 experiment | STOP report; no independent clean rerun | preserve STOP evidence; do not use as base |
| `research/parameter-semantics-repair-v1` / `cec0b40` | role-dependent detector, typed parameter classes, derived timing/lookahead/diameter helpers | closed loop not yet recomputed; runtime binding remains default-N=6 oriented | fully decentralized, 0 guards | no learned action | mechanical N=5,6,8; experimental N=6 | 633 passed; 0 guards | valid milestone, but lacks decisive regression |
| `research/post-parameter-repair-regression-v1` / `1795809` | all cumulative assets plus frozen detector regression and failure attribution | common commit can expand unsafe outer roles; no readiness phase; no COMPACT; no decentralized learned residual; no N=24 validation | strict deployable path passes; simulation boundary still handles joint environment stepping | old global learned heads preserved; decentralized runtime uses fixed local controller | original stack reaches 24; decentralized mechanics tested 5,6,8 and closed loop only 6 | **665 passed**, 0 guards in this audit | **selected reconstruction base** |

## 5. Tracked and Local Artifact Inventory

### 5.1 Tracked source groups

| Group | Tracked files | Notes |
|---|---:|---|
| `rvt_swarm/` | 41 | original stack plus decentralized package |
| `rvt_swarm/decentralized/` | 18 | system model, radio, ego graph, consensus, epochs, roles, controller, metrics, parameters, guards |
| `tests/` | 42 | 665 collected test cases after parametrization |
| `docs/` | 83 at base; 84 with this audit | protocols, audits, reports, and paper planning |
| `scripts/` | 29 | training, diagnostics, qualifications, and frozen regressions |
| `results/` | 76 | machine-readable and text artifacts, about 12 MiB |
| `checkpoints/` | 3 | documentation markers only; `.pt` files are ignored local artifacts |
| `latex/` | 59 | IEEE Access manuscript, bibliography, figures, class/font support |
| `output/` | 14 | generated diagram TeX/PDF/PNG/Mermaid artifacts |
| `ros2_ws/` | 27 | ROS 2 package source/configuration |

### 5.2 Documentation and reports

The 83 pre-existing documents are preserved, and this repository-base audit is
the 84th document on the Phase 0 branch. Their functional groups are:

- benchmark validity and provenance: `BENCHMARK_BUG_VERIFICATION.md`,
  `EPISODE_METRIC_SPECIFICATION.md`, `EVALUATION_PROTOCOL_V2_VERIFICATION.md`,
  `DATA_SPLIT_AND_CHECKPOINT_PROTOCOL.md`, `CHECKPOINT_SELECTION_V2.md`,
  `TRAINING_BUDGET_PROTOCOL.md`, and `SMOKE_BENCHMARK_PROTOCOL_V2_REPORT.md`;
- method/action evidence: `ARCHITECTURE_EVIDENCE_TABLE.md`,
  `LEARNING_SANITY_AUDIT.md`, `METHOD_AUDIT_V2_REPORT.md`,
  `SIMPLIFIED_MODEL_SPECIFICATION.md`, `DUAL_SUPERVISION_DATA_PROTOCOL.md`,
  `BINARY_MODE_LABEL_GATE_REPORT.md`, and both binary seed-0 reports;
- scenario and label evidence: scenario-family, layout-split, headroom, mode,
  recovery-event V1/V2/V3, and reconfiguration qualification specifications
  and reports;
- decentralization evidence: system model, RobotView/ego-graph audit,
  P2P discovery, role protocol, communication accounting, epoch protocol,
  consensus gates, runtime integration audit, event origination/adoption,
  trigger latching, rearming, and local-controller reports;
- geometry/parameter evidence: Metric V3, KEEP/LINE disjointness,
  forward-sector derivation, lookahead derivation, parameter configuration,
  generality audit, parameter repair, role-dependent detector validation,
  post-repair failure attribution, and post-repair regression;
- manuscript planning: `PRESCREEN_REDESIGN_AUDIT.md`, `PAPER_BLUEPRINT.md`,
  `compare.md`, and `mindset.md`.

Important invalid/superseded documents are retained and labelled by their own
content or tags. They must not be silently used as current evidence.

### 5.3 Tests

The 42 tracked test modules cover:

- episode-wide metrics, collision geometry, randomization, split/seed leakage,
  result schema, timing, model-selection budget, and baseline fidelity;
- original and binary learned models, dataset/runtime compatibility, decisive
  metrics, dense action learning, simplified-model loss, and training budget;
- local ego-graph locality, neighbour discovery, leaderless consensus,
  communication accounting, epochs, confirmation, event adoption/latching,
  no-op suppression, and strict runtime access;
- local pairwise formation geometry, Metric V3, tube disjointness, valid initial
  conditions, reconfiguration state machine, recovery events V2/V3, detector
  scaling, no unexplained constants, and the post-repair regression.

No test currently establishes the full target architecture at N=24. In
particular, there is no test joining N=24 local ego inference, score/intent/
readiness/confirmation rounds, learned residual action, and safety projection.

### 5.4 Result directories

| Result directory | Files | Status/use |
|---|---:|---|
| `binary_mode_pilot/` | 14 | v1/v2 seed-0 diagnostics and frozen labels |
| `decentralized/` | 7 | communication cost and seed-0 selector/runtime diagnostics |
| `decentralized_event_protocol_v3/` | 1 | observability artifact |
| `legacy_pre_metric_fix/` | 1 | invalid legacy metric result |
| `legacy_recovery_event_v1/` | 5 | invalid/superseded recovery event |
| `local_controller_reconfiguration_qualification/` | 1 | first qualification, superseded |
| `local_controller_reconfiguration_qualification_v2/` | 1 | repaired qualification |
| `local_exit_observability_audit/` | 1 | local observability evidence |
| `method_audit/` | 5 | method diagnosis |
| `post_parameter_repair_regression/` | 6 | current frozen N=6 three-cell regression |
| `reconfiguration_width_sweep/` | 1 | width-headroom diagnosis |
| `recovery_event_v2/` | 1 | corrected recovery-event evidence |
| `recovery_propagation_latency/` | 4 | pre-repair propagation evidence |
| `recovery_propagation_latency_repair/` | 1 | repaired comparison |
| `recovery_timing_repair/` | 1 | timing diagnosis |
| `recovery_trigger_timing_repair/` | 1 | trigger repair evidence |
| `scenario_headroom/` | 5 | initial headroom result; invalid label caveat |
| `scenario_headroom_v2/` | 5 | corrected headroom artifacts |
| `smoke_protocol_v2/` | 13 | benchmark smoke and figures |

No result directory is a complete RVT-FD24 publication experiment. The most
recent closed-loop scientific evidence is still N=6.

### 5.5 Manifests and provenance

- `results/post_parameter_repair_regression/experiment_manifest.json` is the
  only immutable experiment manifest with physical, mission, protocol,
  communication, derived, normalized, source, geometry, and seed fields. Its
  content hash is
  `519acb13a79b4ef66fcaa4d1c84e13108265c927f46a848502461b763b3f8b87`.
- `rvt_swarm/provenance.py` stamps source commit, benchmark tag, recovery-event
  version, evaluation schema, dataset version, layout version, and layout hash.
- `results/smoke_protocol_v2/config.yaml` and ROS 2 YAML files are
  configurations, not complete experiment manifests.
- Other JSON files are result payloads or training summaries, not immutable
  run manifests.

There is no complete dataset manifest, checkpoint manifest, final architecture
manifest, or N=24 experiment manifest. Phase 3 must freeze these before new
training.

### 5.6 Checkpoints

Only three checkpoint notices are tracked:

- `checkpoints/binary_mode_pilot_dryrun_v2/ENGINEERING_ARTIFACT.md`;
- `checkpoints/invalid_concurrent_writers/README.md`;
- `checkpoints/legacy_pre_metric_fix/README.md`.

Fifteen ignored local `.pt` files are present and preserved:

| Group/file | SHA-256 | Disposition |
|---|---|---|
| `binary_mode_pilot_dryrun_v2/direct_keep_line_classifier/seed_0/selected.pt` | `0f2f50b641a7a1d77a728232d79bbfb5e06c7267535cc546951efc3038fcd3df` | engineering artifact only |
| `binary_mode_pilot_dryrun_v2/rvt_binary_recovery/seed_0/selected.pt` | `46f37f54852d02b6bf5fbfc845f20d4d1c1ba8746e95e893650fccc52905ed92` | engineering artifact only |
| `binary_mode_pilot_dryrun_v2/topology_agnostic_gnn/seed_0/selected.pt` | `2c189875fd9eb9f0e047d3512b3cf958760a9afeafb5412ad5185486f3709726` | engineering artifact only |
| `method_audit/gnn_only.pt` | `1e40de2708574112ada36aaed22964a637b4b61a52730cb491ac9d900e258cb5` | diagnostic |
| `method_audit/gnn_only_best.pt` | `a675d36745bd54087f31311433f6249501d8b9124988eac5cac7ea122a8a02f0` | diagnostic |
| `method_audit/gnn_only_last.pt` | `49685d18f10989f298e98de8f7df329fc28cc022404420d3d9841bed57cc2cfd` | diagnostic |
| `method_audit/rvt_swarm.pt` | `c3f4366815f9b68d4c135cc7e4242d0dc19f8e05cae60f484a016510842db708` | diagnostic |
| `method_audit/rvt_swarm_best.pt` | `5429418f33397693afcd84ec8b70505d930513d2a5078bf0450d52d73d8ab137` | diagnostic |
| `method_audit/rvt_swarm_last.pt` | `974249c51dc7f6814f071612670acc2eddc57a338cfb962e74931f8ea99c6f45` | diagnostic |
| `smoke_protocol_v2/gnn_only.pt` | `588bc50dbe1ca5f5e45691877294f0822f7479ab932f5864bab014d5476a7cc6` | smoke only |
| `smoke_protocol_v2/gnn_only_best.pt` | `36b528ff0356d720ea461f81ceb1370bc3a7ab98cd6b139285e81083763bb051` | smoke only |
| `smoke_protocol_v2/gnn_only_last.pt` | `85997c0732f644e87fd7dd1ccd803adb42ea825f793aa41ab14d9a630ca2409e` | smoke only |
| `smoke_protocol_v2/rvt_swarm.pt` | `d302f56876f6b358422822b1f9334c775900c54870250b4002a5c4ec8f76814f` | smoke only |
| `smoke_protocol_v2/rvt_swarm_best.pt` | `391aa54875b3d906e3a5a3161888a53a3bb6b9f99ad1f95a48711aa71d0ffb16` | smoke only |
| `smoke_protocol_v2/rvt_swarm_last.pt` | `caae3659017381720c3b274aac47fe1655d82656a909073046417fbdf451dd58` | smoke only |

None is approved as a final RVT-FD24 checkpoint. The binary selected files are
explicitly marked as engineering artifacts, and the method/smoke files predate
the required final architecture and manifest contract.

### 5.7 Manuscript, figures, and tables

- Main manuscript: `latex/access.tex`.
- Bibliography: `latex/bib/references.bib`.
- Main figures: `latex/figures/main/f1.pdf`, `f2.pdf`.
- Result figures: `latex/figures/results/all_trajectories.png`,
  `ablation_trajectories.png`.
- Teaser figures: `latex/figures/teaser/a.png`, `b.png`.
- Generated diagrams under `output/pdf/`: algorithm flowchart, robot deployment
  overview, and system overview in TeX/PDF/PNG; the deployment source also has a
  Mermaid file.
- Tables are embedded directly in `latex/access.tex`; there are no standalone
  generated table artifacts.

The manuscript is legacy evidence, not current truth. It still claims a global
RVT architecture and 2-to-24 results that do not correspond to the current
decentralized runtime. It also contains placeholder publication metadata and
unsupported resilience/performance language. `latex/access.tex` already uses
"safety filter" rather than "shield", but stale terminology remains elsewhere,
including `README.md` and `docs/PAPER_BLUEPRINT.md`. Terminology cleanup is not
performed in Phase 0.

## 6. Required Component Location Map

| Required work | Authoritative location(s) | What exists | Limitation at selected base |
|---|---|---|---|
| Original RVT-Swarm model | `rvt_swarm/models.py`, `train.py`, `policy_runtime.py` | whole-graph backbone, topology consensus/pooling, scores, action bank | runtime is centralized and not the target deployable architecture |
| Original multiple topology implementation | `config.py`, `environment.py`, `controllers.py`, `safety.py` | KEEP, COMPRESS, LINE, SPLIT_HINT, RECOVER; learned persistent set KEEP/LINE/SPLIT_HINT | modes mix structural actions and transition commands; COMPACT is not authoritative in decentralized code |
| Action heads | `models.py` | GNN action head; RVT base plus topology residual; binary base plus mode residual | decentralized selector model explicitly has no action head; LINE learned execution failed |
| Whole-swarm/global graph | `dataset.build_graph_arrays`, `policy_runtime._batch`, `models.pooled_graph_features` | one graph per team, global mean pooling, one team decision | prohibited for target runtime; retained only as legacy/training diagnostic code |
| Local ego graph | `decentralized/ego_graph.py` | 28 audited local features and center-node readout | only KEEP/LINE candidate conditioning |
| Decentralized communication | `decentralized/comms.py`, `comm_cost.py` | one-hop beacons, freshness, loss/delay model, byte accounting | simulator boundary constructs RobotViews from joint state; hardware path not experimentally exercised |
| Leaderless consensus | `decentralized/consensus.py`, `epoch.py` | MH score recursion, trigger max-consensus, min/max confirmation | no readiness-consensus stage; score-round default is not yet FD24-derived |
| Metric V3 | `decentralized/formation_metric_v3.py` | translation-aligned persistent-role `E_inf`, dwell, disjointness certificate | offline only as intended; closed-loop evidence only N=6 |
| Parameter semantics repairs | `decentralized/parameters.py`, `epoch.py`, `runtime.py` | role widths, timing, lookahead, diameter derivations, unsupported-config result | `ConsensusParams.for_protocol` is mentioned but absent; default runtime binding remains N=6-specific |
| Robot-local controller | `decentralized/local_controller.py` | RobotView to one 2-D acceleration with local formation/avoidance terms | fixed hand-coded controller, no learned bounded residual or explicit local safety projection |
| Event-triggered transitions | `decentralized/epoch.py`, integrated by `decentralized/runtime.py` | local entry/recovery events, propagation, score, confirmation, commitment, lifecycle latch | common KEEP commitment can be unsafe for outer roles; no distributed transition-readiness certificate |
| Dense action data | `binary_pilot.build_action_dataset`, `tests/test_dense_action_learning.py` | equal KEEP/LINE expert targets sampled every 2 steps | whole-graph format, N=4/6, no COMPACT, no local residual target contract |
| Recoverability labels | `recovery_v2.py`, `results/binary_mode_pilot/task_recovery_labels.csv`, `decentralized/training.py` | separated gold-standard task recovery and team labels copied to robot ego samples | binary KEEP/LINE labels; not candidate set KEEP/COMPACT/LINE; no final dataset manifest |
| Variable-team-size support | `config.py`, `dataset.py`, `decentralized/roles.py`, `parameters.check_team_size` | original data/model tensors are dynamic; role templates have no fixed-N branch; explicit support checks | decentralized tests cover mechanics mainly N=5/6/8; protocol defaults max N=6 |
| 24-robot support | `EnvConfig.team_sizes`, `splits.TEST_TEAM_SIZES` | original centralized benchmark includes N=24; a Phase-0 mechanical probe can construct roles and widths at N=24 | no decentralized N=24 integration test, training, closed-loop run, bandwidth result, or publication evidence |

### 6.1 N=24 mechanical probe

Without loading layouts or running a scientific episode, the audit constructed
`RoleAssignment.from_index(24, 0.9)` and evaluated
`check_team_size(..., ProtocolParams(max_team_size=24))`. It returned supported,
with `delta_N=8.7958`, `k_trigger=23`, and role widths from 0.55 m to 2.35 m,
within the 3.0 m obstacle range.

This is only evidence that the current role/geometry helper can represent N=24.
It is not evidence that the deployed protocol, controller, learned model, or
closed loop works at N=24.

## 7. Reconstruction Blockers and Risks

1. **Topology scope mismatch.** The original model has KEEP/LINE/SPLIT_HINT;
   the decentralized runtime has KEEP/LINE; the intended primary set is
   KEEP/COMPACT/LINE. COMPACT lacks an authoritative role generator, local
   controller qualification, transition envelopes, and headroom evidence.
2. **No decentralized learned action path.** The local selector outputs only
   candidate scores. The deployed local controller is fixed. The old learned
   action bank is global, and its LINE head failed every forced-LINE closed-loop
   episode in the binary pilot.
3. **No transition-readiness agreement.** The post-repair detector is locally
   correct, but centre evidence can authorize simultaneous expansion while outer
   roles remain wall-constrained. The branch named `distributed-safe-expansion`
   contains an audit STOP, not an implemented certificate.
4. **No robot-local safety projection.** Local avoidance exists inside the
   controller, but the intended final pipeline's explicit per-robot projection
   and its guarantee/fallback semantics do not.
5. **Parameter wiring is not yet FD24-complete.** Derivation helpers support a
   configured diameter, but runtime `ConsensusParams` defaults remain the N=6
   values, `k_score` is fixed at 4, and the documented `for_protocol` constructor
   does not exist.
6. **N=24 is legacy evaluation scope, not decentralized evidence.** No current
   local-runtime closed-loop result exists beyond N=6.
7. **Training assets are not final.** Existing labels/actions cover binary modes
   and N=4/6; all local checkpoints are diagnostic or engineering artifacts.
8. **Provenance is incomplete for future training.** There is no immutable
   dataset/checkpoint/final-architecture manifest yet.
9. **Manuscript and results are stale.** They mix original centralized claims,
   invalid/superseded artifacts, and later decentralized negative evidence.
10. **Repository hygiene debt exists.** Unreachable and temporary Git objects
    should be archived or cleaned only after explicit approval.

## 8. Verification at the Selected Base

Run from the clean selected-base checkout before this documentation-only change:

```text
.venv/bin/python -m pytest tests -q
665 passed, 1 warning in 44.84s

strict_decentralized_runtime = True
guards.audit() violations = 0

.venv/bin/python -m pytest \
  tests/test_no_central_runtime_access.py \
  tests/test_no_unexplained_runtime_constants.py -q
24 passed in 2.58s

git fsck --full --no-reflogs
exit 0; no corrupt or missing reachable object
```

The single warning is in a test assertion converting a gradient-bearing tensor
to `float`; it does not indicate a runtime failure.

## 9. Phase 0 Gate

Phase 0 is complete when this audit is committed and the same full-suite and
strict-guard checks pass from the clean Phase-0 commit.

No Phase 1 system-model edit, new topology, readiness protocol, learned residual,
training run, final-test evaluation, or manuscript rewrite is authorized before
approval of the selected base.
