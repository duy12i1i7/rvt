"""CR-0W-R2: create global contract V5 and the enforced V4->V5 diff."""
from __future__ import annotations
import copy, hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import attach_canonical_hash, verify_canonical_hash
ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
def fh(p): return hashlib.sha256((R/p).read_bytes()).hexdigest()
V = {v: json.loads((R/f"rvt_swarm_clean_room_global_contract_{v}.json").read_text())
     for v in ("v1","v2","v3","v4")}
K = "rvt_swarm_clean_room_global_contract_root"
assert verify_canonical_hash(V["v4"], K)
auth = json.loads((R/"rvt_cleanroom_generator_authority_v1.json").read_text())
lock = json.loads((R/"rvt_cleanroom_dependency_lock_v1.json").read_text())

v5 = copy.deepcopy(V["v4"]); del v5[K]
v5["schema_version"] = "rvt-swarm-clean-room-global-contract/v5"
v5["name"] = "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V5"
v5["stage"] = "CR-0W-R2"
v5["cr0_source_commit"] = subprocess.run(["git","-C",str(ROOT),"rev-parse","HEAD"],
                                          capture_output=True, text=True).stdout.strip()
v5["amendment"] = {
 "amends": "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V4",
 "lineage": [f"RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V{i}" for i in (1,2,3,4)],
 "v1_root": V["v1"][K], "v2_root": V["v2"][K], "v3_root": V["v3"][K], "v4_root": V["v4"][K],
 "v1_tag": "rvt-cleanroom-cr0-v1", "v2_tag": "rvt-cleanroom-cr0r-v2",
 "v3_tag": "rvt-cleanroom-cr0s-v3", "v4_tag": "rvt-cleanroom-cr0t-v4",
 "all_prior_preserved_unmodified": True,
 "supersedes_only": [
   "the assumption that the historical V3 pilot dataset authorization can authorize "
   "clean-room roles -- it cannot, and it remains valid for pilot provenance only",
   "the V4 role-level generation seeds, which the frozen generator cannot consume"],
 "new_generation_authority": "RVT_CLEANROOM_GENERATOR_AUTHORITY_V1",
 "no_clean_room_dataset_existed": True,
 "no_clean_room_model_existed": True,
 "clean_room_generation_attempts": 0,
 "no_clean_room_outcome_informed_this_change": True,
 "scope": ["generation execution authority", "executable-equivalence definition",
           "role authorization", "budget consumer", "layout membership",
           "study/split", "seed schema", "dependency and image authority",
           "historical pilot provenance disclosure"],
 "all_other_v4_decisions": "PRESERVED",
}
v5["clean_room_generation_authority"] = {
 "authority": "RVT_CLEANROOM_GENERATOR_AUTHORITY_V1",
 "root": auth["rvt_cleanroom_generator_authority_v1_root"],
 "artifact": "results/rvt_fd24/rvt_cleanroom_generator_authority_v1.json",
 "artifact_sha256": fh("rvt_cleanroom_generator_authority_v1.json"),
 "clean_room_generation_image_digest": auth["clean_room_generation_image_digest"],
 "source_commit": auth["source_commit"],
 "dependency_lock_root": lock["rvt_cleanroom_dependency_lock_v1_root"],
 "dependency_lock_artifact_sha256": fh("rvt_cleanroom_dependency_lock_v1.json"),
 "sole_generator_authority_for_final_clean_room_data": True,
 "historical_v3_generator_authority": "valid for PILOT PROVENANCE ONLY",
 "v4_role_level_generation_seeds": "RETIRED -- historical_v4_inoperable_role_seed; "
   "not_consumed_by_generator; scientific_seed_authority superseded",
 "HISTORICAL_PILOT_SEED_PROVENANCE": "NOT_FULLY_RECONSTRUCTIBLE_FROM_REPOSITORY",
 "historical_provenance_affects_final_clean_room_inference": False,
 "global_episode_universe_root": auth["global_episode_universe_root"],
 "global_seed_ledger_root": auth["global_seed_ledger_root"],
 "generation_call_plan_root": auth["generation_call_plan_root"],
 "geometry_equivalence": auth["geometry_equivalence"],
 "seed_builder_equivalence": auth["seed_builder_equivalence"],
 "consumer_callability": auth["consumer_callability"],
}
v5["clean_room_generation_authority"]["execution_provenance_guard"] = {
 "module": "rvt_swarm/cleanroom/generation/provenance.py",
 "sha256": hashlib.sha256((ROOT/"rvt_swarm/cleanroom/generation/provenance.py").read_bytes()).hexdigest(),
 "role": "VERIFICATION_SIDE_GUARD",
 "in_generation_image": False,
 "why": "it enforces WHICH image, commit and dependency lock may be used; it is not "
   "generation code and is deliberately outside the frozen image, whose authority layer "
   "is the eight modules present at the bound source commit"}
