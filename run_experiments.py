from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
from typing import Dict, List

import numpy as np


# Avoid high-contention BLAS/OpenMP native crashes in long training/eval runs.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

from rvt_swarm.config import Config


LEARNED = ["gnn_only", "instant_cert", "rvt_swarm"]
BASELINES = ["adaptive_formation", "cbf_qp", "orca", "centralized_mpc"]


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


DEFAULT_MULTI_SEEDS = [0, 1, 2, 3, 4]


def apply_runtime_overrides(
    cfg: Config,
    device: str,
    workers: int,
    seed: int | None = None,
    episodes_per_setting: int | None = None,
) -> Config:
    cfg.train.device = device
    cfg.train.n_workers = workers
    if seed is not None:
        cfg.train.seed = int(seed)
    if episodes_per_setting is not None:
        cfg.eval.episodes_per_setting = int(episodes_per_setting)
    return cfg


def runtime_config(
    device: str,
    workers: int,
    seed: int | None = None,
    episodes_per_setting: int | None = None,
) -> Config:
    return apply_runtime_overrides(
        Config(),
        device,
        workers,
        seed=seed,
        episodes_per_setting=episodes_per_setting,
    )


def run_train(cfg: Config, results_dir: Path) -> None:
    from rvt_swarm.dataset import generate_dataset
    from rvt_swarm.train import train_model

    print("Generating shared dataset...")
    dataset = generate_dataset(cfg)
    for method in LEARNED:
        print(f"Training {method}...")
        train_model(method, cfg, str(results_dir), dataset=dataset)
    print("Training done.")


def run_eval(cfg: Config, results_dir: Path) -> None:
    from rvt_swarm.evaluate import evaluate_method, summarize, summarize_by_team_size

    summary = {}
    summary_by_team_size = {}
    for method in LEARNED + BASELINES:
        print(f"Evaluating {method}...")
        rows = evaluate_method(method, cfg, str(results_dir))
        by_team_size = summarize_by_team_size(rows)
        save_json(rows, results_dir / f"{method}_rows.json")
        save_json(by_team_size, results_dir / f"{method}_by_team_size.json")
        summary[method] = summarize(rows)
        summary_by_team_size[method] = by_team_size
        covered_team_sizes = sorted({int(row["n_agents"]) for row in rows})
        print(f"  covered team sizes: {covered_team_sizes}")
    save_json(summary, results_dir / "summary.json")
    save_json(summary_by_team_size, results_dir / "summary_by_team_size.json")
    print(json.dumps(summary, indent=2))


def build_ablation_configs(device: str, workers: int) -> dict[str, Config]:
    ablations = {
        "full": runtime_config(device, workers),
        "no_recoverability": runtime_config(device, workers),
        "no_counterfactual": runtime_config(device, workers),
        "no_progress_shield": runtime_config(device, workers),
        "no_topology": runtime_config(device, workers),
        "fixed_formation": runtime_config(device, workers),
    }
    ablations["no_recoverability"].method.use_recoverability = False
    ablations["no_counterfactual"].method.use_counterfactual_topology = False
    ablations["no_progress_shield"].method.use_progress_shield = False
    ablations["no_topology"].method.use_topology = False
    ablations["fixed_formation"].method.use_adaptive_formation_scale = False
    return ablations


def run_ablations(device: str, workers: int, results_dir: Path) -> None:
    from rvt_swarm.dataset import generate_dataset
    from rvt_swarm.evaluate import evaluate_method, summarize
    from rvt_swarm.train import train_model

    ablation_dir = Path(str(results_dir) + "_ablation")
    base_cfg = runtime_config(device, workers)
    ablations = build_ablation_configs(device, workers)
    all_rows = {}

    print("Generating shared ablation dataset...")
    dataset = generate_dataset(base_cfg)
    for name, cfg in ablations.items():
        print(f"Ablation train/eval: {name}")
        train_model("rvt_swarm", cfg, str(ablation_dir / name), dataset=dataset)
        rows = evaluate_method("rvt_swarm", cfg, str(ablation_dir / name))
        all_rows[name] = summarize(rows)
    save_json(all_rows, ablation_dir / "ablations.json")
    print(json.dumps(all_rows, indent=2))


