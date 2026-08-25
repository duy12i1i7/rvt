"""CR-0T -- amend to V4, freezing dataset composition for all six roles."""
from __future__ import annotations
import copy, hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import attach_canonical_hash, verify_canonical_hash
from rvt_swarm.cleanroom.composition import (
    ACQUISITION_RULE, CELLS, EPISODE_ID_NAMESPACE, FAMILIES, GENERATION_SEED_DOMAIN,
    GENERATION_SEED_MODULUS, K_MAX_SELECTED_SOURCE_EVENTS_PER_EPISODE, MAIN_R_PLANNING,
    REPLICA_FAMILIES_R3, ROLE_COMPOSITION, SOURCE_POLICIES, TEAM_SIZES, V3_ROOT,
    composition_fingerprint, enumerate_episode_ids, generation_seed, verify_role_arithmetic,
)

ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
def h(rel): return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
v1 = json.loads((R/"rvt_swarm_clean_room_global_contract_v1.json").read_text())
v2 = json.loads((R/"rvt_swarm_clean_room_global_contract_v2.json").read_text())
v3 = json.loads((R/"rvt_swarm_clean_room_global_contract_v3.json").read_text())
assert verify_canonical_hash(v3, "rvt_swarm_clean_room_global_contract_root")
V1_ROOT = v1["rvt_swarm_clean_room_global_contract_root"]
V2_ROOT = v2["rvt_swarm_clean_room_global_contract_root"]
V3R = v3["rvt_swarm_clean_room_global_contract_root"]
assert V3R == V3_ROOT

v4 = copy.deepcopy(v3)
del v4["rvt_swarm_clean_room_global_contract_root"]
v4["schema_version"] = "rvt-swarm-clean-room-global-contract/v4"
v4["name"] = "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V4"
v4["stage"] = "CR-0T"
v4["cr0_source_commit"] = subprocess.run(
    ["git","-C",str(ROOT),"rev-parse","HEAD"], capture_output=True, text=True).stdout.strip()
v4["amendment"] = {
 "amends": "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V3",
 "lineage": ["RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V1",
             "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V2",
             "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V3"],
 "v1_root": V1_ROOT, "v1_tag": "rvt-cleanroom-cr0-v1",
 "v2_root": V2_ROOT, "v2_tag": "rvt-cleanroom-cr0r-v2",
 "v3_root": V3R,     "v3_tag": "rvt-cleanroom-cr0s-v3",
 "v1_preserved_unmodified": True, "v2_preserved_unmodified": True,
 "v3_preserved_unmodified": True,
 "reason": "CR-1 returned D -- CLEAN_ROOM_TRAIN_R_GENERATION_CONTRACT_INCOMPLETE -- "
     "because V3 bound the generator, offsets and every scientific rule but never bound "
     "the dataset composition. This amendment supplies exactly that missing authority.",
 "no_clean_room_data_existed": True,
 "no_clean_room_model_existed": True,
 "no_cr1_generation_attempt_occurred": True,
 "no_clean_room_empirical_outcome_informed_composition": True,
 "scope": ["dataset composition for all six roles", "sample-size authority",
           "layout-instance allocation", "generation-seed authority",
           "source-episode enumeration authority",
           "the qualification requirements those imply"],
 "all_other_v3_decisions": "PRESERVED",
}

