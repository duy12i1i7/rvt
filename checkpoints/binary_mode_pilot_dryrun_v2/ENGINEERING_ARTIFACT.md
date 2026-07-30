# Engineering artifacts — not scientific results

Every checkpoint under this directory, and under
`checkpoints/binary_mode_pilot_v1/`, is an **engineering artifact**. None may be
used for a scientific comparison or reported as a result.

## Learned action heads are excluded

The learned **line** action head failed closed-loop execution: 0.000 task
recovery against the expert controller's 1.000 on the same episodes, while the
learned *keep* head reached 0.300–0.550 against the expert's 0.450. The failure
is localised to the line head, not to the harness — mean action magnitude tracks
the expert (ratio 0.948–1.019) and the same runtime path yields 0.550 under
forced keep. See `docs/BINARY_MODE_SEED0_DRY_RUN_V2.md` §6.1.

The decentralized system therefore uses a **fixed** robot-local mode-conditioned
controller and no learned action head. That controller executes both modes:
keep 0.700 and line 1.000, versus the centralized reference's 0.450 and 1.000
(`results/decentralized/gate_d5_local_controller.txt`).

## The centralized global selector is retained as a diagnostic reference only

`rvt_binary_recovery` and `direct_keep_line_classifier` pool over the whole-swarm
graph (`models.RVTBinaryRecoveryPolicy` calls `pooled_graph_features` over
`batch_index`, producing one logit per team). They are **not deployable** and
must never be presented as such. They exist to bound how much is lost by
restricting inference to ego graphs.
