"""Smoke benchmark under evaluation protocol v2 (Steps 2-6).

DIAGNOSTIC ONLY. This is not a publication experiment: the training budget is
deliberately tiny, there is one model seed, and the episode count is small. No
superiority, significance, scalability, robustness, generalization,
decentralization, recoverability or publication-readiness conclusion may be drawn
from its output.

Purpose: verify that training completes, that checkpoint selection touches only
the validation split, that fresh schema-2 checkpoints evaluate end to end, and
that the metrics behave consistently.

    python scripts/run_smoke_protocol_v2.py
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config  # noqa: E402
from rvt_swarm.consistency import run_all_checks  # noqa: E402
from rvt_swarm.evaluate import run_policy_episode  # noqa: E402
from rvt_swarm.metrics import EVALUATION_SCHEMA_VERSION  # noqa: E402
from rvt_swarm.splits import (  # noqa: E402
    TEST,
    VALIDATION,
    episode_signature,
    setting_episode_seeds,
)
from rvt_swarm.train import git_commit, training_budget_report  # noqa: E402


OUT = REPO / "results" / "smoke_protocol_v2"
CKPT = REPO / "checkpoints" / "smoke_protocol_v2"

# ---------------------------------------------------------------------------
# Reduced smoke budget -- identical for BOTH learned methods.
#
# Rationale (stated before training, per the approval conditions):
#   expert_episodes 8   : enough samples (~800 graphs) for a few gradient epochs
#                         without a multi-hour counterfactual-labelling pass.
#   epochs 6            : enough for the loop, checkpointing, early stopping and
#                         the top-k recheck to all execute at least once.
#   val interval 2      : gives 3 validation calls, so ranking and the top-k pool
#                         are both exercised.
#   topk 2              : exercises the recheck path with more than one candidate.
#   patience 3          : cannot trigger before the run ends; early stopping is
#                         exercised structurally, not as a real stopping decision.
#   validation N {5,11} : from the validation split; disjoint from test N {4,8}.
# Every one of these applies identically to gnn_only and rvt_swarm.
# ---------------------------------------------------------------------------
SMOKE = dict(
    expert_episodes=8,
    epochs=6,
    rollout_val_interval=2,
    rollout_val_episodes_per_setting=1,
    rollout_val_topk_checkpoints=2,
    rollout_val_recheck_episodes_per_setting=1,
    early_stopping_patience=3,
    validation_team_sizes=[5, 11],
    validation_scenarios=["narrow_passage", "dynamic_obstacles"],
)

TEST_TEAM_SIZES = [4, 8]
TEST_SCENARIOS = ["open_field", "narrow_passage"]  # one open, one constrained
EPISODES_PER_CELL = 30
MODEL_SEED = 0
FINAL_TEST_SEED = 0

LEARNED = ["gnn_only", "rvt_swarm"]
BASELINES = ["fixed_formation_expert", "orca", "cbf_qp"]
METHODS = BASELINES[:1] + LEARNED + BASELINES[1:]


def smoke_config() -> Config:
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.train.n_workers = 4
    cfg.train.expert_episodes = SMOKE["expert_episodes"]
    cfg.train.epochs_gnn_only = SMOKE["epochs"]
    cfg.train.epochs_instant_cert = SMOKE["epochs"]
    cfg.train.epochs_rvt_swarm = SMOKE["epochs"]
    cfg.train.rollout_val_interval = SMOKE["rollout_val_interval"]
    cfg.train.rollout_val_episodes_per_setting = SMOKE["rollout_val_episodes_per_setting"]
    cfg.train.rollout_val_topk_checkpoints = SMOKE["rollout_val_topk_checkpoints"]
    cfg.train.rollout_val_recheck_episodes_per_setting = SMOKE["rollout_val_recheck_episodes_per_setting"]
    cfg.train.early_stopping_patience = SMOKE["early_stopping_patience"]
    cfg.train.rollout_val_team_sizes = list(SMOKE["validation_team_sizes"])
    cfg.train.rollout_val_scenarios = list(SMOKE["validation_scenarios"])
    cfg.env.team_sizes = list(TEST_TEAM_SIZES)
    cfg.env.scenarios = list(TEST_SCENARIOS)
    cfg.eval.episodes_per_setting = EPISODES_PER_CELL
    cfg.seeds.model_seed = MODEL_SEED
    cfg.seeds.training_data_seed = 0
    cfg.seeds.validation_seed = 0
    cfg.seeds.final_test_seed = FINAL_TEST_SEED
    return cfg


def assert_deterministic_mode(cfg: Config) -> dict:
    """Step 1.4, option B: run with the noise seed roles explicitly INACTIVE.

    `counterfactual_rollout_seed` and `environment_noise_seed` are declared in
    SeedConfig but consumed nowhere: rollout labelling is deterministic (one
    rollout per candidate) and no sensor or actuation noise model exists. Rather
    than pretend they are wired, this run is declared deterministic/no-noise and
    the fact is recorded in config.yaml and the report.

    No robustness-to-noise conclusion may be drawn from this benchmark.
    """
    import rvt_swarm.dataset as ds
    import rvt_swarm.environment as env

    src = (Path(env.__file__).read_text() + Path(ds.__file__).read_text())
    for token in ("environment_noise_seed", "counterfactual_rollout_seed"):
        assert token not in src, (
            f"{token} now appears in the environment/dataset source. It must either be "
            f"wired and documented, or this deterministic-mode declaration updated."
        )
    return {
        "deterministic_mode": True,
        "sensor_noise": "none (no noise model implemented)",
        "actuation_noise": "none",
        "counterfactual_rollout_seed": "INACTIVE - rollout labelling is deterministic (M=1)",
        "environment_noise_seed": "INACTIVE - no noise model exists",
        "noise_robustness_claims_permitted": False,
    }


def initial_state_record(cfg: Config, obs: dict) -> dict:
    p = np.asarray(obs["positions"])
    o = np.asarray(obs["obstacles"])
    d = np.linalg.norm(p[:, None, :] - p[None, :, :], axis=-1)
    np.fill_diagonal(d, np.inf)
    ro = np.linalg.norm(p[:, None, :] - o[None, :, :], axis=-1) if len(o) else np.array([[np.inf]])
    return {
        "initial_min_rr_clearance": float(d.min()) if len(p) > 1 else float("inf"),
        "initial_min_ro_clearance": float(ro.min()),
        "min_rr_distance": float(cfg.env.min_rr_distance),
        "min_ro_distance": float(cfg.env.min_ro_distance),
        "initial_in_bounds": bool(np.abs(p).max() <= cfg.env.world_size * 0.5),
        "initial_formation_valid": bool(np.isfinite(p).all()),
        "initial_obstacles_valid": bool(np.isfinite(o).all() if len(o) else True),
    }


def train_smoke_models(cfg: Config) -> dict:
    from rvt_swarm.dataset import generate_dataset
    from rvt_swarm.train import train_model
    import torch

    CKPT.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Generating shared training dataset ({cfg.train.expert_episodes} episodes) ===")
    dataset = generate_dataset(cfg)
    steps_per_epoch = int(np.ceil(0.9 * len(dataset) / cfg.train.batch_size))
    print(f"    {len(dataset)} samples -> {steps_per_epoch} optimizer steps/epoch")

    meta = {}
    for method in LEARNED:
        print(f"\n=== Training {method} (smoke budget) ===")
        train_model(method, cfg, str(CKPT), dataset=dataset)
        state = torch.load(CKPT / f"{method}.pt", map_location="cpu", weights_only=False)
        meta[method] = {
            "evaluation_schema_version": int(state.get("evaluation_schema_version", -1)),
            "git_commit": state.get("git_commit", "unknown"),
            "epoch": int(state.get("epoch", -1)),
            "is_fresh": True,
            "path": str((CKPT / f"{method}.pt").relative_to(REPO)),
        }
        print(f"    -> {meta[method]}")
    return meta, steps_per_epoch, len(dataset)


def main() -> int:
    cfg = smoke_config()
    commit = git_commit()
    determinism = assert_deterministic_mode(cfg)
    OUT.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print(f"SMOKE BENCHMARK - protocol v2 - commit {commit}")
    print(f"schema={EVALUATION_SCHEMA_VERSION}  model_seed={MODEL_SEED}  "
          f"final_test_seed={FINAL_TEST_SEED}")
    print(f"methods: {METHODS}")
    print(f"test cells: N={TEST_TEAM_SIZES} x {TEST_SCENARIOS} x {EPISODES_PER_CELL} episodes")
    print("=" * 72)

    ckpt_meta, steps_per_epoch, dataset_size = train_smoke_models(cfg)
    budget = training_budget_report(cfg, steps_per_epoch=steps_per_epoch)

    # ---- evaluation on the final test split ------------------------------
    test_seeds, validation_seeds = [], []
    for si, scenario in enumerate(TEST_SCENARIOS):
        for n in TEST_TEAM_SIZES:
            test_seeds += setting_episode_seeds(TEST, si, n, EPISODES_PER_CELL, FINAL_TEST_SEED)
    for si, _ in enumerate(SMOKE["validation_scenarios"]):
        for n in SMOKE["validation_team_sizes"]:
            validation_seeds += setting_episode_seeds(VALIDATION, si, n, 1, 0)

    rows, initial_records = [], []
    for method in METHODS:
        print(f"\n=== Evaluating {method} ===")
        model = None
        if method in LEARNED:
            from rvt_swarm.policy_runtime import load_learned_model
            from rvt_swarm.utils import torch_device

            model = load_learned_model(method, cfg, str(CKPT), torch_device("cpu"))
        for si, scenario in enumerate(TEST_SCENARIOS):
            for n in TEST_TEAM_SIZES:
                seeds = setting_episode_seeds(TEST, si, n, EPISODES_PER_CELL, FINAL_TEST_SEED)
                for ep_idx, seed in enumerate(seeds):
                    out = run_policy_episode(
                        method, cfg, n, scenario, ckpt_dir=str(CKPT), seed=seed, model=model,
                        trace=True,
                    )
                    initial_obs = out.pop("initial_obs")
                    sig = episode_signature(initial_obs)
                    trace = out.pop("trace")
                    if method == METHODS[0]:
                        # Validity of the INITIAL state, i.e. the state at reset.
                        # (trace[0] is the state after the first step, which has
                        # already moved and is not what "initial" means.)
                        initial_records.append(initial_state_record(cfg, initial_obs))
                    row = {
                        "evaluation_schema_version": int(out["evaluation_schema_version"]),
                        "git_commit": commit,
                        "method": method,
                        "model_seed": MODEL_SEED if method in LEARNED else -1,
                        "final_test_seed": FINAL_TEST_SEED,
                        "episode_seed": seed,
                        "episode_index": ep_idx,
                        "episode_signature": sig,
                        "scenario": scenario,
                        "team_size": n,
                    }
                    for k in [
                        "goal_reached", "collision_free", "collision_free_terminal", "success",
                        "success_terminal", "robot_robot_collision_steps",
                        "robot_obstacle_collision_steps", "min_rr_clearance", "min_ro_clearance",
                        "deadlock", "deadlock_terminal", "irreversible_collapse",
                        "irreversible_collapse_terminal", "form_rms_mean", "form_rms_max",
                        "form_ok_terminal", "time_in_formation_tube", "stall_rate",
                        "completion_time", "completion_time_censored", "topology_switches",
                        "safety_filter_activations", "safety_filter_activation_rate",
                        "inference_latency_mean_ms", "inference_latency_median_ms",
                        "inference_latency_p95_ms", "inference_latency_p99_ms",
                        "timed_control_steps", "steps",
                    ]:
                        row[k] = float(out[k])
                    row["completion_censored"] = row.pop("completion_time_censored")
                    rows.append(row)
                print(f"    {scenario:16s} N={n:2d}  {EPISODES_PER_CELL} episodes done")

    # ---- consistency checks ----------------------------------------------
    print("\n" + "=" * 72)
    print("CONSISTENCY CHECKS")
    print("=" * 72)
    report = run_all_checks(
        rows=rows,
        initial_records=initial_records,
        test_seeds=test_seeds,
        validation_seeds=validation_seeds,
        checkpoint_meta=ckpt_meta,
        budget_report=budget,
        learned_methods=LEARNED,
    )
    print(report)

    # ---- write raw data ---------------------------------------------------
    per_ep = OUT / "per_episode.csv"
    with per_ep.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    summary_rows = []
    for method in METHODS:
        for scenario in TEST_SCENARIOS:
            for n in TEST_TEAM_SIZES:
                sub = [r for r in rows if r["method"] == method
                       and r["scenario"] == scenario and r["team_size"] == n]
                entry = {"method": method, "scenario": scenario, "team_size": n,
                         "episodes": len(sub),
                         "evaluation_schema_version": EVALUATION_SCHEMA_VERSION}
                for k in sub[0]:
                    if isinstance(sub[0][k], float) and k not in ("team_size",):
                        entry[f"{k}_mean"] = float(np.nanmean([r[k] for r in sub]))
                summary_rows.append(entry)
    with (OUT / "summary.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)

    config_doc = {
        "evaluation_schema_version": EVALUATION_SCHEMA_VERSION,
        "git_commit": commit,
        "purpose": "DIAGNOSTIC SMOKE BENCHMARK - not a publication experiment",
        "determinism": determinism,
        "methods": METHODS,
        "learned_methods": LEARNED,
        "test_split": {
            "scenarios": TEST_SCENARIOS, "team_sizes": TEST_TEAM_SIZES,
            "episodes_per_cell": EPISODES_PER_CELL,
            "final_test_seed": FINAL_TEST_SEED,
            "total_episodes_per_method": len(TEST_SCENARIOS) * len(TEST_TEAM_SIZES) * EPISODES_PER_CELL,
        },
        "validation_split": {
            "scenarios": SMOKE["validation_scenarios"],
            "team_sizes": SMOKE["validation_team_sizes"],
            "episodes_per_setting": SMOKE["rollout_val_episodes_per_setting"],
        },
        "smoke_budget": SMOKE,
        "model_seed": MODEL_SEED,
        "dataset_size_samples": dataset_size,
        "steps_per_epoch": steps_per_epoch,
        "training_budget_report": budget,
        "checkpoints": ckpt_meta,
        "environment": {k: v for k, v in asdict(cfg.env).items() if not isinstance(v, list)},
        "consistency_checks": [
            {"name": r.name, "passed": r.passed, "detail": r.detail, "n": r.n_checked}
            for r in report.results
        ],
    }
    try:
        import yaml  # type: ignore

        (OUT / "config.yaml").write_text(yaml.safe_dump(config_doc, sort_keys=False))
    except ImportError:
        (OUT / "config.yaml").write_text(
            "# PyYAML unavailable; emitted as JSON (valid YAML 1.2)\n"
            + json.dumps(config_doc, indent=2, default=str)
        )

    print(f"\nwrote {per_ep}")
    print(f"wrote {OUT / 'summary.csv'}")
    print(f"wrote {OUT / 'config.yaml'}")
    if not report.passed:
        print("\n*** CONSISTENCY CHECKS FAILED - results must not be interpreted ***")
        for f in report.failures:
            print("   ", f)
        return 1
    print("\nAll consistency checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
