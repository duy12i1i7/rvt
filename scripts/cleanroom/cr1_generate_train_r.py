"""CR-1 TRAIN-R generation driver.

Consumes ONLY: global contract V5, generator authority V1, and the immutable
TRAIN-R pre-generation manifest. It carries no scientific constant of its own --
every family, team size, source policy, layout, seed and count is read from the
frozen manifest, and any disagreement fails closed.
"""
from __future__ import annotations

import argparse, hashlib, json, os, pathlib, sys, time

sys.path.insert(0, "/opt/rvt")
sys.path.insert(0, "/Users/udy/rvt")

from rvt_swarm.phase8.common import sha256_document, verify_canonical_hash

# The provenance guard lives OUTSIDE the frozen image on purpose: it decides
# which image may run, so it is not part of what runs. The orchestrator asserts
# it and injects the digest it launched, which the driver confirms below.
EXPECTED_IMAGE_ENV = "RVT_CLEANROOM_EXPECTED_IMAGE"

MANIFEST_ROOT = "797c27920d3273106c359113f837fc7c911746574a9bac66e7f47d1fa3ad1176"
V5_ROOT = "1d38cd511dd95e4dceb2c7c3fc8f908c31f228b2ebaae4db973c721bd3719fed"
AUTHORITY_ROOT = "4eef216e077cb353c0e1473e421d73d54876dd310f25aeb03a5543250ee30025"


class DriverError(RuntimeError):
    """A CR-1 driver violation that must fail closed."""


def load_authority(root: pathlib.Path):
    R = root / "results/rvt_fd24"
    man = json.loads((R/"cleanroom_train_r_pregeneration_manifest_v1.json").read_text())
    v5 = json.loads((R/"rvt_swarm_clean_room_global_contract_v5.json").read_text())
    auth = json.loads((R/"rvt_cleanroom_generator_authority_v1.json").read_text())
    if not verify_canonical_hash(man, "train_r_pregeneration_manifest_root"):
        raise DriverError("the TRAIN-R manifest failed its own canonical hash")
    if man["train_r_pregeneration_manifest_root"] != MANIFEST_ROOT:
        raise DriverError("manifest root is not the frozen pre-generation root")
    if v5["rvt_swarm_clean_room_global_contract_root"] != V5_ROOT:
        raise DriverError("global contract is not the frozen V5")
    if man["global_contract_v5_root"] != V5_ROOT:
        raise DriverError("manifest does not bind the frozen V5")
    if auth["rvt_cleanroom_generator_authority_v1_root"] != AUTHORITY_ROOT:
        raise DriverError("generator authority is not the frozen V1")
    if man["generator_authority_v1_root"] != AUTHORITY_ROOT:
        raise DriverError("manifest does not bind the frozen generator authority")
    launched = os.environ.get(EXPECTED_IMAGE_ENV)
    if launched is None:
        raise DriverError(
            f"{EXPECTED_IMAGE_ENV} was not injected; generation must be launched by the "
            "orchestrator, which asserts execution provenance and pins the image digest")
    if launched != man["execution_image_digest"]:
        raise DriverError(
            f"running under image {launched!r} but the frozen manifest authorizes "
            f"{man['execution_image_digest']!r}")
    if not launched.startswith("sha256:"):
        raise DriverError("image authority must be an immutable digest, never a mutable tag")
    return man, v5, auth


