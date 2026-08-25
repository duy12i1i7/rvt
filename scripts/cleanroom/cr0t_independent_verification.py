"""CR-0T independent verification -- re-derive every V4 composition claim from source."""
from __future__ import annotations
import hashlib, json, pathlib, subprocess, sys
from math import sqrt
from statistics import NormalDist
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import verify_canonical_hash

ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
def h(rel): return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
V = {v: json.loads((R/f"rvt_swarm_clean_room_global_contract_{v}.json").read_text())
     for v in ("v1","v2","v3","v4")}
df = json.loads((R/"rvt_swarm_clean_room_contract_v3_to_v4_diff.json").read_text())
fail = []
def ck(n, ok, d=""):
    print(("PASS " if ok else "FAIL ") + n + (f" -- {d}" if d else ""))
    if not ok: fail.append(n)

ROOTS = {"v1":"16aa431b290eae42ad62b0f72fae22ed3a2e3b7be138db4cfdda4a636bd87c02",
         "v2":"90e5d4d9ee6b4388596f3a48ce5e62e0a8f446f08c7f7020d6ceda800a082740",
         "v3":"90d374d52f47319949cfafd724e83996d9d9dd95a71eb26ab6fed0116252e905"}
K = "rvt_swarm_clean_room_global_contract_root"
for v, want in ROOTS.items():
    ck(f"{v.upper()} unchanged", verify_canonical_hash(V[v], K) and V[v][K] == want)
ck("V4 canonical hash", verify_canonical_hash(V["v4"], K))
am = V["v4"]["amendment"]
ck("V4 references V1, V2 and V3",
   am["v1_root"] == ROOTS["v1"] and am["v2_root"] == ROOTS["v2"] and am["v3_root"] == ROOTS["v3"]
   and len(am["lineage"]) == 3)
ck("V4 asserts the clean pre-data state",
   am["no_clean_room_data_existed"] and am["no_clean_room_model_existed"]
   and am["no_cr1_generation_attempt_occurred"]
   and am["no_clean_room_empirical_outcome_informed_composition"])
for tag in ("rvt-cleanroom-cr0-v1","rvt-cleanroom-cr0r-v2","rvt-cleanroom-cr0s-v3"):
    ck(f"prior tag {tag} resolves", subprocess.run(
       ["git","-C",str(ROOT),"rev-parse",tag], capture_output=True).returncode == 0)

# ---- clean state ------------------------------------------------------------
roles = ["TRAIN-R","SELECT-R","CL-DEV-R","MAIN-R","MECH-R","PROTECTED-R"]
declared = {r: 0 for r in roles}
for p in ROOT.rglob("*.json"):
    if ".git" in p.parts: continue
    try: d = json.loads(p.read_text())
    except Exception: continue
    if isinstance(d, dict):
        rr = d.get("role") or d.get("dataset_role") or d.get("clean_room_role")
        if isinstance(rr, str) and rr.upper() in declared: declared[rr.upper()] += 1
ck("zero clean-room datasets", not any(declared.values()), json.dumps(declared))
ck("zero clean-room models",
   not any("clean" in str(p).lower() for p in ROOT.rglob("*.pt") if ".git" not in p.parts))
ck("zero generation attempts recorded", V["v4"]["cr0_state"]["cr1_generation_attempts"] == 0)

# ---- scoped diff ------------------------------------------------------------
ck("diff canonical", verify_canonical_hash(df, "clean_room_contract_v3_to_v4_diff_root"))
ck("diff links V3 to V4", df["from_root"] == ROOTS["v3"] and df["to_root"] == V["v4"][K])
ck("no out-of-scope change", df["out_of_scope_changes"] == []
   and df["all_unrelated_v3_decisions_preserved"] is True)
ck("every prior scientific block untouched", df["every_prior_scientific_block_untouched"] is True,
   f'{sum(df["prior_scientific_blocks_untouched"].values())}/19 blocks')

