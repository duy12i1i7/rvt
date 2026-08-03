from rvt_swarm.phase8.contracts import (
    CHECKPOINT_SELECTION_SCHEMA_VERSION,
    CheckpointSelectionContract,
)


def test_checkpoint_selection_is_validation_closed_loop_and_safety_constrained():
    contract = CheckpointSelectionContract()
    assert contract.schema_version == CHECKPOINT_SELECTION_SCHEMA_VERSION
    assert contract.minimum_closed_loop_validation_episodes == 120
    assert contract.collision_free_point_estimate_floor == 0.95
    assert contract.primary_order[:3] == (
        "collision_constraint_satisfied",
        "episode_task_success_maximized",
        "recoverability_Brier_score_minimized",
    )


def test_training_loss_and_zero_shot_n24_cannot_select_checkpoint():
    contract = CheckpointSelectionContract()
    assert "training" not in " ".join(contract.primary_order).lower()
    assert contract.zero_shot_n24_handling == "never_used_for_checkpoint_selection"


def test_residual_variants_are_selected_separately_before_h4_gate():
    contract = CheckpointSelectionContract()
    assert contract.residual_variant_handling == "separate_pool_then_H4_paired_validation_gate"
    assert contract.failed_run_handling == "ineligible_and_reported"
