import pytest

from rvt_swarm.decentralized.phase7_qualification import (
    PHASE7_CONSTRICTION_FIXTURES,
    run_phase7_constriction_fixture,
)


@pytest.mark.parametrize("fixture", PHASE7_CONSTRICTION_FIXTURES)
def test_all_predeclared_constriction_fixtures(fixture):
    result = run_phase7_constriction_fixture(fixture)
    assert result.false_safe_count == 0
    assert not result.premature_commitment
    assert result.collision_free
    assert result.no_op_epoch_count == 0
    assert result.mode_epoch_count in (0, 1)


def test_historical_centre_safe_outer_constrained_defect_is_blocked():
    result = run_phase7_constriction_fixture("centre_ready_before_outer")
    assert all(result.initial_states[robot_id] == "SAFE"
               for robot_id in result.centre_robot_ids)
    assert all(result.initial_states[robot_id] == "UNSAFE"
               for robot_id in result.constrained_robot_ids)
    assert not result.initial_all_ready
    assert not result.committed
    assert result.mode_epoch_count == 0


def test_safe_widening_proceeds_after_all_outer_roles_become_ready():
    result = run_phase7_constriction_fixture("all_roles_eventually_ready")
    assert not result.initial_all_ready
    assert result.final_all_ready
    assert result.committed
    assert result.mode_epoch_count == 1


def test_infeasible_and_incomplete_fixtures_abort_without_epoch():
    for fixture in ("no_feasible_transition_window", "incomplete_local_sensing"):
        result = run_phase7_constriction_fixture(fixture)
        assert result.timed_out_or_aborted
        assert not result.committed
        assert result.mode_epoch_count == 0
