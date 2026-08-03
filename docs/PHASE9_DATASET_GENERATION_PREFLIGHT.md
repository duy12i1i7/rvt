# Phase 9 Dataset Generation Preflight

## Result

Preflight passes. The approved Phase 8 source is
`c17081fe1cf58cc2d3f929e35ff4bca811c75c58`, tagged
`rvt-experiment-protocol-v1`. The active branch is
`research/rvt-phase9-dataset-generation-v1`.

The protocol schema is `rvt-experiment-protocol/v1` and its canonical hash is
`0bb68dd56ef0837f83c44dcf5281498f8c0ea934b00bbb9b3d3f298264d32147`.
The machine-readable audit is
`results/rvt_fd24/datasets/phase9_preflight_audit.json`.

## Frozen Boundary

| item | approved value | result |
|---|---|---|
| train split | `a2a7257ae09d244f21224bd89b18ba32f7cd1457627f54d3b898cc83be2e9a35` | pass |
| validation split | `cff73ce294f16f557af783fbabee20cd89a2f929878f7b80122265f481c58d7f` | pass |
| sealed final-test commitment | `e225a3114dfb2d74e8a691f24484898de1481a6f8f243bcc3eabbfba5aff8d0f` | pass, commitment only |
| online topology scope | `bc65ec533c895a9ad82ef277e89998c772db3403d4177ec04d9dce375f0c7684` | pass |
| candidates | COMPACT `5`, LINE `2` | pass |
| transition graph | COMPACT to LINE and LINE to COMPACT | pass |
| ego-graph schema | `rvt-ego-graph/v2` | pass |
| ego feature hash | `1ea52c6aebb23360641ce6a09ef41d2d21fd372f2744f196b91ff184a1a2cf5b` | pass |
| model schema | `rvt-fd24-model/v1` | pass |
| model config hash | `44cc7176a38e79d938952398ccb08d7fe2646643ddfe6dec08822a60de9fb1a3` | pass |
| seed namespace contract | `6a13281db6d4a2195ff4a73809986f173249c657fbaedda14b85ded16e0c2b3f` | pass |

All six team-size runtime hashes reproduce exactly. These hashes cover the
frozen controller, safety and transition-protocol configuration. Every hashed
Phase 8 protocol document, including the mechanical scope, target definitions,
loss contract and final-test guard, also reproduces exactly.

## Final-Test Guard

The preflight loader opens only the train and validation split manifests. It
does not open `final_test_layouts.sealed.json`; it compares the approved final
hash commitment already present in the experiment-protocol manifest. The access
audit contains one initialization entry, zero admitted entries and zero
successful runtime accesses.

## Gate Boundary

Phase 9A passes. Dataset generation is nevertheless not authorized because the
independent Phase 9C generation-budget completeness gate fails as documented in
`PHASE9_DATASET_REPORT.md`. A valid preflight does not fill missing scientific
budget declarations.