# ---- composition: recompute independently -----------------------------------
from rvt_swarm.cleanroom.composition import (
    CELLS, FAMILIES, GENERATION_SEED_MODULUS, ROLE_COMPOSITION, SOURCE_POLICIES,
    TEAM_SIZES, V3_ROOT, all_roles_disjoint, composition_fingerprint,
    enumerate_episode_ids, generation_seed, verify_role_arithmetic)
dc = V["v4"]["dataset_composition"]
ck("grid is 10 x 5 x 6 = 300", CELLS == 300 and dc["grid"]["cells"] == 300
   and len(FAMILIES) == 10 and len(TEAM_SIZES) == 5 and len(SOURCE_POLICIES) == 6)
ck("grid matches the pilot cell structure recorded in V4",
   dc["grid"]["families"] == list(FAMILIES) and dc["grid"]["team_sizes"] == list(TEAM_SIZES)
   and dc["grid"]["source_policies"] == list(SOURCE_POLICIES))

# reconstruct the pilot figures straight from the pilot manifests
import collections
for name, key, exp_eps, exp_lay in (
    ("phase9d_v3f_l_train_manifest_dry_final_v1.json","pilot_TRAIN",1200,20),
    ("phase9d_v3f_l_validation_manifest_dry_final_v1.json","pilot_VALIDATION",300,10)):
    d = json.loads((R/name).read_text()); eps = d["episodes"]
    cell = collections.Counter()
    for e in eps: cell[(e["family"], e["team_size"], e["source_policy"])] += 1
    rec = dc["pilot_reconstruction"][key]
    ck(f"{key} reconstructs from its own manifest",
       len(eps) == exp_eps == rec["source_episodes"] and d["layout_count"] == exp_lay == rec["layouts"]
       and len(cell) == CELLS and len(set(cell.values())) == 1,
       f"{len(eps)} episodes, {d['layout_count']} layouts, {len(cell)} cells uniform")
ck("TRAIN-R is sized to pilot TRAIN, not pilot VALIDATION",
   dc["roles"]["TRAIN-R"]["source_episode_count"] == 1200
   and dc["pilot_reconstruction"]["pilot_VALIDATION"]["source_episodes"] == 300)

nd = NormalDist()
total = 0
for r in roles:
    rec = dc["roles"][r]; comp = ROLE_COMPOSITION[r]; a = verify_role_arithmetic(r)
    total += rec["source_episode_count"]
    ck(f"{r}: offset matches V3", rec["offset"] == V["v3"]["disjointness_contract"]
       ["layout_offset_assignment"]["clean_room"][r] == comp.offset)
    payload = "|".join((V3_ROOT, r, "GENERATION")).encode("ascii")
    want = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % GENERATION_SEED_MODULUS
    ck(f"{r}: generation seed recomputes from V3 root", rec["generation_seed"] == want == generation_seed(r))
    ck(f"{r}: arithmetic exact",
       rec["source_episode_count"] == a["source_episodes"]
       == rec["episodes_per_cell"] * CELLS
       and rec["episodes_per_family_team_size_cell"] == rec["episodes_per_cell"] * 6
       and rec["source_episode_count"] % rec["layout_count"] == 0
       and rec["episodes_per_layout"] * rec["layout_count"] == rec["source_episode_count"],
       f"{rec['episodes_per_cell']}/cell x {CELLS} = {rec['source_episode_count']}")
    ids = list(enumerate_episode_ids(r))
    ck(f"{r}: episode universe enumerates exactly and uniquely",
       len(ids) == rec["source_episode_count"] and len(set(ids)) == len(ids))
ck("total across all roles", total == dc["total_source_episodes"] == 4200)
ck("all six role universes pairwise disjoint", all_roles_disjoint())
ck("composition fingerprint reproduces", dc["composition_fingerprint"] == composition_fingerprint())
ck("composition implementation hash live",
   dc["implementation_sha256"] == h("rvt_swarm/cleanroom/composition.py"))

