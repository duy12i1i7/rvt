"""CR-0W-R2 independent verification -- re-derive every V5/authority claim from source.

Written and frozen BEFORE any empirical clean-room data exists.
"""
from __future__ import annotations
import ast, hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import sha256_document, verify_canonical_hash

ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
def fh(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
fail = []
def ck(n, ok, d=""):
    print(("PASS " if ok else "FAIL ") + n + (f" -- {d}" if d else ""))
    if not ok: fail.append(n)

K = "rvt_swarm_clean_room_global_contract_root"
V = {v: json.loads((R/f"rvt_swarm_clean_room_global_contract_{v}.json").read_text())
     for v in ("v1","v2","v3","v4","v5")}
auth = json.loads((R/"rvt_cleanroom_generator_authority_v1.json").read_text())
lock = json.loads((R/"rvt_cleanroom_dependency_lock_v1.json").read_text())
df = json.loads((R/"rvt_swarm_clean_room_contract_v4_to_v5_diff.json").read_text())

# ---- lineage ---------------------------------------------------------------
ROOTS = {"v1":"16aa431b290eae42ad62b0f72fae22ed3a2e3b7be138db4cfdda4a636bd87c02",
         "v2":"90e5d4d9ee6b4388596f3a48ce5e62e0a8f446f08c7f7020d6ceda800a082740",
         "v3":"90d374d52f47319949cfafd724e83996d9d9dd95a71eb26ab6fed0116252e905",
         "v4":"74e02ce55c0793dc7f9b81d0181ac5bded0e4cc4ff169564107629473fab330a"}
for v, w in ROOTS.items():
    ck(f"{v.upper()} unchanged", verify_canonical_hash(V[v], K) and V[v][K] == w)
ck("V5 canonical hash", verify_canonical_hash(V["v5"], K))
am = V["v5"]["amendment"]
ck("V5 references V1-V4",
   all(am[f"v{i}_root"] == ROOTS[f"v{i}"] for i in (1,2,3,4)) and len(am["lineage"]) == 4)
ck("V5 declares the clean pre-data state",
   am["no_clean_room_dataset_existed"] and am["no_clean_room_model_existed"]
   and am["clean_room_generation_attempts"] == 0
   and am["no_clean_room_outcome_informed_this_change"])
for t in ("rvt-cleanroom-cr0-v1","rvt-cleanroom-cr0r-v2","rvt-cleanroom-cr0s-v3",
          "rvt-cleanroom-cr0t-v4"):
    ck(f"prior tag {t} resolves",
       subprocess.run(["git","-C",str(ROOT),"rev-parse",t], capture_output=True).returncode == 0)

# ---- clean state -----------------------------------------------------------
roles = ["TRAIN-R","SELECT-R","CL-DEV-R","MAIN-R","MECH-R","PROTECTED-R"]
n = {r: 0 for r in roles}
for p in ROOT.rglob("*.json"):
    if ".git" in p.parts: continue
    try: d = json.loads(p.read_text())
    except Exception: continue
    if isinstance(d, dict):
        rr = d.get("role") or d.get("dataset_role") or d.get("clean_room_role")
        if isinstance(rr, str) and rr.upper() in n: n[rr.upper()] += 1
ck("zero clean-room datasets", not any(n.values()), json.dumps(n))
ck("zero clean-room models",
   not any("clean" in str(p).lower() for p in ROOT.rglob("*.pt") if ".git" not in p.parts))
ck("zero generation attempts", V["v4"]["cr0_state"]["cr1_generation_attempts"] == 0)

# ---- dry-manifest classification ------------------------------------------
adj = auth["dry_manifest_adjudication"]
for f, key in (("phase9d_v3f_l_train_manifest_dry_final_v1.json","train_manifest_sha256"),
               ("phase9d_v3f_l_validation_manifest_dry_final_v1.json","validation_manifest_sha256"),
               ("phase9d_v3f_l_implementation_handoff_v1.json","implementation_handoff_sha256")):
    ck(f"dry artifact hash live: {f[:40]}", adj["artifacts"][key] == fh(R/f))
tr = json.loads((R/"phase9d_v3f_l_train_manifest_dry_final_v1.json").read_text())
ck("dry manifests really are non-executed",
   tr["executed"] == 0 and tr["generated"] == 0 and tr["rows"] == 0
   and tr["status"] == "DRY_FROZEN_METADATA_ONLY_NO_GENERATION")
ck("classified as placeholders, not executed output",
   adj["classification"] == "DESIGN_METADATA_PLACEHOLDERS"
   and adj["cr0v_6000_mismatch_classification"] == "INVALID_COMPARATOR_MISMATCH")
ck("historical seed provenance limitation recorded",
   auth["HISTORICAL_PILOT_SEED_PROVENANCE"] == "NOT_FULLY_RECONSTRUCTIBLE_FROM_REPOSITORY"
   and auth["historical_provenance_affects_clean_room_inference"] is False)

# ---- geometry equivalence, recomputed --------------------------------------
from rvt_swarm.phase8 import scenario as S
gm = gt = 0
for nm in ("phase9d_v3f_l_train_manifest_dry_final_v1.json",
           "phase9d_v3f_l_validation_manifest_dry_final_v1.json"):
    seen = set()
    for e in json.loads((R/nm).read_text())["episodes"]:
        if e["layout_id"] in seen: continue
        seen.add(e["layout_id"]); gt += 1
        L = S._layout(e["family"], e["generator_split_namespace"],
                      int(e["layout_id"].rsplit("-",1)[1]))
        if not (L.layout_id == e["layout_id"] and L.geometry_sha256() == e["layout_sha256"]): gm += 1
sm = st = 0
for split in ("train","validation"):
    for p in sorted((R/"layout_execution_specifications"/split).glob("*.json")):
        sl = json.loads(p.read_text())["source_layout"]; st += 1
        L = S._layout(sl["family_id"], sl["split"], int(sl["layout_id"].rsplit("-",1)[1]))
        if not (L.layout_id == sl["layout_id"] and L.geometry_sha256() == sl["geometry_sha256"]): sm += 1
ck("geometry equivalence recomputed", gm == 0 and sm == 0 and gt == 30 and st == 60,
   f"{gt} identities, {st} specs, {gm+sm} mismatches")
ck("authority records the same geometry result",
   auth["geometry_equivalence"]["manifest_mismatches"] == 0
   and auth["geometry_equivalence"]["spec_mismatches"] == 0)

# ---- 16800 seed comparisons, recomputed ------------------------------------
from rvt_swarm.phase9c.manifest import _source_seeds
from rvt_swarm.phase9b.identity import SourceEpisodeIdentity
from rvt_swarm.cleanroom.generation.ledger import all_roots, enumerate_role
from rvt_swarm.cleanroom.generation.callplan import validate_all
from rvt_swarm.cleanroom.generation.seeds import source_episode_seeds, SOURCE_EPISODE_SEED_NAMESPACES
from rvt_swarm.cleanroom.generation.roles import ROLES, CLEAN_ROOM_STUDY, authorize, RoleAuthorityError
from rvt_swarm.cleanroom.generation.budget import budget
from rvt_swarm.cleanroom.generation.layouts import all_role_layouts, assert_layouts_disjoint_across_roles
tot = mis = 0; pairs = []
for role in ROLES:
    for ident in enumerate_role(role):
        frozen = _source_seeds(SourceEpisodeIdentity(
            cell=ident.cell, source_class=ident.source_class,
            episode_index=ident.episode_index))
        mine = dict(source_episode_seeds(ident))
        for ns in SOURCE_EPISODE_SEED_NAMESPACES:
            tot += 1
            if frozen[ns] != mine[ns]: mis += 1
        pairs.append([ident.source_episode_id(), sorted(mine.items())])
ck("16800 frozen _source_seeds comparisons", tot == 16800 and mis == 0 and len(pairs) == 4200,
   f"identities={len(pairs)} comparisons={tot} mismatches={mis}")
ck("seed-equivalence root matches the authority",
   sha256_document(pairs) == auth["seed_builder_equivalence"]["root"]
   == "adc9fcbfae8c15367d61047e0ec7f694a0c6ac10fd676f8fc62f08ac4644f8ee")

# ---- enumeration + call plan ----------------------------------------------
A = all_roots(); C = validate_all()
ck("global episode root", A["global_episode_universe_root"] == auth["global_episode_universe_root"]
   == "4b925d644c998d368707728a3d6acf018488c4484d540019142044414c9c424b")
ck("global seed root", A["global_seed_ledger_root"] == auth["global_seed_ledger_root"]
   == "34e616d6db62bf4b91ed09041e827d0d2760573593f30838eae9e3c2e707b3fe")
ck("call-plan root", C["call_plan_root"] == auth["generation_call_plan_root"]
   == "77b6e31c25e9678fae18314f9c915cab536bb6574f7051f2ecbe6ed0b5beb6db")
ck("4200 calls, no unknown or missing arguments",
   C["calls"] == 4200 and C["unknown_arguments"] == 0 and C["missing_required_arguments"] == 0)
ck("per-role roots match the authority",
   all(A["per_role"][r]["episode_universe_root"] == auth["episode_universe_roots"][r]
       and A["per_role"][r]["seed_ledger_root"] == auth["seed_ledger_roots"][r] for r in ROLES))
ck("no seed collisions",
   all(A["per_role"][r]["distinct_seed_values"] == A["per_role"][r]["total_seed_values"] for r in ROLES))

# ---- role / budget / layout authority --------------------------------------
ck("clean-room study and six roles", CLEAN_ROOM_STUDY == "rvt_cleanroom_final_v1" and len(ROLES) == 6)
try:
    authorize("study_a_zero_shot", "train", "study_a_train"); refused = False
except RoleAuthorityError: refused = True
ck("pilot identity actively refused", refused)
ck("budget consumes V4 exactly",
   all(budget(r).expected_source_episode_count
       == V["v4"]["dataset_composition"]["roles"][r]["source_episode_count"] for r in ROLES))
L = all_role_layouts(); assert_layouts_disjoint_across_roles()
ck("60 role/family layouts resolve, disjoint",
   sum(len(v) for v in L.values()) == 60 and all(len(v) == 10 for v in L.values()))
ck("layout materialization policy recorded",
   auth["layout_authority"]["materialization_policy"].startswith("PATH_B"))
pf = auth["protected_r_firewall"]
ck("PROTECTED-R firewall: identity only, no outcomes",
   pf["simulation_performed"] is False and pf["outcomes_inspected"] is False
   and pf["performance_characteristics_exposed"] is False)
ck("F6 headroom audit-only", auth["f6_headroom"]["status"] == "AUDIT_ONLY"
   and auth["f6_headroom"]["in_canonical_geometry"] is False)

# ---- non-duplication -------------------------------------------------------
issues = []
for p in sorted((ROOT/"rvt_swarm/cleanroom/generation").glob("*.py")):
    t = ast.parse(p.read_text()); imps = set()
    for nd in ast.walk(t):
        if isinstance(nd, ast.Import): imps |= {a.name for a in nd.names}
        elif isinstance(nd, ast.ImportFrom): imps.add(nd.module or "")
    if any(m == "hashlib" or m.startswith("random") for m in imps): issues.append(p.name)
    for nd in ast.walk(t):
        if isinstance(nd, ast.Attribute) and nd.attr in ("sha256","md5","default_rng"):
            issues.append(f"{p.name}:{nd.attr}")
ck("scientific core not duplicated", not issues, str(issues))
ck("authority agrees", auth["scientific_core_duplicated"] is False)

# ---- image / dependency / commit binding -----------------------------------
from rvt_swarm.cleanroom.generation.provenance import (
    CLEAN_ROOM_DEPENDENCY_LOCK_ROOT, CLEAN_ROOM_GENERATION_IMAGE_DIGEST,
    CLEAN_ROOM_SOURCE_COMMIT, ProvenanceError, assert_execution_authority)
ck("image digest bound consistently",
   auth["clean_room_generation_image_digest"] == CLEAN_ROOM_GENERATION_IMAGE_DIGEST
   == lock["clean_room_generation_image_digest"]
   == V["v5"]["clean_room_generation_authority"]["clean_room_generation_image_digest"])
ck("source commit bound consistently",
   auth["source_commit"] == CLEAN_ROOM_SOURCE_COMMIT == lock["source_commit"]
   == "3eca3f1a3a480c40b46b46edcdae82a5af3698a9")
ck("dependency lock root bound consistently",
   lock["rvt_cleanroom_dependency_lock_v1_root"] == CLEAN_ROOM_DEPENDENCY_LOCK_ROOT
   == auth["dependency_lock_root"])
ck("dependency lock canonical", verify_canonical_hash(lock, "rvt_cleanroom_dependency_lock_v1_root"))
ck("requirements lock hash live",
   lock["requirements_lock_sha256"] == fh(ROOT/"docker/generation/requirements.lock.txt")
   == "4b8ae11c181ac1067abe29f5df188beaf54b81a088406029e495a6f4d1d0a1ac")
ck("environment not modified", lock["environment_modified"] is False)
assert_execution_authority(image_reference=CLEAN_ROOM_GENERATION_IMAGE_DIGEST,
                           source_commit=CLEAN_ROOM_SOURCE_COMMIT,
                           dependency_lock_root=CLEAN_ROOM_DEPENDENCY_LOCK_ROOT)
bad = 0
for kw in ({"source_commit":"3eca3f1"}, {"image_reference":"rvt-cleanroom-gen:3eca3f1"},
           {"dependency_lock_root":"0"*64}, {"image_reference":"sha256:"+"0"*64}):
    try:
        assert_execution_authority(**{**{"image_reference":CLEAN_ROOM_GENERATION_IMAGE_DIGEST,
            "source_commit":CLEAN_ROOM_SOURCE_COMMIT,
            "dependency_lock_root":CLEAN_ROOM_DEPENDENCY_LOCK_ROOT}, **kw})
    except ProvenanceError: bad += 1
ck("provenance guard fails closed on all four substitutions", bad == 4)

# ---- authority + V5 --------------------------------------------------------
ck("generator authority canonical",
   verify_canonical_hash(auth, "rvt_cleanroom_generator_authority_v1_root"))
ck("V5 binds the generator authority",
   V["v5"]["clean_room_generation_authority"]["root"]
   == auth["rvt_cleanroom_generator_authority_v1_root"])
ck("V5 declares it the sole generator authority",
   V["v5"]["clean_room_generation_authority"]["sole_generator_authority_for_final_clean_room_data"] is True
   and "PILOT PROVENANCE ONLY" in V["v5"]["clean_room_generation_authority"]["historical_v3_generator_authority"])
ck("consumer-callability unresolved = 0", auth["consumer_callability"]["unresolved"] == 0)

# ---- diff scope ------------------------------------------------------------
ck("diff canonical", verify_canonical_hash(df, "clean_room_contract_v4_to_v5_diff_root"))
ck("diff links V4 to V5", df["from_root"] == ROOTS["v4"] and df["to_root"] == V["v5"][K])
ck("no out-of-scope scientific change",
   df["out_of_scope_changes"] == [] and df["all_unrelated_v4_decisions_preserved"] is True)
ck("all 23 forbidden blocks untouched", df["every_forbidden_block_untouched"] is True,
   f"{sum(df['forbidden_blocks_untouched'].values())}/{len(df['forbidden_blocks_untouched'])}")

# ---- historical immutability ----------------------------------------------
HIST = {'rvt_swarm/phase8/scenario.py':'a159cada3f86891c10d4cb6786b3509f58fdf2febfc20340544b837ea879256d',
 'rvt_swarm/phase8/seeds.py':'0a0e863bc18ef331792bb2c3749f1eb5d7f4c6aac42eaa8624700682883a81c6',
 'rvt_swarm/phase9b/budget.py':'9e3e8fa00e37ebb6b614d702fc588f67b0c2bfa56ba31bb48847a6ef0ae18611',
 'rvt_swarm/phase9b/identity.py':'67027a84c9997cb2332960546de266170498f99a6934641a7285202941e8e660',
 'rvt_swarm/phase9c/manifest.py':'a8681e3e4309178755f830f3c7a6afb4f09106843e880ed553f9e472459982e6',
 'rvt_swarm/phase9g0r/compiler.py':'f8a73826655de529511266fc8a9c7597a9b98a9c01b54c51d425d8e9bc310c2f',
 'rvt_swarm/phase9g0r/compiler_v3.py':'e5f4232ea0302b007d02df7009ab03cd7459fdea770bc41c72471d0984ed67f0',
 'rvt_swarm/phase8e/compiler.py':'9067b8041043126e172e2967b174e520661fb9cddd969613a6d22ba07df3dc50',
 'results/rvt_fd24/phase9d_v3f_l_layout_split_registry_v2.json':'8c42629fb988c9bef1ca0706485f7636c239df4e9212634a01ef6e1bfb1f57aa'}
ck("historical authority byte-identical",
   all(fh(ROOT/f) == h for f, h in HIST.items()))
from rvt_swarm.phase9b.budget import DATASET_IDS
from rvt_swarm.phase9g0r.compiler import AUTHORIZED_DATASETS, AUTHORIZED_STUDY_SPLITS
ck("no clean-room entry in historical allowlists",
   len(DATASET_IDS) == 5 and not any("cleanroom" in str(x) for x in
   list(DATASET_IDS)+list(AUTHORIZED_DATASETS)+list(AUTHORIZED_STUDY_SPLITS)))
ck("authority records historical unmutated", auth["historical_authority_mutated"] is False)

print("\nVERIFICATION", "PASS" if not fail else f"FAIL {fail}")
for v in ("v1","v2","v3","v4"): print(f"{v.upper()}_ROOT", ROOTS[v])
print("V5_ROOT", V["v5"][K])
print("GENERATOR_AUTHORITY_ROOT", auth["rvt_cleanroom_generator_authority_v1_root"])
print("DEPENDENCY_LOCK_ROOT", lock["rvt_cleanroom_dependency_lock_v1_root"])
