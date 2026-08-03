"""Invalid generation remains distinct from legitimate task failure."""

from rvt_swarm.phase9b.policy import recoverability_emission, residual_emission


def test_invalid_candidate_pair_emits_no_rows_and_keeps_denominator():
    result = recoverability_emission(
        both_candidate_groups_executed=True,
        every_required_replica_present=False,
        rollout_matching_valid=True,
        ego_graphs_valid=True,
        provenance_complete=True,
        task_succeeded=False,
    )
    assert result.pair_valid is False
    assert result.emit_training_records is False
    assert result.label is None
    assert result.preserve_failure_traces is True
    assert result.retain_audit_denominator is True
    assert result.replacement_event is False


def test_valid_task_failure_is_a_legitimate_negative_label():
    result = recoverability_emission(
        both_candidate_groups_executed=True,
        every_required_replica_present=True,
        rollout_matching_valid=True,
        ego_graphs_valid=True,
        provenance_complete=True,
        task_succeeded=False,
    )
    assert result.pair_valid is True
    assert result.emit_training_records is True
    assert result.label == 0


def test_invalid_residual_expert_preserves_audit_sample_without_replacement():
    result = residual_emission(expert_feasible_and_valid=False)
    assert result.emit_training_record is False
    assert result.preserve_base_sample_and_failure is True
    assert result.retain_expert_invalid_denominator is True
    assert result.replacement_sample is False