def source_task(root: pathlib.Path, record, man):
    """Build the frozen OfficialSourceTask for one manifest record."""
    from rvt_swarm.phase9g0r.compiler import OfficialSourceTask
    lay = {l["layout_id"]: l for l in man["layouts"]}
    if record["layout_id"] not in lay:
        raise DriverError(f"layout {record['layout_id']!r} is not in the frozen manifest")
    if lay[record["layout_id"]]["layout_sha256"] != record["layout_sha256"]:
        raise DriverError("layout hash disagrees with the frozen manifest")
    if record["family"] not in man["families"]:
        raise DriverError(f"family {record['family']!r} outside the frozen manifest")
    if record["team_size"] not in man["team_sizes"]:
        raise DriverError(f"team size {record['team_size']!r} outside the frozen manifest")
    if record["source_policy"] not in man["source_policies"]:
        raise DriverError(f"source policy {record['source_policy']!r} outside the frozen manifest")
    if not 0 <= record["episode_index"] < man["episodes_per_cell"]:
        raise DriverError("episode index outside the frozen per-cell budget")
    from rvt_swarm.phase8 import scenario as S
    horizon = float(S._layout(record["family"],
                              lay[record["layout_id"]]["generator_split_namespace"],
                              lay[record["layout_id"]]["variant_index"]).episode_horizon_seconds)
    return OfficialSourceTask(
        job_id=record["source_episode_id"], dataset_id=man["dataset_id"],
        study=man["study"], split=man["split"],
        layout_source_split=lay[record["layout_id"]]["generator_split_namespace"],
        family=record["family"], layout_id=record["layout_id"],
        layout_sha256=record["layout_sha256"], team_size=record["team_size"],
        source_class=record["source_policy"], episode_index=record["episode_index"],
        horizon_seconds=horizon, seeds=dict(record["seeds"]))


def generate(root: pathlib.Path, out_dir: pathlib.Path, limit=None, start=0):
    from rvt_swarm.phase9g0r.compiler_v2 import (
        compile_recoverability_v2_candidate_tasks, execute_v2_source_acquisition,
    )
    man, _, _ = load_authority(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = man["expected_episode_records"]
    if len(records) != man["expected_source_episode_count"]:
        raise DriverError("manifest record count disagrees with its own expected count")
    todo = records[start:] if limit is None else records[start:start+limit]
    log = out_dir / "generation_attempts.jsonl"
    done = 0
    for rec in todo:
        eid = rec["source_episode_id"]
        dest = out_dir / "episodes" / (hashlib.sha256(eid.encode()).hexdigest() + ".json")
        if dest.exists():
            done += 1; continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        task = source_task(root, rec, man)
        acq = execute_v2_source_acquisition(root, task)
        events = compile_recoverability_v2_candidate_tasks(acq)
        payload = {
            "source_episode_id": eid, "role": man["role"], "dataset_id": man["dataset_id"],
            "study": man["study"], "split": man["split"], "family": rec["family"],
            "team_size": rec["team_size"], "source_policy": rec["source_policy"],
            "episode_index": rec["episode_index"], "layout_id": rec["layout_id"],
            "layout_sha256": rec["layout_sha256"], "seeds": dict(rec["seeds"]),
            "acquisition": acq.as_dict(),
            "selected_event_count": acq.selected_event_count,
            "M": acq.M, "terminal_cause": acq.terminal_cause,
            "decision_events": [
                {"event_id": e.event_id, "event_slot_index": e.event_slot_index,
                 "resolved_control_step": e.resolved_control_step,
                 "resolved_timestamp_seconds": e.resolved_timestamp_seconds,
                 "replicas_per_candidate": e.replicas_per_candidate,
                 "candidate_replica_jobs": [dict(j) for j in e.candidate_replica_jobs]}
                for e in events],
            "manifest_root": man["train_r_pregeneration_manifest_root"],
            "execution_image_digest": man["execution_image_digest"],
        }
        dest.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="ascii")
        with log.open("a") as fh:
            fh.write(json.dumps({"source_episode_id": eid, "seconds": round(time.time()-t0, 3),
                                 "M": acq.M, "selected": acq.selected_event_count,
                                 "events": len(events)}, sort_keys=True) + "\n")
        done += 1
    return {"completed": done, "requested": len(todo)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/opt/rvt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--start", type=int, default=0)
    a = ap.parse_args()
    print(json.dumps(generate(pathlib.Path(a.root), pathlib.Path(a.out),
                              a.limit, a.start), sort_keys=True))
