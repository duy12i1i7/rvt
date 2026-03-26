from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rvt_swarm.config import Config
from rvt_swarm.dataset import generate_dataset
from rvt_swarm.evaluate import evaluate_method, summarize
from rvt_swarm.train import train_model


def build_config(args: argparse.Namespace) -> Config:
    cfg = Config()
    cfg.train.device = args.device
    cfg.train.n_workers = args.workers
    cfg.train.expert_episodes = args.episodes
    cfg.train.batch_size = args.batch_size
    cfg.train.epochs_rvt_swarm = args.epochs
    cfg.train.rollout_val_interval = args.rollout_interval
    cfg.train.rollout_val_episodes_per_setting = args.rollout_eps
    cfg.train.rollout_val_recheck_episodes_per_setting = args.recheck_eps
    cfg.train.rollout_val_topk_checkpoints = args.topk
    cfg.eval.episodes_per_setting = args.eval_eps
    return cfg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=str, default="results_scorefirst_smoke")
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--eval-eps", type=int, default=3)
    parser.add_argument("--rollout-interval", type=int, default=10)
    parser.add_argument("--rollout-eps", type=int, default=1)
    parser.add_argument("--recheck-eps", type=int, default=2)
    parser.add_argument("--topk", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.results_dir)
    root.mkdir(parents=True, exist_ok=True)

    base = build_config(args)
    print("Generating shared smoke dataset...")
    dataset = generate_dataset(base, episodes=args.episodes)

    cfgs = {
        "full": base,
        "no_topology": copy.deepcopy(base),
    }
    cfgs["no_topology"].method.use_topology = False

    summary = {}
    for name, cfg in cfgs.items():
        out_dir = root / name
        print(f"=== TRAIN {name} ===")
        train_model("rvt_swarm", cfg, str(out_dir), dataset=dataset)
        print(f"=== EVAL {name} ===")
        rows = evaluate_method("rvt_swarm", cfg, str(out_dir))
        stats = summarize(rows)
        summary[name] = stats
        print(json.dumps({name: stats}, indent=2))

    with open(root / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("SMOKE_SUMMARY")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
