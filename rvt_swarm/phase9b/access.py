"""Study A N=24 zero-shot evaluation sealing contract."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


ZERO_SHOT_PURPOSE = "zero_shot_size_evaluation_only"
PROHIBITED_PURPOSES = (
    "training",
    "validation",
    "early_stopping",
    "hyperparameter_search",
    "checkpoint_selection",
)


class StudyAN24AccessError(PermissionError):
    """Study A N=24 was requested before its checkpoint-selection boundary."""


@dataclass(frozen=True)
class N24EvaluationAuthorization:
    frozen_study_a_checkpoint_sha256: str
    validation_selection_audit_sha256: str
    explicit_zero_shot_evaluation_authorization: bool


def require_study_a_n24_access(
    *,
    purpose: str,
    authorization: N24EvaluationAuthorization,
    access_log: Path,
) -> None:
    admitted = (
        purpose == ZERO_SHOT_PURPOSE
        and len(authorization.frozen_study_a_checkpoint_sha256) == 64
        and len(authorization.validation_selection_audit_sha256) == 64
        and authorization.explicit_zero_shot_evaluation_authorization
    )
    event = {
        "schema_version": "rvt-study-a-n24-access/v1",
        "purpose": purpose,
        "authorization": asdict(authorization),
        "admitted": admitted,
    }
    access_log.parent.mkdir(parents=True, exist_ok=True)
    with access_log.open("a", encoding="ascii") as stream:
        stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
    if not admitted:
        raise StudyAN24AccessError(
            "Study A N=24 requires a frozen checkpoint, completed validation "
            "selection audit, explicit authorization, and evaluation-only purpose"
        )
