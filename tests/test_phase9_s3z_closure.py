from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import sha256_document
from scripts.check_phase9_s3z_recoverability_readiness import validate


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


@pytest.mark.parametrize(
    ("name", "field"),
    [
        (
            "phase9_s3_centerline_population_requalification_v1.json",
            "phase9_s3_centerline_population_requalification_closure_sha256",
        ),
        (
            "phase9_s3_existing_data_requalification_v2.json",
            "phase9_s3_existing_data_requalification_closure_sha256",
        ),
        (
            "phase9_s3_centerline_replay_v1.json",
            "phase9_s3_centerline_replay_sha256",
        ),
        (
            "phase9_s3_final_resume_readiness_v1.json",
            "phase9_s3_final_resume_readiness_sha256",
        ),
        (
            "phase9_current_generation_provenance_v3.json",
            "phase9_current_generation_provenance_v3_sha256",
        ),
        (
            "phase9_generation_readiness_v5.json",
            "phase9_generation_readiness_v5_sha256",
        ),
    ],
)
def test_s3z_closure_artifact_has_valid_canonical_hash(
    name: str, field: str
) -> None:
    document = json.loads((RESULTS / name).read_text(encoding="ascii"))
    body = dict(document)
    expected = body.pop(field)
    assert sha256_document(body) == expected


def _readiness() -> dict:
    return json.loads(
        (RESULTS / "phase9_s3_final_resume_readiness_v1.json").read_text(
            encoding="ascii"
        )
    )


def test_s3z_prestart_guard_passes_without_granting_authorization() -> None:
    document = _readiness()
    validate(document)
    assert document["official_resume_authorized_now"] is False
    assert document["official_resume_performed"] is False


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("missing_side_unresolved", "S3_MISSING_OPPOSING_SIDE_UNDERSPECIFIED"),
        ("tie_unresolved", "S3_SUPPORT_TIE_UNDERSPECIFIED"),
    ],
)
def test_s3z_prestart_guard_fails_closed(field: str, code: str) -> None:
    document = copy.deepcopy(_readiness())
    document["population_guard"][field] = 1
    with pytest.raises(RuntimeError, match=code):
        validate(document)
