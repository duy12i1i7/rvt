"""CR-1 driver qualification: every listed substitution must fail closed."""
from __future__ import annotations

import copy, json, pathlib, sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts/cleanroom"))
import cr1_generate_train_r as D  # noqa: E402

ROOT = pathlib.Path("/Users/udy/rvt")
R = ROOT / "results/rvt_fd24"
MAN = json.loads((R/"cleanroom_train_r_pregeneration_manifest_v1.json").read_text())


def _with_image(monkeypatch):
    monkeypatch.setenv(D.EXPECTED_IMAGE_ENV, MAN["execution_image_digest"])


def test_authority_chain_loads_under_the_frozen_roots(monkeypatch):
    _with_image(monkeypatch)
    man, v5, auth = D.load_authority(ROOT)
    assert man["train_r_pregeneration_manifest_root"] == D.MANIFEST_ROOT
    assert v5["rvt_swarm_clean_room_global_contract_root"] == D.V5_ROOT
    assert auth["rvt_cleanroom_generator_authority_v1_root"] == D.AUTHORITY_ROOT


def test_manifest_binds_the_full_frozen_composition():
    assert MAN["role"] == "TRAIN-R" and MAN["dataset_id"] == "cleanroom_train_r"
    assert MAN["study"] == "rvt_cleanroom_final_v1" and MAN["split"] == "train_r"
    assert MAN["offset"] == 0.00
    assert len(MAN["families"]) == 10 and MAN["team_sizes"] == [5, 6, 8, 12, 16]
    assert len(MAN["source_policies"]) == 6
    assert MAN["episodes_per_cell"] == 4 and MAN["cells"] == 300
    assert MAN["expected_source_episode_count"] == 1200
    assert len(MAN["expected_source_episode_ids"]) == 1200
    assert MAN["k_max_selected_source_events_per_episode"] == 5
    assert MAN["layout_count"] == 10
    assert MAN["master_seed"] is None


@pytest.mark.parametrize("attr,bad", [
    ("MANIFEST_ROOT", "0"*64), ("V5_ROOT", "0"*64), ("AUTHORITY_ROOT", "0"*64),
])
def test_fixture_wrong_root_fails_closed(monkeypatch, attr, bad):
    _with_image(monkeypatch)
    monkeypatch.setattr(D, attr, bad)
    with pytest.raises(D.DriverError):
        D.load_authority(ROOT)


def test_fixture_stale_first_mint_v5_would_fail():
    """The superseded first-mint V5 root must not be accepted."""
    assert D.V5_ROOT != "aef04dd156a3e0910e77c50590217e62a02df948488113fbc346674ed8cb13f7"


def test_fixture_image_and_commit_substitutions_fail_closed():
    from rvt_swarm.cleanroom.generation.provenance import ProvenanceError, assert_execution_authority
    ok = dict(image_reference=MAN["execution_image_digest"],
              source_commit=MAN["image_source_commit"],
              dependency_lock_root=MAN["dependency_lock_v1_root"])
    assert_execution_authority(**ok)
    for field, bad in (("source_commit", "3eca3f1"),               # abbreviated
                       ("source_commit", "0"*40),                  # wrong full
                       ("image_reference", "rvt-cleanroom-gen:3eca3f1"),  # mutable tag
                       ("image_reference", "sha256:"+"0"*64),      # wrong digest
                       ("image_reference",                          # historical pilot image
                        "sha256:0b2d9a686d17ae9a67fbf8745535e56df9da88d82560b9378254947904782137"),
                       ("dependency_lock_root", "0"*64)):
        with pytest.raises(ProvenanceError):
            assert_execution_authority(**{**ok, field: bad})


@pytest.mark.parametrize("field,bad", [
    ("family", "F99"), ("team_size", 24), ("source_policy", "S9_UNKNOWN"),
    ("episode_index", 4), ("layout_id", "train-f1-02"),
])
def test_fixture_out_of_manifest_record_fails_closed(field, bad):
    rec = copy.deepcopy(MAN["expected_episode_records"][0]); rec[field] = bad
    with pytest.raises(D.DriverError):
        D.source_task(ROOT, rec, MAN)


