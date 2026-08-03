# RVT-FD24 Split Contract

Schema `rvt-layout-split/v1` freezes 20 train layouts, 10 validation layouts and
10 sealed final-test layouts across all ten scenario families. Train has two
canonical variants per family; validation and final test each have one held-out
variant. Split membership is deterministic under `rvt-seed-namespaces/v1` and
geometry generator `rvt-compact-line-geometry/v1`.

Disjointness requires both geometry SHA-256 and canonical-parameter-tuple
SHA-256 to be unique across splits. Validation/final profiles use held-out
widths, offsets, curvature amplitudes, bottleneck sequences, bypass parameters,
dynamic paths and communication schedules; different random seeds alone are
not considered geometric separation.

Artifacts are:

- `results/rvt_fd24/splits/train_layouts.json`
- `results/rvt_fd24/splits/validation_layouts.json`
- `results/rvt_fd24/splits/final_test_layouts.sealed.json`

The final manifest is stored separately and marked sealed. Normal split loaders
reject its filename and split identity. Final geometry enumeration requires the
split-freeze qualification path; experiment access additionally requires the
one-time final-test gate. That gate verifies the method-freeze manifest and SHA,
the three-seed pilot manifest and SHA with a permitting verdict, an explicit
single-use authorization ID and an existing audit log. Training and validation
orchestration may load only the first two manifests.

Each manifest records count, family distribution, headroom distribution,
team-size distribution, geometry hashes, parameter hashes and its canonical
manifest hash. Reports may expose only final count, family distribution,
team-size distribution and manifest hash. Dynamic/communication seeds are
split-namespaced and cannot reproduce an episode across splits.