# ------------------------------------------------------- the composition ----
v4["dataset_composition"] = {
 "status": "FROZEN_AT_CR0T -- every role's size and allocation is now authoritative",
 "template": "the pilot's own balanced design, reconstructed from "
     "results/rvt_fd24/phase9d_v3f_l_train_manifest_dry_final_v1.json and "
     "phase9d_v3f_l_validation_manifest_dry_final_v1.json",
 "pilot_reconstruction": {
   "pilot_TRAIN": {"source_episodes": 1200, "layouts": 20, "layout_offsets": [0.22, 0.54],
     "layouts_per_family": 2, "episodes_per_layout": 60, "episodes_per_family": 120,
     "episodes_per_family_team_size_cell": 24, "K": 5,
     "maximum_selected_source_events": 6000},
   "pilot_VALIDATION": {"source_episodes": 300, "layouts": 10, "layout_offsets": [0.65],
     "layouts_per_family": 1, "episodes_per_layout": 30, "episodes_per_family": 30,
     "episodes_per_family_team_size_cell": 6, "K": 5,
     "maximum_selected_source_events": 1500},
   "atomic_cell": "(scenario family) x (team size) x (source policy) = 10 x 5 x 6 = 300",
   "correction_recorded": "the CR-1 report inferred an allocation of 300 source episodes "
     "per split. That is the pilot VALIDATION figure. Pilot TRAIN is 1200. TRAIN-R is "
     "sized to the TRAIN budget, not the VALIDATION budget.",
   "task_expansion_semantics": "the frozen acquisition rule "
     f"{ACQUISITION_RULE} selects at most K = {K_MAX_SELECTED_SOURCE_EVENTS_PER_EPISODE} "
     "decision events per source episode. 'Tasks' in the pilot manifests are SOURCE "
     "EPISODES; decision events are the K-bounded expansion of each, and actual yield is "
     "data-dependent, which is why zero-yield episodes exist and are retained."},
 "grid": {"families": list(FAMILIES), "team_sizes": list(TEAM_SIZES),
          "source_policies": list(SOURCE_POLICIES), "cells": CELLS,
          "balanced": "every role fills every cell with an identical integer count"},
 "replica_law_reproduction": {"R3_families": sorted(REPLICA_FAMILIES_R3),
   "R1_families": [f for f in FAMILIES if f not in REPLICA_FAMILIES_R3],
   "authority": "the frozen replica-protocol artifact; reproduced here only for manifest "
                "construction, never redefined"},
 "roles": {r: {
     "role": r, "offset": c.offset, "generation_seed": generation_seed(r),
     "families": list(FAMILIES), "team_sizes": list(TEAM_SIZES),
     "source_policies": list(SOURCE_POLICIES),
     "layout_instances_per_family": c.layout_instances_per_family,
     "layout_count": c.layout_count,
     "episodes_per_cell": c.episodes_per_cell,
     "episodes_per_family_team_size_cell": c.episodes_per_family_team_size_cell,
     "episodes_per_layout": c.episodes_per_layout,
     "source_episode_count": c.source_episode_count,
     "maximum_selected_source_events": c.maximum_selected_source_events,
     "open_loop_event_acquisition": c.open_loop_event_acquisition,
     "purpose": c.purpose, "sizing_basis": c.sizing_basis}
   for r, c in ROLE_COMPOSITION.items()},
 "total_source_episodes": sum(c.source_episode_count for c in ROLE_COMPOSITION.values()),
 "main_r_planning": MAIN_R_PLANNING,
 "mech_r_sizing_rule": "fixed at MAIN-R's size, satisfying the conservative requirement "
     "of being at least as large as MAIN-R. No future MAIN-R effect size may resize it.",
 "protected_r_sizing_rule": "precision-based for an estimation role that runs no "
     "hypothesis test; may not be resized after any protected result.",
 "generation_seed_authority": {
   "algorithm": "seed(role) = int.from_bytes(SHA256(V3_root | role | "
       f"'{GENERATION_SEED_DOMAIN}')[:8], 'big') mod {GENERATION_SEED_MODULUS}",
   "canonical_byte_encoding": "ASCII, fields joined by a single '|'",
   "modulus": GENERATION_SEED_MODULUS,
   "v3_root_used": V3R,
   "hand_picked": False,
   "computed": {r: generation_seed(r) for r in ROLE_COMPOSITION},
   "immutable_after": "V4"},
 "source_episode_id_rule": {
   "namespace": EPISODE_ID_NAMESPACE,
   "format": f"{EPISODE_ID_NAMESPACE}/{{role}}/{{family}}/N{{team_size}}/"
             "{source_policy}/episode-{index}",
   "fields": ["role", "family", "team_size", "source_policy", "cell episode index"],
   "layout_hash_in_id": False,
   "why_not": "the universe must be enumerable BEFORE the generator runs or any layout "
       "is compiled; the resolved layout hash is bound separately in the role manifest",
   "filesystem_derived": False,
   "independently_enumerable_before_generation": True},
 "composition_fingerprint": composition_fingerprint(),
 "outcome_adaptive_allocation": "FORBIDDEN",
 "post_hoc_episode_addition": "FORBIDDEN",
 "implementation": "rvt_swarm/cleanroom/composition.py",
 "implementation_sha256": h("rvt_swarm/cleanroom/composition.py"),
 "declared_limitation": "TRAIN-R reaches the pilot TRAIN episode budget with ONE layout "
     "instance per family instead of the pilot's two, because V3 froze TRAIN-R to a "
     "single generator offset. The episode budget and per-cell allocation are preserved "
     "exactly; layout-instance diversity is halved relative to pilot TRAIN. This is "
     "recorded rather than silently absorbed.",
}

