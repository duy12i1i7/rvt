import pytest

from rvt_swarm.decentralized.local_projection_forensics import (
    action_primal_residual,
    independent_local_feasibility,
)
from rvt_swarm.decentralized.local_control_types import LocalConstraintDiagnostic


def _constraint(normal, lower, key="peer:1"):
    return LocalConstraintDiagnostic(
        source_key=key,
        threat_kind="peer",
        outward_normal=normal,
        lower_bound_meters_per_second_squared=lower,
        current_distance_meters=0.5,
        required_clearance_meters=0.4,
        stale_or_uncertain=False,
        active_for_proposed_action=True,
    )


def test_independent_oracle_proves_single_half_space_exceeds_disk_support():
    result = independent_local_feasibility((_constraint((1.0, 0.0), 0.61),), 0.6)
    assert result.classification == "B_independently_infeasible"
    assert result.feasible is False
    assert result.proof_kind == "single_half_space_exceeds_disk_support"
    assert result.proof_constraint_keys == ("peer:1",)


def test_independent_oracle_finds_minimum_norm_feasible_witness():
    constraints = (
        _constraint((1.0, 0.0), 0.2, "peer:left"),
        _constraint((0.0, 1.0), 0.3, "peer:below"),
    )
    result = independent_local_feasibility(constraints, 0.6)
    assert result.classification == "A_independently_feasible"
    assert result.feasible is True
    assert result.witness_action == pytest.approx((0.2, 0.3))
    assert action_primal_residual(result.witness_action, constraints, 0.6) == 0.0


def test_independent_oracle_rejects_malformed_normal():
    result = independent_local_feasibility((_constraint((0.0, 0.0), 0.1),), 0.6)
    assert result.classification == "D_malformed_constraint_system"
    assert result.feasible is None
