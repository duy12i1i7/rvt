"""Stage-5B mechanical qualification, run from inside the training image.

Everything here is qualification, not science: synthetic mechanical fits with
seed 0, a read-only structural census of official TRAIN, and explicit proof that
the fail-closed guards refuse what they are supposed to refuse.

It never optimizes official data, never fits the official M0 value, never trains
a frozen scientific seed, and never opens VALIDATION records.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
from typing import Any, Dict, Mapping

import torch

from ..fd24.loader_v3 import load_v3_event_groups
from ..phase8.common import attach_canonical_hash
from . import authorization, driver, m0, synthetic
from .authority import (
    M1_INPUT_CONTRACT_V1_SHA256, M2_MODEL_CONFIG_SHA256,
    OFFICIAL_V3_TRAIN_SEAL_ROOT, OFFICIAL_V3_VALIDATION_SEAL_ROOT,
    PREREGISTRATION_V1_SHA256, TRAIN_INTERNAL_FOLD_MANIFEST_V1_SHA256,
    FAMILY_SELECTION_RULE_V1_SHA256, load_open_loop_v3_authority,
)
from .envelope import (
    SYNTHETIC_MECHANICAL, build_study_checkpoint_envelope,
    load_study_checkpoint_envelope, save_study_checkpoint_envelope,
)
from .folds import build_train_internal_folds, split_by_fold
from .m1 import M1_INPUT_DIMENSION, verify_against_frozen_contract

SHORT = dict(maximum_steps=8, evaluation_interval=2, warmup_steps=4,
             events_per_batch=2)


def _mechanical(family: str, root: pathlib.Path) -> driver.MechanicalRunResult:
    groups = load_v3_event_groups(synthetic.synthetic_transactions(),
                                  split=synthetic.SYNTHETIC_SPLIT)
    folds = build_train_internal_folds(synthetic.synthetic_fold_manifest())
    split = split_by_fold(groups, folds)
    return driver.run_training(
        family=family, mode=authorization.MODE_MECHANICAL,
        fit_groups=split["A"], held_out_groups=split["B"],
        cache=driver.GraphCache(), dataset_root=root, seed=0,
        learning_rate=1e-3, weight_decay=0.0, **SHORT)


def _refusal(callable_, *args, **kwargs) -> Mapping[str, Any]:
    try:
        callable_(*args, **kwargs)
    except Exception as exc:                                 # noqa: BLE001
        return {"refused": True, "exception": type(exc).__name__,
                "message": str(exc)[:180]}
    return {"refused": False, "exception": None, "message": "NOT REFUSED"}


def run(*, repo_root: pathlib.Path, train_namespace: pathlib.Path | None,
        train_root: pathlib.Path | None) -> Mapping[str, Any]:
    report: Dict[str, Any] = {}
    authority = load_open_loop_v3_authority(repo_root)
    report["authority"] = {
        "preregistration_sha256": PREREGISTRATION_V1_SHA256,
        "fold_manifest_sha256": TRAIN_INTERNAL_FOLD_MANIFEST_V1_SHA256,
        "m1_contract_sha256": M1_INPUT_CONTRACT_V1_SHA256,
        "family_selection_rule_sha256": FAMILY_SELECTION_RULE_V1_SHA256,
        "m2_model_config_sha256": M2_MODEL_CONFIG_SHA256,
        "train_seal_root": OFFICIAL_V3_TRAIN_SEAL_ROOT,
        "validation_seal_root": OFFICIAL_V3_VALIDATION_SEAL_ROOT,
        "status": authority.preregistration["status"],
        "permissions": dict(authority.permissions),
    }
    verify_against_frozen_contract(authority.m1_contract)
    report["m1"] = {"input_dimension": M1_INPUT_DIMENSION,
                    "contract_verified": True}

    # ------------------------------------------------ mechanical determinism
    with tempfile.TemporaryDirectory() as scratch:
        root = pathlib.Path(scratch)
        runs = {}
        for family in ("M1", "M2"):
            first = _mechanical(family, root)
            second = _mechanical(family, root)
            runs[family] = {
                "run_1_state_dict_sha256": first.state_dict_sha256,
                "run_2_state_dict_sha256": second.state_dict_sha256,
                "state_dict_match": first.state_dict_sha256 == second.state_dict_sha256,
                "metric_trace_match": first.metric_trace == second.metric_trace,
                "event_order_match": first.event_order == second.event_order,
                "steps": first.steps,
                "metric_trace": [[step, round(value, 12)]
                                 for step, value in first.metric_trace],
                "residual_state_sha256_before": first.residual_state_sha256_before,
                "residual_state_sha256_after": first.residual_state_sha256_after,
                "residual_unchanged": (
                    first.residual_state_sha256_before
                    == first.residual_state_sha256_after),
            }
        report["mechanical"] = runs

        # -------------------------------------------- checkpoint round trip
        torch.manual_seed(0)
        from .m1 import M1LocalPredictor
        from ..runtime_configuration import DEFAULT_RUNTIME_CONFIG
        commit = "0" * 40
        m1_envelope = build_study_checkpoint_envelope(
            family="M1", model=M1LocalPredictor(), source_commit=commit,
            training_seed=0, learning_rate=1e-3, weight_decay=0.0,
            refit_step=None, training_status=SYNTHETIC_MECHANICAL)
        m2_envelope = build_study_checkpoint_envelope(
            family="M2", model=driver.build_model("M2"), source_commit=commit,
            training_seed=0, learning_rate=1e-3, weight_decay=0.0,
            refit_step=None, training_status=SYNTHETIC_MECHANICAL,
            runtime_config=DEFAULT_RUNTIME_CONFIG)
        round_trip = {}
        for name, envelope in (("M1", m1_envelope), ("M2", m2_envelope)):
            path = root / f"{name}.pt"
            save_study_checkpoint_envelope(path, envelope)
            loaded = load_study_checkpoint_envelope(path)
            round_trip[name] = {
                "state_dict_sha256": loaded["state_dict_sha256"],
                "match": loaded["state_dict_sha256"] == envelope["state_dict_sha256"],
                "training_status": loaded["training_status"],
                "deployment_classification": loaded["deployment_classification"],
                "envelope_root": loaded[
                    "open_loop_v3_study_checkpoint_envelope_v1_sha256"],
            }
        corrupt = dict(m1_envelope)
        payload = dict(corrupt["family_payload"])
        state = dict(payload["state_dict"])
        state["network.0.bias"] = state["network.0.bias"] + 1.0
        payload["state_dict"] = state
        corrupt["family_payload"] = payload
        corrupt_path = root / "corrupt.pt"
        save_study_checkpoint_envelope(corrupt_path, corrupt)
        round_trip["corruption"] = _refusal(load_study_checkpoint_envelope, corrupt_path)
        report["checkpoints"] = round_trip

        # ----------------------------------------------------- fail closed
        official = root / "official-v3-train"
        (official / "ops").mkdir(parents=True, exist_ok=True)
        (official / "ops" / "authority.json").write_text(
            json.dumps({"v3_split": "v3_train"}))
        validation = root / "official-v3-validation"
        (validation / "ops").mkdir(parents=True, exist_ok=True)
        (validation / "ops" / "authority.json").write_text(
            json.dumps({"v3_split": "v3_validation"}))
        reserve = root / "reserve-domain"
        (reserve / "ops").mkdir(parents=True, exist_ok=True)
        (reserve / "ops" / "authority.json").write_text(
            json.dumps({"v3_split": "reserve"}))
        report["fail_closed"] = {
            "scientific_training_without_authorization": _refusal(
                authorization.require_optimization_authorization,
                mode=authorization.MODE_SCIENTIFIC, dataset_root=official, seed=11),
            "official_train_in_mechanical_mode": _refusal(
                authorization.require_optimization_authorization,
                mode=authorization.MODE_MECHANICAL, dataset_root=official, seed=0),
            "validation_as_training_data": _refusal(
                authorization.require_training_dataset, validation),
            "protected_domain_as_training_data": _refusal(
                authorization.require_training_dataset, reserve),
            "frozen_scientific_seed_in_mechanical_mode": _refusal(
                authorization.require_optimization_authorization,
                mode=authorization.MODE_MECHANICAL, dataset_root=root, seed=11),
        }

    # -------------------------------------- official TRAIN structural census
    if train_namespace is not None and train_root is not None:
        folds = build_train_internal_folds(authority.fold_manifest)
        census = driver.inspect_dataset(
            train_namespace, split="v3_train", dataset_root=train_root,
            folds=folds, forward_untrained_m2=True)
        report["official_train_census"] = dict(census)
        report["official_train_census"]["m0_official_value_fitted"] = False
        report["official_train_census"]["backward_passes"] = 0
    else:
        report["official_train_census"] = {"skipped": True}

    report["scientific_state"] = {
        "official_optimizer_steps": 0,
        "official_m0_fitted": False,
        "frozen_scientific_seeds_trained": [],
        "validation_records_opened": 0,
        "protected_domain_records_opened": 0,
        "scientifically_trained_checkpoints_created": 0,
    }
    return report


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/opt/rvt")
    parser.add_argument("--train-namespace", default=None)
    parser.add_argument("--train-root", default=None)
    parser.add_argument("--out", default="/out/stage5b_qualification.json")
    args = parser.parse_args()
    report = run(
        repo_root=pathlib.Path(args.repo_root),
        train_namespace=(pathlib.Path(args.train_namespace)
                         if args.train_namespace else None),
        train_root=pathlib.Path(args.train_root) if args.train_root else None)
    pathlib.Path(args.out).write_text(
        json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: v for k, v in report.items()
                      if k in ("mechanical", "fail_closed", "official_train_census",
                               "scientific_state")},
                     indent=1, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