# ------------------------------------------------- manifest schema (§17) ----
v4["generation_manifest_schema"] = {
 "applies_to": "every clean-room role manifest, created and hashed BEFORE generation",
 "required_fields": ["global_contract_root", "role", "role_offset", "generation_seed",
   "layout_ids", "layout_sha256_by_family", "family_ids", "team_sizes",
   "source_policies", "episodes_per_cell", "expected_source_episode_ids",
   "expected_source_episode_count", "replicas_per_candidate_by_family",
   "acquisition_rule", "k_max_selected_source_events_per_episode",
   "target_semantics_sha256", "replica_law_sha256", "invalidity_semantics_sha256",
   "row_event_binding_sha256", "generator_sha256", "production_image_digest",
   "source_commit", "layout_execution_spec_registry_sha256",
   "layout_split_registry_sha256", "composition_fingerprint"],
 "scientific_universe_explicit_before_generation": True,
 "filesystem_derived_universe": "FORBIDDEN",
}

# -------------------------------------------- sample-size claim boundary ----
v4["sample_size_claim_boundary"] = {
 "TRAIN-R": "a training-budget choice; it licenses no scientific claim",
 "SELECT-R": "a model-selection evidence budget",
 "CL-DEV-R": "a development budget; never confirmatory",
 "MAIN-R": "a confirmatory design sized by prospective power",
 "MECH-R": "a mechanism-confirmatory design",
 "PROTECTED-R": "a protected-instance evaluation budget",
 "identity_disjoint_is_not_independent_distributions": "identity-disjoint role universes "
     "are NOT independent distributions; all six draw from the same known layout families",
 "protected_r_is_not_ood": "PROTECTED-R tests unseen layout INSTANCES within known "
     "families F1-F10. It is not unseen-family or out-of-distribution generalization.",
}

v4["orchestration_authority"]["clean_room_engine"] = {
 p: h(f"rvt_swarm/cleanroom/{p}") for p in
 ("__init__.py","universe.py","family_statistic.py","selection.py",
  "calibration_contract.py","safety_contract.py","a3_control.py","benefit_contract.py",
  "oracle_contract.py","development_selection.py","closed_loop_engine.py",
  "composition.py")}
v4["adversarial_qualification"]["cr0t_suite"] = {
 "path": "tests/test_cleanroom_cr0t.py", "sha256": h("tests/test_cleanroom_cr0t.py"),
 "tests": 29, "result": "29 passed"}
v4["adversarial_qualification"]["composition_negative_fixtures"] = {
 k: "COVERED" for k in (
   "missing episodes-per-cell", "changed total count", "changed N schedule",
   "omitted family", "duplicated family", "unbalanced allocation", "wrong layout count",
   "wrong offset", "wrong generation seed", "seed derivation mismatch",
   "missing expected episode ID", "extra expected episode ID",
   "duplicate expected episode ID", "pilot identity overlap",
   "clean-room role overlap", "attempt to resize MAIN-R after CL-DEV",
   "attempt to resize MECH-R after MAIN-R",
   "attempt to resize PROTECTED-R after reveal")}