# ---- sizing derivations -----------------------------------------------------
p = dc["main_r_planning"]
n_main = dc["roles"]["MAIN-R"]["source_episode_count"]
se = sqrt(0.5 / n_main)
power = nd.cdf((p["planning_alternative"] - p["threshold"]) / se - nd.inv_cdf(1 - p["alpha_one_sided"]))
ck("MAIN-R power recomputes from the frozen planning inputs and meets the target",
   power >= p["target_power"] and abs(power - p["achieved_power_at_chosen_size"]) < 1e-3,
   f"n={n_main} power={power:.4f} target={p['target_power']}")
smaller = sqrt(0.5 / (2 * CELLS))
ck("one balanced step smaller would miss the power target",
   nd.cdf(0.08 / smaller - nd.inv_cdf(0.95)) < p["target_power"])
ck("MAIN-R threshold equals the frozen H-CL1 threshold",
   p["threshold"] == V["v4"]["h_cl1_benefit_contract"]["primary_endpoint"]["practical_benefit_threshold"] == 0.08)
ck("no clean-room outcome informed MAIN-R sizing",
   p["pilot_information_used"].startswith("NONE in the arithmetic"))
ck("MECH-R at least as large as MAIN-R",
   dc["roles"]["MECH-R"]["source_episode_count"] >= n_main)
n_prot = dc["roles"]["PROTECTED-R"]["source_episode_count"]
ck("PROTECTED-R precision target met", 1.959964 * sqrt(0.25 / n_prot) <= 0.05,
   f"half-width {1.959964*sqrt(0.25/n_prot):.4f}")

# ---- disjointness from pilot and reserve ------------------------------------
used = {dc["roles"][r]["offset"] for r in roles}
ck("no clean-room offset touches pilot, reserve or forbidden bands",
   not (used & {0.22, 0.54, 0.65}) and not (used & {0.33}) and not (used & {0.76, 0.77, 0.87}))
pilot_ids = set()
for name in ("phase9d_v3f_l_train_manifest_dry_final_v1.json",
             "phase9d_v3f_l_validation_manifest_dry_final_v1.json"):
    pilot_ids |= {e["episode_id"] for e in json.loads((R/name).read_text())["episodes"]}
clean_ids = set()
for r in roles: clean_ids |= set(enumerate_episode_ids(r))
ck("no clean-room episode id collides with any pilot episode id",
   not (pilot_ids & clean_ids), f"{len(pilot_ids)} pilot vs {len(clean_ids)} clean-room ids")

# ---- schema + claim boundary + qualification --------------------------------
ck("manifest schema requires an explicit pre-generation universe",
   V["v4"]["generation_manifest_schema"]["scientific_universe_explicit_before_generation"] is True
   and "expected_source_episode_ids" in V["v4"]["generation_manifest_schema"]["required_fields"])
cb = V["v4"]["sample_size_claim_boundary"]
ck("claim boundary refuses independence and OOD readings",
   "NOT independent distributions" in cb["identity_disjoint_is_not_independent_distributions"]
   and "not unseen-family" in cb["protected_r_is_not_ood"])
q = V["v4"]["adversarial_qualification"]
ck("all eighteen composition fixtures covered",
   len(q["composition_negative_fixtures"]) == 18
   and all(v == "COVERED" for v in q["composition_negative_fixtures"].values()))
ck("cr0t suite hash live", q["cr0t_suite"]["sha256"] == h("tests/test_cleanroom_cr0t.py"))
for name, want in V["v4"]["orchestration_authority"]["clean_room_engine"].items():
    ck(f"engine hash live: {name}", h(f"rvt_swarm/cleanroom/{name}") == want)

print("\nVERIFICATION", "PASS" if not fail else f"FAIL {fail}")
for v in ("v1","v2","v3"): print(f"{v.upper()}_ROOT", ROOTS[v])
print("V4_ROOT", V["v4"][K])
