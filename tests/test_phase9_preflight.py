"""Phase 9A approved-boundary verification."""

from pathlib import Path

from rvt_swarm.phase9.preflight import build_preflight_audit


ROOT = Path(__file__).resolve().parents[1]


def test_phase9_preflight_passes_every_approved_hash_check():
    audit = build_preflight_audit(ROOT)
    assert audit["status"] == "PASS"
    assert all(item["passed"] for item in audit["checks"])


def test_phase9_preflight_does_not_load_final_test_geometry(monkeypatch):
    original = Path.read_text

    def guarded_read(path, *args, **kwargs):
        if path.name == "final_test_layouts.sealed.json":
            raise AssertionError("sealed final-test geometry was opened")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    audit = build_preflight_audit(ROOT)
    assert audit["final_test_geometry_loaded"] is False
    assert audit["status"] == "PASS"


def test_phase9_preflight_observes_zero_final_test_runtime_access():
    access = build_preflight_audit(ROOT)["final_test_access"]
    assert access["admitted_entry_count"] == 0
    assert access["successful_runtime_access_count"] == 0
