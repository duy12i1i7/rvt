"""In-image finalization verification for CR-0W-R2."""
import json, subprocess, sys, platform
sys.path.insert(0, "/opt/rvt")
out = {}
out["image_source_commit"] = subprocess.run(
    ["git","-C","/opt/rvt","rev-parse","HEAD"], capture_output=True, text=True).stdout.strip()
out["commit_matches"] = out["image_source_commit"] == "3eca3f1a3a480c40b46b46edcdae82a5af3698a9"

from rvt_swarm.phase8 import scenario as S
from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9c.manifest import _source_seeds
from rvt_swarm.phase9b.identity import SourceEpisodeIdentity
from rvt_swarm.cleanroom.generation.ledger import all_roots, enumerate_role
from rvt_swarm.cleanroom.generation.callplan import validate_all, REQUIRED_FIELDS
from rvt_swarm.cleanroom.generation.seeds import source_episode_seeds, SOURCE_EPISODE_SEED_NAMESPACES
from rvt_swarm.cleanroom.generation.roles import ROLES
from rvt_swarm.cleanroom.generation.layouts import all_role_layouts, assert_layouts_disjoint_across_roles
import pathlib, json as _j

# --- geometry equivalence ---
R = pathlib.Path("/opt/rvt/results/rvt_fd24")
gmis = gtot = 0
for n in ("phase9d_v3f_l_train_manifest_dry_final_v1.json",
          "phase9d_v3f_l_validation_manifest_dry_final_v1.json"):
    seen = set()
    for e in _j.loads((R/n).read_text())["episodes"]:
        if e["layout_id"] in seen: continue
        seen.add(e["layout_id"]); gtot += 1
        L = S._layout(e["family"], e["generator_split_namespace"],
                      int(e["layout_id"].rsplit("-",1)[1]))
        if not (L.layout_id == e["layout_id"] and L.geometry_sha256() == e["layout_sha256"]):
            gmis += 1
smis = stot = 0
for split in ("train","validation"):
    for p in sorted((R/"layout_execution_specifications"/split).glob("*.json")):
        sl = _j.loads(p.read_text())["source_layout"]; stot += 1
        L = S._layout(sl["family_id"], sl["split"], int(sl["layout_id"].rsplit("-",1)[1]))
        if not (L.layout_id == sl["layout_id"] and L.geometry_sha256() == sl["geometry_sha256"]
                and L.generation_seed_commitment == sl["generation_seed_commitment"]): smis += 1
out["geometry"] = {"manifest_identities": gtot, "manifest_mismatches": gmis,
                   "compiled_specs": stot, "spec_mismatches": smis}

# --- seed-builder equivalence over all 4200 ---
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
out["seed_equivalence"] = {"identities": len(pairs), "streams": 4,
                           "comparisons": tot, "mismatches": mis,
                           "root": sha256_document(pairs)}

# --- enumeration + call plan ---
A = all_roots(); C = validate_all()
out["enumeration"] = {"total": A["total_source_episodes"],
                      "global_episode_root": A["global_episode_universe_root"],
                      "global_seed_root": A["global_seed_ledger_root"],
                      "per_role": {k: {"episodes": v["expected_source_episode_count"],
                                       "universe_root": v["episode_universe_root"],
                                       "seed_ledger_root": v["seed_ledger_root"],
                                       "distinct": v["distinct_seed_values"],
                                       "total_values": v["total_seed_values"]}
                                   for k, v in A["per_role"].items()}}
out["call_plan"] = {"calls": C["calls"], "unknown": C["unknown_arguments"],
                    "missing": C["missing_required_arguments"], "root": C["call_plan_root"]}

# --- layouts ---
L = all_role_layouts(); assert_layouts_disjoint_across_roles()
out["layouts"] = {r: [{"family": i.family_id, "layout_id": i.layout_id,
                       "layout_sha256": i.layout_sha256, "offset": i.offset,
                       "generator_split_namespace": i.generator_split_namespace,
                       "variant_index": i.variant_index} for i in items]
                  for r, items in L.items()}

# --- non-duplication ---
import ast
issues = []
for p in sorted(pathlib.Path("/opt/rvt/rvt_swarm/cleanroom/generation").glob("*.py")):
    t = ast.parse(p.read_text()); imps = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import): imps |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom): imps.add(n.module or "")
    if any(m == "hashlib" or m.startswith("random") for m in imps): issues.append(p.name)
    for n in ast.walk(t):
        if isinstance(n, ast.Attribute) and n.attr in ("sha256","md5","default_rng"):
            issues.append(f"{p.name}:{n.attr}")
out["non_duplication_issues"] = issues

# --- environment ---
from importlib.metadata import distributions
pk = sorted({(d.metadata["Name"] or "").lower(): d.version for d in distributions()}.items())
out["environment"] = {"python_version": platform.python_version(),
                      "platform_machine": platform.machine(),
                      "platform_system": platform.system(),
                      "package_count": len(pk),
                      "packages": [{"name": n, "version": v} for n, v in pk]}
print(json.dumps(out, sort_keys=True))