def test_fixture_wrong_layout_hash_fails_closed():
    rec = copy.deepcopy(MAN["expected_episode_records"][0])
    rec["layout_sha256"] = "0"*64
    with pytest.raises(D.DriverError):
        D.source_task(ROOT, rec, MAN)


def test_fixture_manifest_mutation_after_hashing_fails_closed(tmp_path):
    """Any post-hash edit breaks the canonical hash and is refused."""
    from rvt_swarm.phase8.common import verify_canonical_hash
    m = copy.deepcopy(MAN)
    assert verify_canonical_hash(m, "train_r_pregeneration_manifest_root")
    m["expected_source_episode_count"] = 1201
    assert not verify_canonical_hash(m, "train_r_pregeneration_manifest_root")
    m2 = copy.deepcopy(MAN); m2["episodes_per_cell"] = 5
    assert not verify_canonical_hash(m2, "train_r_pregeneration_manifest_root")
    m3 = copy.deepcopy(MAN); m3["k_max_selected_source_events_per_episode"] = 6
    assert not verify_canonical_hash(m3, "train_r_pregeneration_manifest_root")


def test_fixture_manifest_record_count_mismatch_fails_closed(monkeypatch, tmp_path):
    m = copy.deepcopy(MAN); m["expected_episode_records"] = m["expected_episode_records"][:5]
    monkeypatch.setattr(D, "load_authority", lambda root: (m, None, None))
    with pytest.raises(D.DriverError):
        D.generate(ROOT, tmp_path)


def test_frozen_scientific_authority_bound_in_manifest():
    for key in ("target_semantics_sha256", "replica_law_sha256",
                "invalidity_semantics_sha256", "row_event_binding_sha256",
                "source_acquisition_protocol_sha256", "generator_sha256",
                "layout_execution_spec_registry_sha256", "layout_split_registry_sha256"):
        assert len(MAN[key]) == 64, key
    assert MAN["candidate_topologies"] == {"COMPACT": 5, "LINE": 2}
    assert MAN["replicas_per_candidate_by_family"]["F8"] == 3
    assert MAN["replicas_per_candidate_by_family"]["F9"] == 3
    assert MAN["replicas_per_candidate_by_family"]["F1"] == 1


def test_manifest_universe_disjoint_from_pilot_and_future_roles():
    from rvt_swarm.cleanroom.generation.ledger import enumerate_role
    from rvt_swarm.cleanroom.generation.roles import ROLES
    ids = set(MAN["expected_source_episode_ids"])
    pilot = set()
    for nm in ("phase9d_v3f_l_train_manifest_dry_final_v1.json",
               "phase9d_v3f_l_validation_manifest_dry_final_v1.json"):
        pilot |= {e["episode_id"] for e in json.loads((R/nm).read_text())["episodes"]}
    assert not (ids & pilot)
    for r in ROLES:
        if r == "TRAIN-R":
            continue
        assert not (ids & {i.source_episode_id() for i in enumerate_role(r)})


def test_driver_carries_no_alternative_scientific_constants():
    """Counts, families, N and policies must come from the manifest, not the driver."""
    src = pathlib.Path("scripts/cleanroom/cr1_generate_train_r.py").read_text()
    for banned in ("1200", "episodes_per_cell = 4", "F1\", \"F2", "[5, 6, 8, 12, 16]",
                   "S0_SCRIPTED_DIAGNOSTIC"):
        assert banned not in src, banned


def test_fixture_missing_injected_image_fails_closed(monkeypatch):
    """Generation must be launched by the orchestrator, which pins the digest."""
    monkeypatch.delenv(D.EXPECTED_IMAGE_ENV, raising=False)
    with pytest.raises(D.DriverError):
        D.load_authority(ROOT)


@pytest.mark.parametrize("bad", [
    "sha256:" + "0"*64,                                    # wrong digest
    "rvt-cleanroom-gen:3eca3f1",                           # mutable tag
    "sha256:0b2d9a686d17ae9a67fbf8745535e56df9da88d82560b9378254947904782137",  # pilot image
])
def test_fixture_wrong_injected_image_fails_closed(monkeypatch, bad):
    monkeypatch.setenv(D.EXPECTED_IMAGE_ENV, bad)
    with pytest.raises(D.DriverError):
        D.load_authority(ROOT)
