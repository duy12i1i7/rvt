import json
from dataclasses import replace
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import file_sha256
from rvt_swarm.phase8.final_test_guard import (
    PERMITTED_PILOT_VERDICT,
    PERMITTED_PURPOSE,
    FinalTestAuthorization,
    evaluate_final_test_authorization,
    guarded_read_json,
    scan_source_for_final_test_access,
)


ROOT = Path(__file__).resolve().parents[1]


def _authorization(
    method_freeze_path="results/rvt_fd24/method_freeze.json",
    pilot_path="results/rvt_fd24/three_seed_pilot.json",
    **changes,
):
    values = {
        "method_freeze_manifest_path": str(method_freeze_path),
        "method_freeze_manifest_sha256": "a" * 64,
        "three_seed_pilot_manifest_path": str(pilot_path),
        "three_seed_pilot_manifest_sha256": "b" * 64,
        "three_seed_pilot_verdict": PERMITTED_PILOT_VERDICT,
        "authorization_id": "one-time-final-001",
        "one_time": True,
        "purpose": PERMITTED_PURPOSE,
    }
    values.update(changes)
    return FinalTestAuthorization(**values)


def test_official_final_test_runtime_access_count_is_zero():
    lines = (
        ROOT / "results/rvt_fd24/final_test_access_audit.jsonl"
    ).read_text(encoding="ascii").splitlines()
    records = [json.loads(line) for line in lines if line]
    assert sum(item.get("admitted") is True for item in records) == 0


def test_access_requires_every_frozen_gate(tmp_path):
    audit = tmp_path / "audit.jsonl"
    audit.write_text("", encoding="ascii")
    method_freeze = tmp_path / "method_freeze.json"
    method_freeze.write_text("{}", encoding="ascii")
    pilot = tmp_path / "pilot.json"
    pilot.write_text("{}", encoding="ascii")
    valid = _authorization(
        method_freeze,
        pilot,
        method_freeze_manifest_sha256=file_sha256(method_freeze),
        three_seed_pilot_manifest_sha256=file_sha256(pilot),
    )
    assert not evaluate_final_test_authorization(None, audit).admitted
    assert not evaluate_final_test_authorization(
        _authorization(method_freeze_manifest_path=""), audit
    ).admitted
    assert not evaluate_final_test_authorization(
        replace(valid, three_seed_pilot_verdict="BLOCK"), audit
    ).admitted
    assert not evaluate_final_test_authorization(
        replace(valid, purpose="checkpoint_selection"), audit
    ).admitted
    assert not evaluate_final_test_authorization(
        replace(valid, one_time=False), audit
    ).admitted


def test_one_time_authorization_is_consumed_and_audited_on_temporary_fixture(tmp_path):
    sealed = tmp_path / "final_test_fixture.sealed.json"
    sealed.write_text('{"ok": true}', encoding="ascii")
    audit = tmp_path / "audit.jsonl"
    audit.write_text("", encoding="ascii")
    method_freeze = tmp_path / "method_freeze.json"
    method_freeze.write_text('{"frozen": true}', encoding="ascii")
    pilot = tmp_path / "pilot.json"
    pilot.write_text('{"verdict": "PERMIT_FINAL_EVALUATION"}', encoding="ascii")
    authorization = _authorization(
        method_freeze,
        pilot,
        method_freeze_manifest_sha256=file_sha256(method_freeze),
        three_seed_pilot_manifest_sha256=file_sha256(pilot),
    )
    assert guarded_read_json(sealed, authorization, audit) == {"ok": True}
    with pytest.raises(PermissionError, match="already been consumed"):
        guarded_read_json(sealed, authorization, audit)


def test_static_guard_detects_all_forbidden_training_access_shapes():
    source = '''
import sealed_final_test_module
path = "results/final_test/layout.json"
guarded_read_json(path, auth, audit)
generate_layouts("final_test")
select_checkpoint_from_final_test(results)
'''
    issues = scan_source_for_final_test_access(source)
    assert any(item.startswith("sealed_import") for item in issues)
    assert any(item.startswith("sealed_literal") for item in issues)
    assert any("guarded_read_json" in item for item in issues)
    assert any("generate_layouts" in item for item in issues)
    assert any("select_checkpoint" in item for item in issues)


def test_existing_training_sources_have_no_sealed_access():
    for path in (
        ROOT / "rvt_swarm/train.py",
        ROOT / "rvt_swarm/decentralized/training.py",
    ):
        assert scan_source_for_final_test_access(path.read_text(encoding="utf-8")) == ()
