"""Measure the real communication cost of the decentralized runtime (Task 10).

Runs `rvt_swarm.decentralized.runtime.simulate_decentralized_episode` -- the
same closed-loop function every other decentralized figure comes from -- on the
VALIDATION layouts, and counts the messages it actually sends. Nothing is
modelled or extrapolated: the two objects that do the sending, `RadioChannel`
and `ConsensusNode`, are replaced by the instrumented subclasses in
`comm_cost.py`, which record the encoded payload of every message that really
crosses them.

Two categories are measured:

  beacon           one per robot per control step (t_comm == t_ctrl == 0.15 s)
  score_consensus  k_score rounds per robot per decision epoch

Two are NOT, and are reported as such:

  trigger          `epoch.py` is not wired into `runtime.py`; no trigger
  mode_confirmation message and no confirmation message is ever sent. Their
                   schemas are verified (21 B, 16 B) but their traffic is
                   unexercised. `pending=True` on those rows.

Usage
-----
    cd /Users/udy/rvt && PYTHONPATH=. .venv/bin/python \
        scripts/measure_communication_cost.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config                              # noqa: E402
from rvt_swarm.decentralized import comm_cost as CC              # noqa: E402
from rvt_swarm.decentralized import runtime as RT                # noqa: E402
from rvt_swarm.decentralized.system_model import (CommParams,    # noqa: E402
                                                  ConsensusParams)
from rvt_swarm.layouts import build_layouts                      # noqa: E402
from rvt_swarm.splits import VALIDATION, setting_episode_seeds   # noqa: E402

FAMILIES = ("line_corridor", "keep_line_keep", "keep_open", "ambiguous")
SIZES = (4, 6)
EPISODES = 2
DECISION_INTERVAL = 25
K_SCORE = 4
OUT = REPO / "results" / "decentralized" / "communication_cost"


class _EpochIndexedAccountant(CC.MessageAccountant):
    """Accountant that files each message under the decision epoch it belongs to.

    The runtime re-decides on `step % decision_interval == 0`, so the decision
    epoch a message belongs to is `step // decision_interval`. Deriving it from
    the step rather than from a counter keeps the k_score consensus rounds --
    which occupy control steps s .. s+k_score-1 -- inside the epoch that opened
    them.
    """

    def __init__(self, n_robots: int, decision_interval: int, **kw) -> None:
        super().__init__(n_robots, **kw)
        self.decision_interval = int(decision_interval)

    def record_sent_bytes(self, message_type, sender_id, payload, step,
                          round_index: int = 0,
                          decision_index: Optional[int] = None) -> int:
        if decision_index is None:
            decision_index = int(step) // self.decision_interval
        return super().record_sent_bytes(message_type, sender_id, payload,
                                         step, round_index, decision_index)

    def record_received_bytes(self, message_type, receiver_id, payload, step,
                              decision_index: Optional[int] = None) -> int:
        if decision_index is None:
            decision_index = int(step) // self.decision_interval
        return super().record_received_bytes(message_type, receiver_id,
                                             payload, step, decision_index)


def measured_episode(cfg: Config, layout, n: int, seed: int,
                     mode_rule: str) -> Dict[str, object]:
    """One closed-loop episode, with every transmitted message accounted."""
    comm = CommParams()
    acct = _EpochIndexedAccountant(
        n, DECISION_INTERVAL, params=comm,
        label=f"{layout.layout_id} n={n} seed={seed} rule={mode_rule}")

    def channel_factory(params, seed=0):
        return CC._AccountingRadioChannel(params, seed=seed, accountant=acct)

    class _Node(CC._AccountingConsensusNode):
        accountant = acct

    real_channel, real_node = RT.RadioChannel, RT.ConsensusNode
    RT.RadioChannel, RT.ConsensusNode = channel_factory, _Node
    try:
        res = RT.simulate_decentralized_episode(
            cfg, layout, n, seed, mode_rule=mode_rule, k_score=K_SCORE,
            use_consensus=True, comm=comm, cons=ConsensusParams(),
            decision_interval=DECISION_INTERVAL)
    finally:
        RT.RadioChannel, RT.ConsensusNode = real_channel, real_node

    steps = int(res["completion_steps"])
    epochs = int(res["n_decisions"])
    acct.set_episode_steps(steps)
    acct.assert_consistent()
    rep = acct.report()

    # The counts must be exactly what the protocol's cadence predicts. If they
    # are not, the instrumentation is measuring something other than the traffic
    # and the table below would be fiction.
    beacons = rep["categories"][CC.BEACON]["messages"]
    scores = rep["categories"][CC.SCORE]["messages"]
    assert beacons == n * steps, (beacons, n, steps)
    assert scores == n * K_SCORE * epochs, (scores, n, K_SCORE, epochs)
    assert rep["categories"][CC.TRIGGER]["messages"] == 0
    assert rep["categories"][CC.CONFIRM]["messages"] == 0
    assert rep["total"]["bytes"] == acct.payload_bytes_ledger_total()

    return {"layout": layout.layout_id, "family": layout.family, "n": n,
            "seed": seed, "mode_rule": mode_rule, "steps": steps,
            "decision_epochs": epochs, "success": float(res["success"]),
            "report": rep}


def aggregate(rows: List[Dict[str, object]]) -> Dict[str, object]:
    reports = [r["report"] for r in rows]
    mean = CC.mean_of_reports(reports)
    return {
        "episodes": len(rows),
        "steps_mean": sum(float(r["steps"]) for r in rows) / len(rows),
        "decision_epochs_mean": (sum(float(r["decision_epochs"]) for r in rows)
                                 / len(rows)),
        "success_mean": sum(float(r["success"]) for r in rows) / len(rows),
        "mean_report": mean,
    }


def row_of(agg: Dict[str, object], category: Optional[str]) -> Dict[str, float]:
    m = agg["mean_report"]
    c = m["total"] if category is None else m["categories"][category]
    return {
        "messages": c["messages"],
        "bytes": c["bytes"],
        "bytes_per_robot_per_episode": c["bytes_per_robot_per_episode"],
        "bytes_per_robot_per_decision": c["bytes_per_robot_per_decision"],
        "peak_bytes_per_second": c["peak_bytes_per_second"],
        "average_bytes_per_second": c["average_bytes_per_second"],
        "peak_bytes_per_second_per_robot": c["peak_bytes_per_second_per_robot"],
        "average_bytes_per_second_per_robot": c["average_bytes_per_second_per_robot"],
        "received_messages": c["received_messages"],
        "received_bytes": c["received_bytes"],
        "pending": bool(c["pending"]),
    }


def print_table(title: str, agg: Dict[str, object]) -> None:
    print()
    print(title)
    hdr = ("{:<28} {:>6} {:>9} {:>11} {:>11} {:>10} {:>10}".format(
        "category", "B/msg", "messages", "B/rob/ep", "B/rob/dec",
        "peak B/s", "avg B/s"))
    print(hdr)
    print("-" * len(hdr))
    m = agg["mean_report"]
    for name in list(CC.MESSAGE_TYPES) + [None]:
        c = m["total"] if name is None else m["categories"][name]
        label = "TOTAL" if name is None else name
        if c["pending"]:
            label += " [NOT YET EXERCISED]"
        wire = c["wire_bytes_per_message"]
        print("{:<28} {:>6} {:>9.1f} {:>11.1f} {:>11.1f} {:>10.1f} {:>10.1f}"
              .format(label[:28], "-" if wire is None else wire, c["messages"],
                      c["bytes_per_robot_per_episode"],
                      c["bytes_per_robot_per_decision"],
                      c["peak_bytes_per_second"], c["average_bytes_per_second"]))


def main() -> int:
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.env.scenarios = ["cluttered"]

    print("schema verification (before any measurement):")
    for name, row in CC.assert_schema_sizes().items():
        print("  {:<18} declared {:>3} B  field-sum {:>3} B  measured {:>3} B  "
              "provisional={}  ok={}".format(
                  name, row["declared_bytes"], row["declared_field_sum"],
                  row["measured_bytes"], row["provisional"], row["ok"]))
    print("  epoch module:", CC.epoch_module_status())

    layouts = [l for l in build_layouts("val") if l.family in FAMILIES]
    print("\nvalidation layouts: {} in families {}".format(
        len(layouts), ", ".join(FAMILIES)))

    all_rows: List[Dict[str, object]] = []
    for rule in ("clearance", "always_line"):
        for layout in layouts:
            for n in SIZES:
                for seed in setting_episode_seeds(VALIDATION, 0, n, EPISODES, 0):
                    all_rows.append(measured_episode(cfg, layout, n, seed, rule))
        print("  {} arm: {} episodes done".format(rule, len(all_rows)))

    primary = [r for r in all_rows if r["mode_rule"] == "clearance"]
    out: Dict[str, object] = {
        "schema": CC.verify_schema_sizes(),
        "epoch_module": CC.epoch_module_status(),
        "t_ctrl_seconds": CommParams().t_ctrl,
        "decision_interval_steps": DECISION_INTERVAL,
        "k_score": K_SCORE,
        "families": list(FAMILIES),
        "sizes": list(SIZES),
        "episodes_per_setting": EPISODES,
        "n_episodes_total": len(all_rows),
        "pooled": {},
        "by_n": {},
        "by_family": {},
        "by_arm": {},
        "episodes": [{k: v for k, v in r.items() if k != "report"}
                     for r in all_rows],
    }

    pooled = aggregate(primary)
    out["pooled"] = {"summary": {k: v for k, v in pooled.items()
                                 if k != "mean_report"},
                     "categories": {name: row_of(pooled, name)
                                    for name in CC.MESSAGE_TYPES},
                     "total": row_of(pooled, None)}
    print_table("POOLED over the clearance arm ({} episodes)".format(len(primary)),
                pooled)

    for n in SIZES:
        sub = [r for r in primary if r["n"] == n]
        agg = aggregate(sub)
        out["by_n"][str(n)] = {"summary": {k: v for k, v in agg.items()
                                           if k != "mean_report"},
                               "categories": {name: row_of(agg, name)
                                              for name in CC.MESSAGE_TYPES},
                               "total": row_of(agg, None)}
        print_table("N = {} ({} episodes)".format(n, len(sub)), agg)

    for fam in FAMILIES:
        sub = [r for r in primary if r["family"] == fam]
        agg = aggregate(sub)
        out["by_family"][fam] = {"summary": {k: v for k, v in agg.items()
                                             if k != "mean_report"},
                                 "categories": {name: row_of(agg, name)
                                                for name in CC.MESSAGE_TYPES},
                                 "total": row_of(agg, None)}
        print_table("family = {} ({} episodes)".format(fam, len(sub)), agg)

    for rule in ("clearance", "always_line"):
        sub = [r for r in all_rows if r["mode_rule"] == rule]
        agg = aggregate(sub)
        out["by_arm"][rule] = {"summary": {k: v for k, v in agg.items()
                                           if k != "mean_report"},
                               "categories": {name: row_of(agg, name)
                                              for name in CC.MESSAGE_TYPES},
                               "total": row_of(agg, None)}
        print_table("arm = {} ({} episodes)".format(rule, len(sub)), agg)

    # per-robot-per-step airtime, the arm-independent quantity
    print()
    for n in SIZES:
        sub = [r for r in all_rows if r["n"] == n]
        b_step = sorted({round(r["report"]["categories"][CC.BEACON]["bytes"]
                               / n / r["steps"], 9) for r in sub})
        s_epoch = sorted({round(r["report"]["categories"][CC.SCORE]["bytes"]
                                / n / r["decision_epochs"], 9) for r in sub})
        print("N={}: beacon B/robot/control-step over {} episodes: {}   "
              "score B/robot/decision-epoch: {}"
              .format(n, len(sub), b_step, s_epoch))
    steps = sorted(int(r["steps"]) for r in primary)
    print("clearance arm episode length: min {} median {} max {} control steps"
          .format(steps[0], steps[len(steps) // 2], steps[-1]))
    print("decision epochs per episode: {}".format(
        sorted({int(r["decision_epochs"]) for r in primary})))

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "measured_val.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True))
    print("\nwrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