def run_visualize(cfg: Config, results_dir: Path) -> None:
    from rvt_swarm.visualize import visualize_comparisons, visualize_methods

    gif_dir = results_dir / "gifs"
    methods = LEARNED + BASELINES
    team_sizes = list(cfg.env.team_sizes)
    print(f"Generating visualization outputs for team sizes {team_sizes}...")
    print("Generating per-method GIFs...")
    gif_paths, metric_plot_paths = visualize_methods(
        methods,
        cfg,
        ckpt_dir=str(results_dir),
        out_dir=str(gif_dir),
        scenarios=["open_field", "narrow_passage"],
        team_sizes=team_sizes,
        seed=42,
        fps=8,
    )
    print(f"{len(gif_paths)} per-method GIFs saved.")
    print(f"{len(metric_plot_paths)} per-method metrics plots saved.")
    print("Generating comparison GIFs...")
    compare_gif_paths, compare_metric_plot_paths = visualize_comparisons(
        method_groups=[
            ["gnn_only", "instant_cert", "rvt_swarm"],
            ["rvt_swarm", "adaptive_formation", "cbf_qp", "orca"],
        ],
        cfg=cfg,
        ckpt_dir=str(results_dir),
        out_dir=str(gif_dir),
        scenarios=["open_field", "narrow_passage"],
        team_sizes=team_sizes,
        seed=42,
        fps=8,
    )
    print(f"{len(compare_gif_paths)} comparison GIFs saved.")
    print(f"{len(compare_metric_plot_paths)} comparison metrics plots saved.")
    print(f"All GIFs in {gif_dir}/")
    print(f"All metrics plots in {gif_dir / 'metrics'}/")


def run_diagnose() -> None:
    modules = [
        "numpy",
        "torch",
        "matplotlib",
        "PIL.Image",
        "rvt_swarm.environment",
        "rvt_swarm.dataset",
        "rvt_swarm.train",
        "rvt_swarm.evaluate",
        "rvt_swarm.visualize",
    ]
    print("Diagnosing imports...", flush=True)
    for name in modules:
        print(f"  importing {name} ...", flush=True)
        importlib.import_module(name)
        print(f"  ok: {name}", flush=True)
    print("Import diagnosis completed.", flush=True)


def _ci95(values: np.ndarray) -> tuple[float, float]:
    if values.size == 0:
        return float("nan"), float("nan")
    if values.size == 1:
        v = float(values[0])
        return v, v
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    half_width = 1.96 * std / max(np.sqrt(values.size), 1e-6)
    return mean - half_width, mean + half_width


def _permutation_pvalue(a: np.ndarray, b: np.ndarray, draws: int, seed: int) -> float:
    if a.size == 0 or b.size == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    pooled = np.concatenate([a, b])
    n_a = a.size
    observed = abs(float(np.mean(a) - np.mean(b)))
    count = 0
    for _ in range(draws):
        perm = rng.permutation(pooled)
        diff = abs(float(np.mean(perm[:n_a]) - np.mean(perm[n_a:])))
        if diff >= observed:
            count += 1
    return (count + 1) / (draws + 1)


def _aggregate_metric_values(values: List[float]) -> Dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {}
    ci_low, ci_high = _ci95(arr)
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        "ci95_low": float(ci_low),
        "ci95_high": float(ci_high),
        "n": int(arr.size),
        "values": [float(v) for v in arr.tolist()],
    }


