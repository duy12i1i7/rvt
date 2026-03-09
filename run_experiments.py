from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.config import Config
from rvt_swarm.evaluate import evaluate_method, summarize
from rvt_swarm.train import train_model


LEARNED = ["gnn_only", "instant_cert", "rvt_swarm"]
BASELINES = ["adaptive_formation", "cbf_qp_like", "orca_like", "centralized_mpc"]


def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="train_all", choices=["train_all", "eval_all", "ablations"])
    parser.add_argument("--device", type=str, default="auto", help="cpu, cuda, mps, or auto")
    parser.add_argument("--results-dir", type=str, default="results")
    args = parser.parse_args()

    cfg = Config()
    cfg.train.device = args.device
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "train_all":
        for m in LEARNED:
            print(f"Training {m}...")
            train_model(m, cfg, str(results_dir))
        print("Done.")
        return

    if args.mode == "eval_all":
        summary = {}
        for m in LEARNED + BASELINES:
            print(f"Evaluating {m}...")
            rows = evaluate_method(m, cfg, str(results_dir))
            save_json(rows, results_dir / f"{m}_rows.json")
            summary[m] = summarize(rows)
        save_json(summary, results_dir / "summary.json")
        print(json.dumps(summary, indent=2))
        return

    if args.mode == "ablations":
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
            train_model("rvt_swarm", acfg, str(results_dir / name))
            rows = evaluate_method("rvt_swarm", acfg, str(results_dir / name))
            all_rows[name] = summarize(rows)
        save_json(all_rows, results_dir / "ablations.json")
        print(json.dumps(all_rows, indent=2))


if __name__ == "__main__":
    main()