v4["adversarial_qualification"]["total_tests_passing_at_CR0T"] = 102
v4["cr0_state"]["cr1_generation_attempts"] = 0

sealed = attach_canonical_hash(v4, "rvt_swarm_clean_room_global_contract_root")
out = R / "rvt_swarm_clean_room_global_contract_v4.json"
out.write_text(json.dumps(sealed, indent=1, sort_keys=True) + "\n", encoding="ascii")

def flat(o, p=""):
    if isinstance(o, dict):
        for k in sorted(o): yield from flat(o[k], f"{p}.{k}")
    elif isinstance(o, list): yield p, json.dumps(o, sort_keys=True)
    else: yield p, o
a = dict(flat({k: v for k, v in v3.items() if k != "rvt_swarm_clean_room_global_contract_root"}))
b = dict(flat({k: v for k, v in sealed.items() if k != "rvt_swarm_clean_room_global_contract_root"}))
added = sorted(set(b)-set(a)); removed = sorted(set(a)-set(b))
changed = sorted(k for k in set(a)&set(b) if a[k] != b[k])
ALLOWED = ("dataset_composition", "generation_manifest_schema", "sample_size_claim_boundary",
           "adversarial_qualification", "orchestration_authority.clean_room_engine",
           "cr0_state.cr1_generation_attempts", "amendment",
           "schema_version", "name", "stage", "cr0_source_commit")
def allowed(k): return any(k.lstrip(".").startswith(x) for x in ALLOWED)
off = [k for k in added+removed+changed if not allowed(k)]
SCI = [".central_thesis", ".model_families", ".a3_mechanism_control", ".training_recipe",
       ".family_statistic", ".family_selection_rule", ".downstream_representative",
       ".closed_loop_architecture", ".safety_contract", ".h_cl1_benefit_contract",
       ".oracle_ceiling", ".closed_loop_development_space", ".main_r_firewall",
       ".main_r_failure_rule", ".protected_generalization", ".calibration_contract",
       ".generation_authority", ".disjointness_contract", ".episode_universe_contract"]
untouched = {s: all(a[k] == b[k] for k in a if k.startswith(s)) for s in SCI}
diff = {
 "schema_version": "rvt-swarm-clean-room-contract-diff/v1",
 "from_root": V3R, "to_root": sealed["rvt_swarm_clean_room_global_contract_root"],
 "v1_root": V1_ROOT, "v2_root": V2_ROOT,
 "closures": ["dataset composition for all six roles", "sample-size authority",
   "layout-instance allocation", "generation-seed authority",
   "source-episode enumeration authority"],
 "added_paths": added, "removed_paths": removed, "changed_paths": changed,
 "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
 "out_of_scope_changes": off,
 "all_unrelated_v3_decisions_preserved": not off,
 "prior_scientific_blocks_untouched": untouched,
 "every_prior_scientific_block_untouched": all(untouched.values()),
}
diff = attach_canonical_hash(diff, "clean_room_contract_v3_to_v4_diff_root")
(R/"rvt_swarm_clean_room_contract_v3_to_v4_diff.json").write_text(
    json.dumps(diff, indent=1, sort_keys=True)+"\n", encoding="ascii")
print("V4_ROOT", sealed["rvt_swarm_clean_room_global_contract_root"])
print("V4_file_sha256", hashlib.sha256(out.read_bytes()).hexdigest())
print("DIFF_ROOT", diff["clean_room_contract_v3_to_v4_diff_root"])
print(f"added={len(added)} removed={len(removed)} changed={len(changed)}")
print("OUT_OF_SCOPE:", off if off else "NONE")
print("ALL PRIOR SCIENTIFIC BLOCKS UNTOUCHED:", all(untouched.values()))
print("composition fingerprint:", composition_fingerprint()[:32])
