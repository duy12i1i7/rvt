"""Task 4R-2 — KEEP/LINE separation under the exact V3 metric.

The condition `delta_N > 2*epsilon_form` is necessary AND sufficient, so a
failure is certified by an explicit configuration lying in both tubes, not by a
bound that merely was not met.
"""
from __future__ import annotations

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized.formation_metric_v3 import (
    EPSILON_FORM, delta_n, e_inf, in_keep_tube, in_line_tube,
    midpoint_configuration, separation_report,
)
from rvt_swarm.decentralized.roles import RoleAssignment
from rvt_swarm.decentralized.system_model import KEEP, LINE

SPACING = Config().env.nominal_spacing
MD = (1.0, 0.0)
SEPARATED = (6,)              # the only N certified disjoint
NOT_SEPARATED = (3, 4)


def roles(n):
    return RoleAssignment.from_index(n, SPACING)


# --- the measured values, pinned ------------------------------------------
@pytest.mark.parametrize("n,expected", [(3, 0.6708), (4, 1.0062), (6, 2.0125)])
def test_delta_n_values(n, expected) -> None:
    assert delta_n(roles(n)) == pytest.approx(expected, abs=1e-4)


def test_threshold_is_two_epsilon_and_epsilon_is_unchanged() -> None:
    assert EPSILON_FORM == 0.55
    assert 2 * EPSILON_FORM == pytest.approx(1.10)


# --- N = 6 is separated ----------------------------------------------------
@pytest.mark.parametrize("n", SEPARATED)
def test_separated_sizes_pass_the_condition(n) -> None:
    assert delta_n(roles(n)) > 2 * EPSILON_FORM


@pytest.mark.parametrize("n", SEPARATED)
def test_separated_sizes_have_no_configuration_in_both_tubes(n) -> None:
    """The midpoint construction -- the best possible candidate -- fails."""
    r = roles(n)
    mid = midpoint_configuration(r, MD)
    assert not (in_keep_tube(mid, r, MD) and in_line_tube(mid, r, MD))


@pytest.mark.parametrize("n", SEPARATED)
def test_separated_sizes_reject_exact_templates_of_the_other_mode(n) -> None:
    r = roles(n)
    from rvt_swarm.decentralized.roles import rotation
    R = rotation(MD).astype(np.float64)
    for mode, other in ((KEEP, LINE), (LINE, KEEP)):
        T = np.asarray(r.coords(mode), dtype=np.float64)
        pos = (R @ (T - T.mean(0)).T).T
        assert e_inf(pos, r, mode, MD) == pytest.approx(0.0, abs=1e-9)
        assert e_inf(pos, r, other, MD) > EPSILON_FORM


# --- N = 3 and N = 4 are NOT separated: constructive certificate -----------
@pytest.mark.parametrize("n", NOT_SEPARATED)
def test_unseparated_sizes_fail_the_condition(n) -> None:
    assert delta_n(roles(n)) <= 2 * EPSILON_FORM


@pytest.mark.parametrize("n", NOT_SEPARATED)
def test_unseparated_sizes_admit_a_configuration_in_BOTH_tubes(n) -> None:
    """Certificate of failure: this configuration is simultaneously KEEP and LINE.

    Its existence is why N=3 and N=4 are excluded from the reconfiguration
    study. `always_line` could satisfy the nominal-recovery requirement without
    ever leaving line, which is exactly the vacuity the V2 task exists to
    remove.
    """
    r = roles(n)
    mid = midpoint_configuration(r, MD)
    assert in_keep_tube(mid, r, MD), e_inf(mid, r, KEEP, MD)
    assert in_line_tube(mid, r, MD), e_inf(mid, r, LINE, MD)
    # the certificate is a legitimate configuration: offsets sum to zero
    assert np.allclose(mid.mean(axis=0), 0.0, atol=1e-9)


# --- boundary perturbations ------------------------------------------------
def test_boundary_perturbation_at_exactly_epsilon_is_inside() -> None:
    r = roles(6)
    from rvt_swarm.decentralized.roles import rotation
    R = rotation(MD).astype(np.float64)
    T = np.asarray(r.coords(KEEP), dtype=np.float64)
    pos = (R @ (T - T.mean(0)).T).T
    n = len(pos)
    # displace one robot so its own error is exactly epsilon
    d = EPSILON_FORM / (1 - 1 / n)
    pos[0] = pos[0] + np.array([d, 0.0])
    assert e_inf(pos, r, KEEP, MD) == pytest.approx(EPSILON_FORM, abs=1e-9)
    assert in_keep_tube(pos, r, MD)


def test_boundary_perturbation_just_beyond_epsilon_is_outside() -> None:
    r = roles(6)
    from rvt_swarm.decentralized.roles import rotation
    R = rotation(MD).astype(np.float64)
    T = np.asarray(r.coords(KEEP), dtype=np.float64)
    pos = (R @ (T - T.mean(0)).T).T
    n = len(pos)
    d = (EPSILON_FORM + 1e-6) / (1 - 1 / n)
    pos[0] = pos[0] + np.array([d, 0.0])
    assert not in_keep_tube(pos, r, MD)


def test_separation_report_matches_the_individual_computations() -> None:
    rep = separation_report(SPACING, (3, 4, 6))
    for n in (3, 4, 6):
        assert rep[n]["delta_n"] == pytest.approx(delta_n(roles(n)))
        assert rep[n]["disjoint"] is (delta_n(roles(n)) > 2 * EPSILON_FORM)
    assert rep[6]["disjoint"] and not rep[4]["disjoint"] and not rep[3]["disjoint"]
