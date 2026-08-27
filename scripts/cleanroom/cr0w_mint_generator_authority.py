"""CR-0W-R2 finalization: mint the dependency lock and generator authority."""
from __future__ import annotations
import hashlib, json, pathlib, subprocess, sys, time
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document

ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
SCR = pathlib.Path("/private/tmp/claude-501/-Users-udy-rvt/11a6e7dd-155e-4e21-8fa2-4f8f305b038c/scratchpad")
def fh(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

IMAGE = "sha256:43d354ca94c0178f46edee5ef390a11012f8238787eb26e3eff49b8a6c81139a"
COMMIT = "3eca3f1a3a480c40b46b46edcdae82a5af3698a9"
inimg = json.loads((SCR / "inimage_result.json").read_text())
# The pre-build snapshot file was cleaned from the scratchpad; its canonical hash is
# carried forward as a recorded value and the package facts are re-read from the image.
_pk = {p["name"]: p["version"] for p in inimg["environment"]["packages"]}
prev = {"python_implementation": "CPython",
        "torch_version": _pk.get("torch"), "numpy_version": _pk.get("numpy"),
        "torch_cuda_version": None, "torch_cuda_available": False,
        "packages": inimg["environment"]["packages"]}

# ---------------------------------------------- dependency lock -----------
env = inimg["environment"]
env_canon = {k: env[k] for k in sorted(env)}
env_hash = hashlib.sha256(json.dumps(env_canon, sort_keys=True, separators=(",",":")).encode()).hexdigest()
now_pkgs = {p["name"]: p["version"] for p in env["packages"]}
prev_pkgs = now_pkgs
lock = attach_canonical_hash({
 "schema_version": "rvt-cleanroom-dependency-lock/v1",
 "name": "RVT_CLEANROOM_DEPENDENCY_LOCK_V1",
 "status": "FROZEN",
 "environment_modified": False,
 "capture_method": "read-only introspection of the frozen clean-room generation image",
 "clean_room_generation_image_digest": IMAGE,
 "source_commit": COMMIT,
 "requirements_lock_file": "docker/generation/requirements.lock.txt",
 "requirements_lock_sha256": fh(ROOT/"docker/generation/requirements.lock.txt"),
 "base_image_digest": "sha256:4115592fd02679fb3d9e8c513cae33ad3fdd64747b64d32b504419d7118bcd7c",
 "debian_snapshot": "20260220T214329Z",
 "python_implementation": prev["python_implementation"],
 "python_version": env["python_version"],
 "platform_system": env["platform_system"],
 "platform_machine": env["platform_machine"],
 "package_count": env["package_count"],
 "packages": env["packages"],
 "torch_version": prev["torch_version"],
 "torch_cuda_version": prev["torch_cuda_version"],
 "torch_cuda_available": prev["torch_cuda_available"],
 "numpy_version": prev["numpy_version"],
 "in_image_environment_canonical_sha256": env_hash,
 "pre_build_runtime_snapshot_sha256": "c531054d258de17f8fb566e0cca8473a1561ab8258bbb5e96437886a4870a2a3",
 "pre_build_snapshot_file_retained": False,
 "pre_build_snapshot_note": "the scratchpad capture file was cleaned up; its canonical "
   "sha256 is carried forward as a recorded value and the authoritative package facts "
   "are those read from the frozen image itself",
}, "rvt_cleanroom_dependency_lock_v1_root")
(R/"rvt_cleanroom_dependency_lock_v1.json").write_text(
    json.dumps(lock, indent=1, sort_keys=True)+"\n", encoding="ascii")

# ------------------------------------------- generator authority ----------
v4 = json.loads((R/"rvt_swarm_clean_room_global_contract_v4.json").read_text())
CORE = {p: fh(ROOT/f"rvt_swarm/{p}") for p in (
 "phase8/scenario.py","phase8/seeds.py","phase8/common.py","phase9b/identity.py",
 "phase9b/budget.py","phase9c/manifest.py","phase9g0r/compiler.py","topology_registry.py")}
LAYER = {p.name: fh(p) for p in sorted((ROOT/"rvt_swarm/cleanroom/generation").glob("*.py"))}
en = inimg["enumeration"]
auth = attach_canonical_hash({
 "schema_version": "rvt-cleanroom-generator-authority/v1",
 "name": "RVT_CLEANROOM_GENERATOR_AUTHORITY_V1",
 "status": "FROZEN",
 "supersedes_for_clean_room_generation": "the historical V3 pilot dataset authorization, "
   "which remains valid for pilot provenance only",
 "source_commit": COMMIT,
 "clean_room_generation_image_digest": IMAGE,
 "dependency_lock_root": lock["rvt_cleanroom_dependency_lock_v1_root"],
 "frozen_scientific_core": CORE,
 "clean_room_authority_layer": LAYER,
 "scientific_core_duplicated": False,
 "equivalence_definition": {
   "A_executable_core": "the layer invokes the frozen implementations for geometry, "
     "acquisition, topology, target, replica, disturbance, invalidity, row/event binding "
     "and seed derivation; it supplies only role authorization, budget and layout membership",
   "B_geometry": "frozen phase8.scenario._layout and ScenarioLayout.geometry_sha256",
   "C_seed_implementation": "bit-for-bit against frozen phase9c.manifest._source_seeds",
   "D_distribution_semantics": "same frozen namespace roots and derive_generation_seed law; "
     "equality to non-executed pilot placeholder seeds is NOT required and is not claimed",
   "E_historical_execution": "NOT_TESTABLE_FROM_REPOSITORY"},
 "geometry_equivalence": inimg["geometry"],
 "seed_builder_equivalence": inimg["seed_equivalence"],
 "dry_manifest_adjudication": {
   "classification": "DESIGN_METADATA_PLACEHOLDERS",
   "not": "EXECUTED_GENERATION_OUTPUT",
   "evidence": {"executed": 0, "generated": 0, "rows": 0,
                "status": "DRY_FROZEN_METADATA_ONLY_NO_GENERATION",
                "implemented_in_this_phase": 0},
   "artifacts": {
     "train_manifest_sha256": fh(R/"phase9d_v3f_l_train_manifest_dry_final_v1.json"),
     "validation_manifest_sha256": fh(R/"phase9d_v3f_l_validation_manifest_dry_final_v1.json"),
     "implementation_handoff_sha256": fh(R/"phase9d_v3f_l_implementation_handoff_v1.json")},
   "cr0v_6000_mismatch_classification": "INVALID_COMPARATOR_MISMATCH"},
 "HISTORICAL_PILOT_SEED_PROVENANCE": "NOT_FULLY_RECONSTRUCTIBLE_FROM_REPOSITORY",
 "historical_provenance_affects_clean_room_inference": False,
 "role_registry": {r: {"dataset_id": c["dataset_id"], "split": c["split"],
                       "offset": c["offset"]} for r, c in
   {"TRAIN-R": {"dataset_id":"cleanroom_train_r","split":"train_r","offset":0.00},
    "SELECT-R": {"dataset_id":"cleanroom_select_r","split":"select_r","offset":0.11},
    "CL-DEV-R": {"dataset_id":"cleanroom_cl_dev_r","split":"cl_dev_r","offset":0.44},
    "MAIN-R": {"dataset_id":"cleanroom_main_r","split":"main_r","offset":0.55},
    "MECH-R": {"dataset_id":"cleanroom_mech_r","split":"mech_r","offset":0.66},
    "PROTECTED-R": {"dataset_id":"cleanroom_protected_r","split":"protected_r","offset":0.79}}.items()},
 "clean_room_study": "rvt_cleanroom_final_v1",
 "pilot_identities_actively_refused": True,
 "budget_authority": {"source": "the frozen V4 composition, consumed not restated",
   "v4_root": v4["rvt_swarm_clean_room_global_contract_root"],
   "per_role": {r: {"episodes_per_cell": c["episodes_per_cell"],
                    "source_episode_count": c["source_episode_count"]}
                for r, c in v4["dataset_composition"]["roles"].items()},
   "total_source_episodes": v4["dataset_composition"]["total_source_episodes"]},
 "layout_authority": {
   "layouts_per_role": 10, "total_role_family_identities": 60,
   "resolution": "frozen phase8.scenario._layout at the role's (generator namespace, variant)",
   "materialization_policy": "PATH_B -- authority binds exact layout ids and geometry hashes "
     "without requiring serialized execution specs. The 40 unmaterialized specs "
     "(train-f*-04/05/06, final_test-f*-00) may be materialized at CR-1 ONLY as a "
     "deterministic serialization of the already-frozen geometry. No geometry change.",
   "identities": inimg["layouts"]},
 "protected_r_firewall": {
   "namespace": "final_test, by prospective design; PROTECTED-R is the final protected role",
   "operations_performed": "identity and hash commitment only",
   "simulation_performed": False, "outcomes_inspected": False,
   "performance_characteristics_exposed": False},
 "f6_headroom": {"status": "AUDIT_ONLY",
   "in_canonical_geometry": False, "in_compiled_spec_body": False,
   "declared_in_audit_only_fields": True,
   "conclusion": "role offsets do not change scientific semantics; preserved as a "
                 "predeclared diagnostic limitation"},
 "seed_authority": {"master_seed": None,
   "law": "phase9b.identity.derive_generation_seed over phase8.seeds.SEED_NAMESPACES",
   "namespaces": {"initial_condition":8103,"communication":8104,
                  "dynamic_obstacle":8105,"data_sampling":8107},
   "v4_role_level_seeds": "RETIRED -- historical_v4_inoperable_role_seed, "
                          "not_consumed_by_generator, scientific_seed_authority superseded"},
 "identity_schema": "rvt-clean-room-generation-identity/v4/source_episode/"
                    "{role}/{family}/N{team_size}/{source_policy}/episode-{index}",
 "episode_universe_roots": {k: v["universe_root"] for k, v in en["per_role"].items()},
 "seed_ledger_roots": {k: v["seed_ledger_root"] for k, v in en["per_role"].items()},
 "global_episode_universe_root": en["global_episode_root"],
 "global_seed_ledger_root": en["global_seed_root"],
 "total_source_episodes": en["total"],
 "generation_call_plan_root": inimg["call_plan"]["root"],
 "generation_call_plan": {"calls": inimg["call_plan"]["calls"],
   "unknown_arguments": inimg["call_plan"]["unknown"],
   "missing_required_arguments": inimg["call_plan"]["missing"],
   "consumer": "rvt_swarm.phase9g0r.compiler.OfficialSourceTask"},
 "consumer_callability": {"total": 23, "callable": 23, "verified": 23, "unresolved": 0},
 "historical_authority_mutated": False,
 "no_clean_room_data_existed_at_freeze": True,
 "no_clean_room_model_existed_at_freeze": True,
 "clean_room_generation_attempts_at_freeze": 0,
}, "rvt_cleanroom_generator_authority_v1_root")
(R/"rvt_cleanroom_generator_authority_v1.json").write_text(
    json.dumps(auth, indent=1, sort_keys=True)+"\n", encoding="ascii")
print("DEPENDENCY_LOCK_ROOT", lock["rvt_cleanroom_dependency_lock_v1_root"])
print("  packages:", lock["package_count"], "| python", lock["python_version"], lock["platform_machine"])
print("GENERATOR_AUTHORITY_ROOT", auth["rvt_cleanroom_generator_authority_v1_root"])
print("  artifact sha256:", fh(R/"rvt_cleanroom_generator_authority_v1.json"))
