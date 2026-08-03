# Phase 9B Generation Budget Contract

## Identity

This addendum is separate from and does not modify the immutable Phase 8
protocol. Its schema is `rvt-generation-budget/v1` and its canonical hash is
`3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e`.

It binds:

- Phase 8 source `c17081fe1cf58cc2d3f929e35ff4bca811c75c58`;
- Phase 8 protocol `0bb68dd56ef0837f83c44dcf5281498f8c0ea934b00bbb9b3d3f298264d32147`;
- online scope `bc65ec533c895a9ad82ef277e89998c772db3403d4177ec04d9dce375f0c7684`;
- train split `a2a7257ae09d244f21224bd89b18ba32f7cd1457627f54d3b898cc83be2e9a35`;
- validation split `cff73ce294f16f557af783fbabee20cd89a2f929878f7b80122265f481c58d7f`;
- sealed final-test commitment `e225a3114dfb2d74e8a691f24484898de1481a6f8f243bcc3eabbfba5aff8d0f`.

Every future dataset must carry both the Phase 8 protocol hash and this
generation-budget hash.

## Exact Budget

| dataset | cells | episodes | events | candidate-replica rollouts | recoverability rows | dense rows |
|---|---:|---:|---:|---:|---:|---:|
| Study A train | 100 | 1,200 | 6,000 | 16,800 | 112,800 | 200,000 |
| Study A validation | 50 | 300 | 1,500 | 4,200 | 28,200 | 40,000 |
| Study A N=24 evaluation | 10 | 60 | 300 | 840 | 14,400 | 8,000 |
| Study B train | 120 | 1,200 | 6,000 | 16,800 | 142,000 | 240,000 |
| Study B validation | 60 | 360 | 1,500 | 4,200 | 35,500 | 48,000 |
| **total** | **340** | **3,120** | **15,300** | **42,840** | **332,900** | **536,000** |

The ten families receive equal event counts within every dataset: respectively
600, 150, 30, 600 and 150 events per family in the table order. Both candidates
are evaluated. F8/F9 use three matched replicas and all-success aggregation;
F1-F7/F10 use one replica.

## Dense Quotas

Study A train and Study B train use 2,000 rows per layout/team cell. Study A
validation, Study A N=24 evaluation and Study B validation use 800. Candidate
rows are first enumerated by episode, timestep, robot, topology and graph
fingerprint. A deterministic identity-only hash rank selects without replacement.

The rank cannot inspect residual magnitude, expert improvement, safety
intervention, labels, success or scenario outcome. A quota shortfall is retained
and reported; it does not create replacement episodes or duplicate rows.

## Immutability

Family, team-size, source, event and dense allocations cannot change after label
observation. The original blocked audit remains at
`results/rvt_fd24/datasets/phase9_generation_budget.json`; it is readable but
does not authorize generation.
