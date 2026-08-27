"""CR-1Q §8: production-driver completeness qualification."""
from __future__ import annotations

import pathlib, subprocess
import pytest

from rvt_swarm.cleanroom.generation.driver_contract import (
    DriverContractError, REQUIRED_STAGE_B_CALL, assert_production_driver_complete,
)

DRIVER = pathlib.Path("scripts/cleanroom/cr1_generate_train_r.py")
FINAL = DRIVER.read_text()
STAGE_A_ONLY_COMMIT = "d170ff925e5771b17f60f10ad838a8242a48d543"


def test_final_production_driver_passes_completeness():
    assert_production_driver_complete(FINAL)


def test_regression_stage_a_only_driver_fails_qualification():
    """The exact quarantined Stage-A-only driver must never qualify again."""
    src = subprocess.run(["git", "show", f"{STAGE_A_ONLY_COMMIT}:{DRIVER}"],
                         capture_output=True, text=True).stdout
    assert src and REQUIRED_STAGE_B_CALL not in src
    with pytest.raises(DriverContractError) as e:
        assert_production_driver_complete(src)
    assert "Stage-A only" in str(e.value)


def test_fixture_driver_missing_stage_a_fails():
    """A driver that never acquires a source episode cannot qualify."""
    src = FINAL.replace("execute_v2_source_acquisition", "some_other_acquisition")
    with pytest.raises(DriverContractError) as e:
        assert_production_driver_complete(src)
    assert "Stage-A" in str(e.value)


@pytest.mark.parametrize("literal", [
    "1200", "[5, 6, 8, 12, 16]", "S0_SCRIPTED_DIAGNOSTIC", "episodes_per_cell = 4",
])
def test_fixture_embedded_scientific_constant_fails(literal):
    with pytest.raises(DriverContractError):
        assert_production_driver_complete(FINAL + f"\nBAD = {literal!r}\n")


def test_final_driver_carries_no_scientific_constant():
    for bad in ("1200", "[5, 6, 8, 12, 16]", "S0_SCRIPTED_DIAGNOSTIC"):
        assert bad not in FINAL, bad


def test_final_driver_calls_the_complete_frozen_path():
    for required in ("execute_v2_source_acquisition",
                     "compile_recoverability_v2_candidate_tasks",
                     "produce_recoverability_event"):
        assert required in FINAL, required