def aggregate_multiseed_summary(
    seed_summaries: Dict[int, Dict[str, Dict[str, float]]],
    reference: str,
    permutation_draws: int,
    permutation_seed: int,
) -> Dict[str, object]:
    report: Dict[str, object] = {
        "seeds": sorted(int(seed) for seed in seed_summaries.keys()),
        "methods": {},
    }
    methods = sorted({method for summary in seed_summaries.values() for method in summary.keys()})
    for method in methods:
        metrics = sorted(
            {
                metric
                for summary in seed_summaries.values()
                if method in summary
                for metric in summary[method].keys()
            }
        )
        method_entry: Dict[str, object] = {"n_seeds": 0, "metrics": {}}
        per_metric_values: Dict[str, List[float]] = {metric: [] for metric in metrics}
        for seed in sorted(seed_summaries):
            summary = seed_summaries[seed]
            if method not in summary:
                continue
            method_entry["n_seeds"] = int(method_entry["n_seeds"]) + 1
            for metric in metrics:
                value = summary[method].get(metric)
                if value is not None and np.isfinite(value):
                    per_metric_values[metric].append(float(value))
        for metric, values in per_metric_values.items():
            stats = _aggregate_metric_values(values)
            if stats:
                method_entry["metrics"][metric] = stats
        report["methods"][method] = method_entry

    ref_success = np.asarray(
        report["methods"].get(reference, {}).get("metrics", {}).get("success", {}).get("values", []),
        dtype=np.float64,
    )
    if ref_success.size:
        for idx, method in enumerate(methods):
            if method == reference:
                continue
            method_success = np.asarray(
                report["methods"].get(method, {}).get("metrics", {}).get("success", {}).get("values", []),
                dtype=np.float64,
            )
            if method_success.size == 0:
                continue
            report["methods"][method]["vs_reference"] = {
                "reference": reference,
                "success_mean_delta": float(np.mean(ref_success) - np.mean(method_success)),
                "success_permutation_pvalue": float(
                    _permutation_pvalue(
                        ref_success,
                        method_success,
                        draws=permutation_draws,
                        seed=permutation_seed + idx,
                    )
                ),
            }
    return report


def aggregate_multiseed_by_team_size(
    seed_team_summaries: Dict[int, Dict[str, Dict[str, Dict[str, float]]]],
    reference: str,
    permutation_draws: int,
    permutation_seed: int,
) -> Dict[str, object]:
    team_sizes = sorted(
        {
            int(team_size)
            for summary in seed_team_summaries.values()
            for method_map in summary.values()
            for team_size in method_map.keys()
        }
    )
    report: Dict[str, object] = {"seeds": sorted(int(seed) for seed in seed_team_summaries.keys()), "team_sizes": {}}
    for team_size in team_sizes:
        per_seed_summary: Dict[int, Dict[str, Dict[str, float]]] = {}
        for seed, summary in seed_team_summaries.items():
            per_seed_summary[int(seed)] = {}
            for method, method_map in summary.items():
                if str(team_size) in method_map:
                    per_seed_summary[int(seed)][method] = method_map[str(team_size)]
        report["team_sizes"][str(team_size)] = aggregate_multiseed_summary(
            per_seed_summary,
            reference=reference,
            permutation_draws=permutation_draws,
            permutation_seed=permutation_seed + team_size * 17,
        )
    return report


def _print_multiseed_summary(report: Dict[str, object], reference: str) -> None:
    print(f"multi-seed summary over seeds: {report['seeds']}")
    for method, entry in sorted(report["methods"].items()):
        success = entry.get("metrics", {}).get("success")
        collision_free = entry.get("metrics", {}).get("collision_free")
        form_ok = entry.get("metrics", {}).get("form_ok")
        if success is None:
            continue
        line = (
            f"{method:18s} n={entry['n_seeds']} "
            f"success={success['mean']:.4f} "
            f"CI=[{success['ci95_low']:.4f}, {success['ci95_high']:.4f}]"
        )
        if collision_free is not None:
            line += f" cf={collision_free['mean']:.4f}"
        if form_ok is not None:
            line += f" form={form_ok['mean']:.4f}"
        if method != reference and "vs_reference" in entry:
            line += (
                f" delta_vs_{reference}={entry['vs_reference']['success_mean_delta']:.4f}"
                f" p={entry['vs_reference']['success_permutation_pvalue']:.4f}"
            )
        print(line)


