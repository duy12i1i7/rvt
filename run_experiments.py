from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path


# Avoid high-contention BLAS/OpenMP native crashes in long training/eval runs.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

from rvt_swarm.config import Config


LEARNED = ["gnn_only", "instant_cert", "rvt_swarm"]
BASELINES = ["adaptive_formation", "cbf_qp_like", "orca", "centralized_mpc"]


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def apply_runtime_overrides(cfg: Config, device: str, workers: int) -> Config:
    cfg.train.device = device
    cfg.train.n_workers = workers
    return cfg


def runtime_config(device: str, workers: int) -> Config:
    return apply_runtime_overrides(Config(), device, workers)


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
            ["rvt_swarm", "adaptive_formation", "cbf_qp_like", "orca"],
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default="train_all",
        choices=["train_all", "eval_all", "ablations", "visualize", "all", "diagnose"],
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    cfg = runtime_config(args.device, args.workers)

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


if __name__ == "__main__":
    main()
