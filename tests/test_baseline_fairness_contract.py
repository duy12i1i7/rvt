from rvt_swarm.phase8.contracts import baseline_definitions


def test_exact_twelve_baselines_and_references_are_frozen():
    baselines = baseline_definitions()
    assert len(baselines) == 12
    assert len({item.baseline_id for item in baselines}) == 12
    assert baselines[0].baseline_id == "always_COMPACT"
    assert baselines[1].baseline_id == "always_LINE"
    assert baselines[2].baseline_id == "always_KEEP_fixed_reference"


def test_keep_is_fixed_reference_and_never_an_online_selector():
    keep = baseline_definitions()[2]
    assert keep.category == "fixed_reference"
    assert keep.communication == "none"
    assert "KEEP" not in " ".join(
        item.baseline_id
        for item in baseline_definitions()
        if "selector" in item.category
    )


def test_comparable_learned_baselines_receive_matched_budget_and_scenarios():
    learned = tuple(
        item for item in baseline_definitions()
        if item.category in ("learned_selector", "full_method", "optional_full_method")
    )
    assert {item.training_budget for item in learned} == {"same_max_steps_and_seeds"}
    assert {item.checkpoint_opportunities for item in learned} == {"same_validation_frequency"}
    assert {item.scenario_access for item in learned} == {"identical_paired_split_and_episode_seeds"}


def test_diagnostic_references_are_explicitly_non_deployable():
    diagnostics = tuple(item for item in baseline_definitions() if item.category == "diagnostic")
    assert len(diagnostics) == 3
    assert all(not item.deployable for item in diagnostics)