def run_multi_seed(
    device: str,
    workers: int,
    results_root: Path,
    seeds: List[int],
    episodes_per_setting: int | None,
    reference_method: str,
    permutation_draws: int,
    skip_train: bool,
    skip_eval: bool,
) -> None:
    seed_summaries: Dict[int, Dict[str, Dict[str, float]]] = {}
    seed_team_summaries: Dict[int, Dict[str, Dict[str, Dict[str, float]]]] = {}
    for seed in seeds:
        seed_dir = results_root / f"seed_{int(seed):03d}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        cfg = runtime_config(
            device,
            workers,
            seed=int(seed),
            episodes_per_setting=episodes_per_setting,
        )
        print(f"=== seed {seed} -> {seed_dir} ===")
        if not skip_train:
            run_train(cfg, seed_dir)
        if not skip_eval:
            run_eval(cfg, seed_dir)
        summary_path = seed_dir / "summary.json"
        by_team_size_path = seed_dir / "summary_by_team_size.json"
        if not summary_path.exists() or not by_team_size_path.exists():
            raise FileNotFoundError(
                f"Missing summary outputs for seed {seed} in {seed_dir}. "
                "Run evaluation or disable skip flags."
            )
        with summary_path.open("r", encoding="utf-8") as f:
            seed_summaries[int(seed)] = json.load(f)
        with by_team_size_path.open("r", encoding="utf-8") as f:
            seed_team_summaries[int(seed)] = json.load(f)

    aggregate = aggregate_multiseed_summary(
        seed_summaries,
        reference=reference_method,
        permutation_draws=permutation_draws,
        permutation_seed=min(seeds) if seeds else 0,
    )
    aggregate_by_team_size = aggregate_multiseed_by_team_size(
        seed_team_summaries,
        reference=reference_method,
        permutation_draws=permutation_draws,
        permutation_seed=min(seeds) if seeds else 0,
    )
    save_json(aggregate, results_root / "aggregate_summary.json")
    save_json(aggregate_by_team_size, results_root / "aggregate_by_team_size.json")
    _print_multiseed_summary(aggregate, reference_method)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default="train_all",
        choices=["train_all", "eval_all", "ablations", "visualize", "all", "diagnose", "multi_seed"],
    )
    parser.add_argument("--device", type=str, default="auto", help="cpu, cuda, mps, or auto")
    parser.add_argument("--results-dir", type=str, default="results")
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Max parallel workers (0 = auto = 3/4 of cpu_count)",
    )
    parser.add_argument(
        "--skip-visualize",
        action="store_true",
        help="Skip GIF generation in --mode all",
    )
    parser.add_argument("--seed", type=int, default=None, help="Override cfg.train.seed for this run")
    parser.add_argument(
        "--episodes-per-setting",
        type=int,
        default=None,
        help="Override cfg.eval.episodes_per_setting for this run",
    )
    parser.add_argument(
        "--multi-seeds",
        type=int,
        nargs="*",
        default=None,
        help="Seed list for --mode multi_seed; default is 0 1 2 3 4",
    )
    parser.add_argument(
        "--reference-method",
        type=str,
        default="rvt_swarm",
        help="Reference method for permutation tests in --mode multi_seed",
    )
    parser.add_argument(
        "--permutation-draws",
        type=int,
        default=5000,
        help="Number of draws for permutation tests in --mode multi_seed",
    )
    parser.add_argument(
        "--skip-train",
        action="store_true",
        help="In --mode multi_seed, reuse existing checkpoints and skip training",
    )
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="In --mode multi_seed, reuse existing summaries and skip evaluation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    cfg = runtime_config(
        args.device,
        args.workers,
        seed=args.seed,
        episodes_per_setting=args.episodes_per_setting,
    )

    if args.mode == "all":
        run_train(cfg, results_dir)
        run_eval(cfg, results_dir)
        run_ablations(args.device, args.workers, results_dir)
        if args.skip_visualize:
            print("Skipping visualization.")
        else:
            run_visualize(cfg, results_dir)
        print("All done.")
        return

    if args.mode == "train_all":
        run_train(cfg, results_dir)
        return
    if args.mode == "eval_all":
        run_eval(cfg, results_dir)
        return
    if args.mode == "ablations":
        run_ablations(args.device, args.workers, results_dir)
        return
    if args.mode == "visualize":
        run_visualize(cfg, results_dir)
        return
    if args.mode == "diagnose":
        run_diagnose()
        return
    if args.mode == "multi_seed":
        run_multi_seed(
            device=args.device,
            workers=args.workers,
            results_root=results_dir,
            seeds=list(args.multi_seeds or DEFAULT_MULTI_SEEDS),
            episodes_per_setting=args.episodes_per_setting,
            reference_method=args.reference_method,
            permutation_draws=args.permutation_draws,
            skip_train=args.skip_train,
            skip_eval=args.skip_eval,
        )
        return


if __name__ == "__main__":
    main()
