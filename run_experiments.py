from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.config import Config
from rvt_swarm.evaluate import evaluate_method, summarize
from rvt_swarm.train import train_model
from rvt_swarm.visualize import visualize_methods


LEARNED = ["gnn_only", "instant_cert", "rvt_swarm"]
BASELINES = ["adaptive_formation", "cbf_qp_like", "orca_like", "centralized_mpc"]


def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="train_all", choices=["train_all", "eval_all", "ablations", "visualize", "all"])
    parser.add_argument("--device", type=str, default="auto", help="cpu, cuda, mps, or auto")
    parser.add_argument("--results-dir", type=str, default="results")
    parser.add_argument("--workers", type=int, default=0, help="Max parallel workers (0 = auto = cpu_count-1)")
    args = parser.parse_args()

    cfg = Config()
    cfg.train.device = args.device
    cfg.train.n_workers = args.workers
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    def do_train():
        for m in LEARNED:
            print(f"Training {m}...")
            train_model(m, cfg, str(results_dir))
        print("Training done.")

    def do_eval():
        summary = {}
        for m in LEARNED + BASELINES:
            print(f"Evaluating {m}...")
            rows = evaluate_method(m, cfg, str(results_dir))
            save_json(rows, results_dir / f"{m}_rows.json")
            summary[m] = summarize(rows)
        save_json(summary, results_dir / "summary.json")
        print(json.dumps(summary, indent=2))

    def do_ablations():
        abl_dir = Path(str(results_dir) + "_ablation")
        ablations = {
            "full": Config(),
            "no_counterfactual": Config(),
            "no_progress_shield": Config(),
            "no_topology": Config(),
        }
        ablations["no_counterfactual"].method.use_counterfactual_topology = False
        ablations["no_progress_shield"].method.use_progress_shield = False
        ablations["no_topology"].method.use_topology = False
        all_rows = {}
        for name, acfg in ablations.items():
            acfg.train.device = args.device
            print(f"Ablation train/eval: {name}")
            train_model("rvt_swarm", acfg, str(abl_dir / name))
            rows = evaluate_method("rvt_swarm", acfg, str(abl_dir / name))
            all_rows[name] = summarize(rows)
        save_json(all_rows, abl_dir / "ablations.json")
        print(json.dumps(all_rows, indent=2))

    def do_visualize():
        from rvt_swarm.visualize import visualize_comparisons
        gif_dir = str(results_dir / "gifs")
        methods = LEARNED + BASELINES
        print("Generating per-method GIFs...")
        paths = visualize_methods(
            methods, cfg,
            ckpt_dir=str(results_dir),
            out_dir=gif_dir,
            scenarios=["open_field", "narrow_passage"],
            team_sizes=[4, 8],
            seed=42, fps=8,
        )
        print(f"{len(paths)} per-method GIFs saved.")
        print("Generating comparison GIFs...")
        cpaths = visualize_comparisons(
            method_groups=[
                ["gnn_only", "instant_cert", "rvt_swarm"],
                ["rvt_swarm", "adaptive_formation", "cbf_qp_like", "orca_like"],
            ],
            cfg=cfg,
            ckpt_dir=str(results_dir),
            out_dir=gif_dir,
            scenarios=["open_field", "narrow_passage"],
            team_sizes=[4, 8],
            seed=42, fps=8,
        )
        print(f"{len(cpaths)} comparison GIFs saved.")
        print(f"All GIFs in {gif_dir}/")

    if args.mode == "all":
        do_train()
        do_eval()
        do_ablations()
        do_visualize()
        print("All done.")
        return

    if args.mode == "train_all":
        do_train()
        return
    if args.mode == "eval_all":
        do_eval()
        return
    if args.mode == "ablations":
        do_ablations()
        return
    if args.mode == "visualize":
        do_visualize()
        return


if __name__ == "__main__":
    main()
