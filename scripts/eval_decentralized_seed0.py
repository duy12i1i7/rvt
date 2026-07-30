"""Closed-loop seed-0 evaluation of the decentralized system (Tasks 12-14).

Validation layouts only. Final-test layouts are never loaded.

Two decision regimes are reported separately, because they answer different
questions and conflating them would hide the main finding:

  single   decide once at t=0 and commit for the episode. Matches the frozen
           Recovery Event V2 label semantics, under which the labels were
           generated, and the previous pilot's selector-only protocol.
  periodic re-decide every `decision_interval` steps, per the Task 6 epoch
           protocol. This is what the decentralized design specifies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config  # noqa: E402
from rvt_swarm.decentralized.models import build_selector  # noqa: E402
from rvt_swarm.decentralized.runtime import simulate_decentralized_episode  # noqa: E402
from rvt_swarm.decentralized.system_model import KEEP, LINE, CommParams  # noqa: E402
from rvt_swarm.layouts import build_layouts  # noqa: E402
from rvt_swarm.splits import VALIDATION, setting_episode_seeds  # noqa: E402

RESULTS = REPO / "results" / "decentralized" / "dry_run_seed0"
FAMILIES = ("line_corridor", "keep_line_keep", "keep_open", "ambiguous")
EPISODES = 2
BIG = 10 ** 9   # effectively "never re-decide"


def load(method):
    ck = torch.load(RESULTS / f"{method}_seed0.pt", weights_only=False)
    m = build_selector(method)
    m.load_state_dict(ck["model"])
    m.eval()
    return m, int(ck["k_score"])


def sweep(cfg, fn, families=FAMILIES, sizes=(4, 6)):
    """Run one arm over the validation grid; return pooled + stratified means."""
    rows = []
    for lay in [l for l in build_layouts("val") if l.family in families]:
        for n in sizes:
            for sd in setting_episode_seeds(VALIDATION, 0, n, EPISODES, 0):
                r = fn(lay, n, sd)
                rows.append({"family": lay.family, "n": n, **r})
    def agg(sub, key):
        v = [r[key] for r in sub if not (isinstance(r[key], float) and np.isnan(r[key]))]
        return float(np.mean(v)) if v else float("nan")
    keys = ("success", "collision_free", "goal_reached", "deadlock",
            "irreversible_collapse", "completion_steps", "formation_rms_error",
            "time_in_formation_tube", "full_agreement", "component_agreement",
            "consensus_residual", "disagreement_fraction",
            "collisions_during_disagreement")
    out = {"pooled": {k: agg(rows, k) for k in keys}, "by_family": {}, "by_n": {}}
    for f in sorted({r["family"] for r in rows}):
        out["by_family"][f] = {k: agg([r for r in rows if r["family"] == f], k) for k in keys}
    for n in sorted({r["n"] for r in rows}):
        out["by_n"][str(n)] = {k: agg([r for r in rows if r["n"] == n], k) for k in keys}
    out["n_episodes"] = len(rows)
    return out


def main() -> int:
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.env.scenarios = ["cluttered"]
    rec, k_rec = load("decentralized_recovery_selector")
    dir_, k_dir = load("decentralized_direct_selector")
    print(f"selected K_score: recovery={k_rec} direct={k_dir}")

    arms = {}

    def add(name, **kw):
        interval = kw.pop("decision_interval", BIG)
        print(f"  {name} ...", flush=True)
        arms[name] = sweep(cfg, lambda l, n, s: simulate_decentralized_episode(
            cfg, l, n, s, decision_interval=interval, **kw))
        print(f"    success={arms[name]['pooled']['success']:.3f} "
              f"agree={arms[name]['pooled']['full_agreement']:.3f}")

    print("REFERENCE ARMS")
    add("always_keep_local", forced_mode=KEEP)
    add("always_line_local", forced_mode=LINE)
    add("clearance_no_comm", mode_rule="clearance", use_consensus=False, k_score=0)
    add("clearance_with_consensus", mode_rule="clearance", k_score=k_rec)

    print("LEARNED, SINGLE DECISION AT t=0")
    add("recovery_single_noconsensus", selector=rec, use_consensus=False, k_score=0)
    add("recovery_single_consensus", selector=rec, k_score=k_rec)
    add("direct_single_consensus", selector=dir_, k_score=k_dir)

    print("LEARNED, PERIODIC EPOCHS (Task 6 protocol)")
    add("recovery_periodic_consensus", selector=rec, k_score=k_rec, decision_interval=25)
    add("recovery_periodic_noconsensus", selector=rec, use_consensus=False,
        k_score=0, decision_interval=25)

    # ---- Task 14 communication stress, validation only --------------------
    print("STRESS SWEEPS")
    stress = {}
    for loss in (0.0, 0.1, 0.3, 0.5):
        c = CommParams(packet_loss=loss)
        stress[f"packet_loss_{loss}"] = sweep(cfg, lambda l, n, s: simulate_decentralized_episode(
            cfg, l, n, s, selector=rec, k_score=k_rec, comm=c))
        print(f"  loss {loss}: success={stress[f'packet_loss_{loss}']['pooled']['success']:.3f} "
              f"agree={stress[f'packet_loss_{loss}']['pooled']['full_agreement']:.3f}")
    for d in (0, 1, 2, 5):
        c = CommParams(delay_steps=d)
        stress[f"delay_{d}"] = sweep(cfg, lambda l, n, s: simulate_decentralized_episode(
            cfg, l, n, s, selector=rec, k_score=k_rec, comm=c))
        print(f"  delay {d}: success={stress[f'delay_{d}']['pooled']['success']:.3f} "
              f"agree={stress[f'delay_{d}']['pooled']['full_agreement']:.3f}")
    for frac in (1.0, 0.75, 0.5):
        c = CommParams(r_comm=3.0 * frac)
        stress[f"r_comm_{frac}"] = sweep(cfg, lambda l, n, s: simulate_decentralized_episode(
            cfg, l, n, s, selector=rec, k_score=k_rec, comm=c))
        print(f"  r_comm x{frac}: success={stress[f'r_comm_{frac}']['pooled']['success']:.3f} "
              f"agree={stress[f'r_comm_{frac}']['pooled']['full_agreement']:.3f} "
              f"comp={stress[f'r_comm_{frac}']['pooled']['component_agreement']:.3f}")

    out = {"arms": arms, "stress": stress,
           "k_score": {"recovery": k_rec, "direct": k_dir},
           "episodes_per_cell": EPISODES}
    (RESULTS / "closed_loop.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {RESULTS/'closed_loop.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