v5["adversarial_qualification"]["generation_suite"] = {
 "path": "tests/test_cleanroom_generation.py",
 "sha256": hashlib.sha256((ROOT/"tests/test_cleanroom_generation.py").read_bytes()).hexdigest()}
sealed = attach_canonical_hash(v5, K)
(R/"rvt_swarm_clean_room_global_contract_v5.json").write_text(
    json.dumps(sealed, indent=1, sort_keys=True)+"\n", encoding="ascii")

def flat(o, p=""):
    if isinstance(o, dict):
        for k in sorted(o): yield from flat(o[k], f"{p}.{k}")
    elif isinstance(o, list): yield p, json.dumps(o, sort_keys=True)
    else: yield p, o
a = dict(flat({k:v for k,v in V["v4"].items() if k != K}))
b = dict(flat({k:v for k,v in sealed.items() if k != K}))
added = sorted(set(b)-set(a)); removed = sorted(set(a)-set(b))
changed = sorted(k for k in set(a)&set(b) if a[k] != b[k])
ALLOWED = ("clean_room_generation_authority","adversarial_qualification","amendment",
           "schema_version","name","stage","cr0_source_commit")
off = [k for k in added+removed+changed if not any(k.lstrip(".").startswith(x) for x in ALLOWED)]
FORBIDDEN = [".central_thesis",".dataset_composition",".model_families",
             ".a3_mechanism_control",".training_recipe",".family_statistic",
             ".family_selection_rule",".downstream_representative",".safety_contract",
             ".h_cl1_benefit_contract",".oracle_ceiling",".closed_loop_development_space",
             ".main_r_firewall",".main_r_failure_rule",".mechanism_study",
             ".protected_generalization",".calibration_contract",".closed_loop_architecture",
             ".disjointness_contract",".episode_universe_contract",".generation_authority",
             ".sample_size_claim_boundary",".closed_loop_hypotheses"]
untouched = {s: all(a[k]==b[k] for k in a if k.startswith(s)) for s in FORBIDDEN}
diff = attach_canonical_hash({
 "schema_version":"rvt-swarm-clean-room-contract-diff/v1",
 "from_root": V["v4"][K], "to_root": sealed[K],
 "lineage_roots": {f"v{i}": V[f"v{i}"][K] for i in (1,2,3)},
 "scope": ["generation execution authority only"],
 "added_paths": added, "removed_paths": removed, "changed_paths": changed,
 "counts": {"added":len(added),"removed":len(removed),"changed":len(changed)},
 "out_of_scope_changes": off,
 "all_unrelated_v4_decisions_preserved": not off,
 "forbidden_blocks_untouched": untouched,
 "every_forbidden_block_untouched": all(untouched.values()),
}, "clean_room_contract_v4_to_v5_diff_root")
(R/"rvt_swarm_clean_room_contract_v4_to_v5_diff.json").write_text(
    json.dumps(diff, indent=1, sort_keys=True)+"\n", encoding="ascii")
print("V5_ROOT", sealed[K])
print("V5_artifact_sha256", fh("rvt_swarm_clean_room_global_contract_v5.json"))
print("DIFF_ROOT", diff["clean_room_contract_v4_to_v5_diff_root"])
print(f"added={len(added)} removed={len(removed)} changed={len(changed)}")
print("OUT_OF_SCOPE:", off if off else "NONE")
print("ALL FORBIDDEN BLOCKS UNTOUCHED:", all(untouched.values()), f"({sum(untouched.values())}/{len(untouched)})")
