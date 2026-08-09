"""RB21P operational numerical profile and frozen-layout authority guards."""

from __future__ import annotations

import pathlib

import torch

from rvt_swarm.phase9c_rb21p import audit_fd24_cuda_forward


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_fd24_numeric_profile_is_operational_and_does_not_relax_guards() -> None:
    dockerfile = (ROOT / "docker/generation/Dockerfile").read_text(encoding="ascii")
    isolation = (
        ROOT / "tests/test_fd24_model_batch_isolation.py"
    ).read_text(encoding="ascii")
    assert "MKL_CBWR=COMPATIBLE" in dockerfile
    assert (
        "RVT_FD24_NUMERICAL_EXECUTION_PROFILE="
        "FD24_NUMERICAL_EXECUTION_PROFILE_V1"
    ) in dockerfile
    assert isolation.count("atol=1e-7") == 4
    assert "atol=1.2e-7" not in isolation
    assert "atol=1e-6" not in isolation


def test_heading_cache_has_no_phase9_runtime_consumer() -> None:
    runtime = ROOT / "rvt_swarm/phase9c_rb"
    consumers = [
        path for path in runtime.rglob("*.py")
        if "heading_radians" in path.read_text(encoding="ascii")
    ]
    assert consumers == []


def test_cuda_forward_diagnostic_is_observational_when_cuda_is_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 0)
    result = audit_fd24_cuda_forward(ROOT)
    assert result["authority"] == "TEST_ONLY_NON_AUTHORITATIVE"
    assert result["scientific_execution_path_changed"] is False
    assert result["status"] == "CUDA_UNAVAILABLE"
