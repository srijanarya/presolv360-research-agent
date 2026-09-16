"""E4 — Cross-source reasoning (the Claim Graph), the highest-risk core.

Two layers are tested here with NO live LLM:
  * `classify_cluster` — the pure, deterministic consensus/contested/outlier decider.
  * `build_claim_graph` / `derive_gaps` — orchestration over an injected fake reasoner,
    including the adversarial dual-perspective cross-check that flips a stance when a
    contradiction the naive clustering missed is surfaced.
"""

from __future__ import annotations

from research_agent.models import Claim, ClaimCluster, ClaimMember, SourceClaims
from research_agent.reason import build_claim_graph, classify_cluster, derive_gaps


def _m(source_id: str, stance: str = "supports") -> ClaimMember:
    return ClaimMember(source_id=source_id, stance=stance, claim_text="c", supporting_quote="q")


# --- E4.S2 — classify_cluster pure logic (the deterministic core) ---

def test_two_sources_supporting_is_consensus():
    assert classify_cluster([_m("s1"), _m("s2")]) == "consensus"


def test_support_plus_contradict_is_contested():
    assert classify_cluster([_m("s1", "supports"), _m("s2", "contradicts")]) == "contested"


def test_single_member_is_outlier():
    assert classify_cluster([_m("s1")]) == "outlier"


def test_two_distinct_sources_same_stance_not_outlier():
    assert classify_cluster([_m("s1"), _m("s2")]) != "outlier"


def test_same_source_twice_does_not_make_consensus():
    assert classify_cluster([_m("s1"), _m("s1")]) == "outlier"


def test_three_sources_one_dissent_is_contested():
    assert classify_cluster([_m("s1"), _m("s2"), _m("s3", "contradicts")]) == "contested"


def test_single_source_self_contradiction_is_not_contested():
    # One article citing two conflicting studies is intra-source nuance, NOT a cross-source
    # disagreement — it must not be labelled contested (the headline feature's correctness).
    assert classify_cluster([_m("s1", "supports"), _m("s1", "contradicts")]) == "outlier"


# --- E4.S3 — gap derivation (pure) ---

def test_single_source_subtopic_flagged_as_gap():
    clusters = [
        ClaimCluster(id="c1", statement="Only s1 asserts this", classification="outlier", members=[_m("s1")])
    ]
    gaps = derive_gaps(clusters)
    assert len(gaps) >= 1
    assert "one source" in (gaps[0].description + gaps[0].rationale).lower()


def test_no_gaps_yields_empty_valid_list():
    clusters = [
        ClaimCluster(
            id="c1", statement="Both agree", classification="consensus",
            members=[_m("s1"), _m("s2")],
        )
    ]
    assert derive_gaps(clusters) == []


# --- E4.S1 — build_claim_graph produces a valid graph ---

def _claim_sets() -> list[SourceClaims]:
    return [
        SourceClaims(source_id="s1", claims=[Claim(text="a", supporting_quote="qa")]),
        SourceClaims(source_id="s2", claims=[Claim(text="b", supporting_quote="qb")]),
    ]


async def test_reason_output_validates_and_has_members():
    async def fake(system: str, prompt: str, model: str):
        return {
            "clusters": [
                {
                    "statement": "AI reshapes jobs",
                    "members": [
                        {"source_id": "s1", "stance": "supports", "claim_text": "a", "supporting_quote": "qa", "confidence": "high"},
                        {"source_id": "s2", "stance": "supports", "claim_text": "b", "supporting_quote": "qb", "confidence": "medium"},
                    ],
                }
            ],
            "gaps": [],
        }

    clusters, gaps = await build_claim_graph("AI jobs", _claim_sets(), call_model=fake, adversarial=False)
    assert len(clusters) == 1
    assert all(len(c.members) >= 1 for c in clusters)
    assert clusters[0].classification == "consensus"  # 2 distinct supporting sources


# --- E4.S5 — adversarial dual-perspective cross-check (the differentiator) ---

def _adv_fake(initial_stance_s2: str, adv_stance_s2: str, n_clusters: int = 1):
    """Build a fake reasoner: clustering returns s2 with `initial_stance_s2`, the
    adversarial recheck returns s2 with `adv_stance_s2`."""
    counters = {"cluster": 0, "adv": 0}

    async def fake(system: str, prompt: str, model: str):
        if "stress-test" in system:  # adversarial cross-check call
            counters["adv"] += 1
            return {
                "for": "case for",
                "against": "case against",
                "members": [
                    {"source_id": "s1", "stance": "supports", "claim_text": "a", "supporting_quote": "qa", "confidence": "high"},
                    {"source_id": "s2", "stance": adv_stance_s2, "claim_text": "b", "supporting_quote": "qb", "confidence": "medium"},
                ],
            }
        counters["cluster"] += 1
        return {
            "clusters": [
                {
                    "statement": f"cluster {i}",
                    "members": [
                        {"source_id": "s1", "stance": "supports", "claim_text": "a", "supporting_quote": "qa", "confidence": "high"},
                        {"source_id": "s2", "stance": initial_stance_s2, "claim_text": "b", "supporting_quote": "qb", "confidence": "medium"},
                    ],
                }
                for i in range(n_clusters)
            ],
            "gaps": [],
        }

    return fake, counters


async def test_contested_emerges_when_sources_conflict():
    # Naive clustering says both support (would be consensus); the adversarial pass
    # reveals s2 actually contradicts -> the cluster is correctly labeled contested.
    fake, _ = _adv_fake(initial_stance_s2="supports", adv_stance_s2="contradicts")
    clusters, _ = await build_claim_graph("t", _claim_sets(), call_model=fake, adversarial=True)
    assert clusters[0].classification == "contested"


async def test_cross_check_runs_once_per_cluster():
    fake, counters = _adv_fake("supports", "supports", n_clusters=3)
    await build_claim_graph("t", _claim_sets(), call_model=fake, adversarial=True)
    assert counters["cluster"] == 1
    assert counters["adv"] == 3


async def test_adversarial_flag_off_falls_back_to_single_pass():
    fake, counters = _adv_fake("supports", "contradicts")  # adv would flip, but it's off
    clusters, _ = await build_claim_graph("t", _claim_sets(), call_model=fake, adversarial=False)
    assert counters["adv"] == 0
    assert clusters[0].classification == "consensus"  # naive pass: both support


async def test_single_source_cluster_skips_adversarial():
    # A 1-source cluster is always outlier regardless of stance → recheck is a no-op, skip it.
    counter = {"adv": 0}

    async def fake(system: str, prompt: str, model: str):
        if "stress-test" in system:
            counter["adv"] += 1
            return {"members": []}
        return {
            "clusters": [
                {
                    "statement": "only s1 asserts this",
                    "members": [{"source_id": "s1", "stance": "supports", "claim_text": "a", "supporting_quote": "qa", "confidence": "high"}],
                }
            ],
            "gaps": [],
        }

    clusters, _ = await build_claim_graph("t", _claim_sets(), call_model=fake, adversarial=True)
    assert counter["adv"] == 0
    assert clusters[0].classification == "outlier"


# --- P2 — grounding: reasoning members must match extracted claims -------------
# Every test injects a fake model. The catalogue below is the extraction output
# that grounds (or fails to ground) each proposed member.

from research_agent.reason import build_claim_catalogue, _validate_member  # noqa: E402


def _grounded_sets() -> list[SourceClaims]:
    return [
        SourceClaims(source_id="s1", claims=[Claim(text="Adoption is rising", supporting_quote="adoption rose sharply")]),
        SourceClaims(source_id="s2", claims=[Claim(text="Hiring slowed", supporting_quote="hiring slowed in Q2")]),
    ]


def _member(source_id="s1", claim_text="Adoption is rising", quote="adoption rose sharply",
            stance="supports", confidence="high") -> dict:
    return {"source_id": source_id, "stance": stance, "claim_text": claim_text,
            "supporting_quote": quote, "confidence": confidence}


def _responder(clusters, adv_members=None, counters=None):
    """Fake model: first call returns `clusters`, adversarial calls return `adv_members`."""
    async def fake(system: str, prompt: str, model: str):
        if "stress-test" in system:
            if counters is not None:
                counters["adv"] += 1
                counters.setdefault("adv_prompts", []).append(prompt)
            return {"for": "f", "against": "a", "members": adv_members or []}
        if counters is not None:
            counters["cluster"] += 1
        return {"clusters": clusters, "gaps": []}
    return fake


async def _graph(clusters, *, sets=None, adversarial=False, adv_members=None, counters=None):
    return await build_claim_graph(
        "topic", sets if sets is not None else _grounded_sets(),
        call_model=_responder(clusters, adv_members, counters), adversarial=adversarial,
    )


# catalogue

def test_catalogue_unions_repeated_source_ids():
    sets = [
        SourceClaims(source_id="s1", claims=[Claim(text="a", supporting_quote="qa")]),
        SourceClaims(source_id="s1", claims=[Claim(text="b", supporting_quote="qb")]),
    ]
    catalogue = build_claim_catalogue(sets)
    assert catalogue["s1"] == {("a", "qa"), ("b", "qb")}


def test_catalogue_normalizes_whitespace_and_case_only():
    catalogue = build_claim_catalogue(
        [SourceClaims(source_id="s1", claims=[Claim(text="  Mixed   CASE ", supporting_quote="A  Quote")])]
    )
    assert catalogue["s1"] == {("mixed case", "a quote")}


# the four measured defects

async def test_unknown_source_is_rejected():
    clusters, _ = await _graph([{"statement": "x", "members": [_member(), _member(source_id="s9")]}])
    assert [m.source_id for m in clusters[0].members] == ["s1"]


async def test_quote_belonging_to_another_source_is_rejected():
    wrong = _member(source_id="s2", claim_text="Hiring slowed", quote="adoption rose sharply")
    clusters, _ = await _graph([{"statement": "x", "members": [_member(), wrong]}])
    assert [m.source_id for m in clusters[0].members] == ["s1"]


async def test_fabricated_quote_is_rejected():
    clusters, _ = await _graph([{"statement": "x", "members": [_member(), _member(quote="never said this")]}])
    assert len(clusters[0].members) == 1


async def test_opposite_claim_text_on_a_genuine_quote_is_rejected():
    # The measured case that a quote-only check would wave through.
    flipped = _member(claim_text="Adoption is falling")
    clusters, _ = await _graph([{"statement": "x", "members": [_member(), flipped]}])
    assert [m.claim_text for m in clusters[0].members] == ["Adoption is rising"]


# normalization boundaries

async def test_whitespace_and_case_variant_is_retained_unchanged():
    variant = _member(claim_text="adoption   IS rising", quote="Adoption  Rose   Sharply")
    clusters, _ = await _graph([{"statement": "x", "members": [variant]}])
    member = clusters[0].members[0]
    assert member.claim_text == "adoption   IS rising"  # original formatting preserved
    assert member.supporting_quote == "Adoption  Rose   Sharply"


async def test_shortened_substring_quote_is_rejected():
    clusters, _ = await _graph([{"statement": "x", "members": [_member(), _member(quote="adoption rose")]}])
    assert len(clusters[0].members) == 1


async def test_punctuation_transformed_quote_is_rejected():
    clusters, _ = await _graph([{"statement": "x", "members": [_member(), _member(quote="adoption rose sharply!")]}])
    assert len(clusters[0].members) == 1


# field and stance validation

async def test_invalid_stance_is_rejected_not_coerced():
    clusters, _ = await _graph([{"statement": "x", "members": [_member(), _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2", stance="maybe")]}])
    assert [m.source_id for m in clusters[0].members] == ["s1"]


def test_scalar_and_empty_fields_are_rejected_with_reason_codes():
    catalogue = build_claim_catalogue(_grounded_sets())
    cases = {
        "malformed_member": "not a dict",
        "missing_source_id": {**_member(), "source_id": ""},
        "missing_claim_text": {**_member(), "claim_text": None},
        "missing_quote": {**_member(), "supporting_quote": 42},
        "invalid_stance": {**_member(), "stance": "unsure"},
        "unknown_source": {**_member(), "source_id": "s404"},
        "ungrounded_pair": {**_member(), "supporting_quote": "invented"},
    }
    for expected, item in cases.items():
        member, reason = _validate_member(item, catalogue)
        assert member is None and reason == expected, (expected, reason)


def test_unknown_confidence_still_falls_back_to_medium():
    catalogue = build_claim_catalogue(_grounded_sets())
    member, reason = _validate_member({**_member(), "confidence": "certain"}, catalogue)
    assert reason == "" and member.confidence == "medium"


# partial results and malformed shapes

async def test_partial_valid_output_is_retained():
    good = {"statement": "keep", "members": [_member()]}
    bad = {"statement": "drop", "members": [_member(quote="invented")]}
    clusters, _ = await _graph([good, "not a cluster", bad])
    assert [c.statement for c in clusters] == ["keep"]


async def test_malformed_member_collection_is_skipped_not_fatal():
    clusters, _ = await _graph([{"statement": "keep", "members": [_member()]}, {"statement": "drop", "members": "nope"}])
    assert [c.statement for c in clusters] == ["keep"]


async def test_null_non_list_and_missing_clusters_raise_descriptive_value_error():
    import pytest
    cases = {  # criterion 11: the message must say what was wrong, not just fail
        '{"clusters": null}': ({"clusters": None}, "must be a list"),
        '{"clusters": "nope"}': ({"clusters": "nope"}, "must be a list"),
        "missing key": ({"gaps": []}, "missing the 'clusters' key"),
        "not an object": (["not", "an", "object"], "not a JSON object"),
    }
    for label, (response, expected) in cases.items():
        async def fake(system, prompt, model, _r=response):
            return _r
        with pytest.raises(ValueError, match=expected):
            await build_claim_graph("t", _grounded_sets(), call_model=fake, adversarial=False)


async def test_all_members_rejected_raises_value_error():
    import pytest
    with pytest.raises(ValueError, match="no member was grounded"):
        await _graph([{"statement": "x", "members": [_member(quote="invented")]}])


async def test_explicit_empty_clusters_is_a_legitimate_result():
    clusters, gaps = await _graph([])
    assert clusters == [] and gaps == []


# duplicates, classification and gaps derive from survivors

async def test_duplicate_valid_members_are_kept_but_do_not_make_consensus():
    clusters, _ = await _graph([{"statement": "x", "members": [_member(), _member()]}])
    assert len(clusters[0].members) == 2
    assert clusters[0].classification == "outlier"


async def test_classification_and_gaps_derive_from_survivors():
    # Mixed cluster: s1 grounded, s2 ungrounded -> outlier, and a single-source gap.
    mixed = {"statement": "mixed", "members": [_member(), _member(source_id="s2", claim_text="Hiring slowed", quote="invented")]}
    clusters, gaps = await _graph([mixed])
    assert clusters[0].classification == "outlier"
    assert any("one source" in (g.description + g.rationale).lower() for g in gaps)


async def test_empty_cluster_is_dropped_when_a_valid_one_survives():
    clusters, _ = await _graph([
        {"statement": "survives", "members": [_member()]},
        {"statement": "vanishes", "members": [_member(source_id="s9")]},
    ])
    assert [c.statement for c in clusters] == ["survives"]


# adversarial interaction

async def test_invalid_members_are_absent_from_recheck_prompts():
    counters = {"adv": 0, "cluster": 0}
    members = [_member(), _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2"),
               _member(source_id="s9", quote="invented")]
    await _graph([{"statement": "x", "members": members}], adversarial=True, counters=counters,
                 adv_members=[{"source_id": "s1", "stance": "supports"}])
    assert counters["adv"] == 1
    assert "s9" not in "".join(counters["adv_prompts"])


async def test_multiplicity_counted_after_validation_skips_recheck():
    # Two proposed sources, but only s1 survives -> single-source cluster -> no recheck.
    counters = {"adv": 0, "cluster": 0}
    await _graph([{"statement": "x", "members": [_member(), _member(source_id="s9")]}],
                 adversarial=True, counters=counters)
    assert counters["adv"] == 0


async def test_revision_ignored_for_ambiguous_original(caplog):
    import logging
    counters = {"adv": 0, "cluster": 0}
    members = [_member(), _member(), _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2")]
    with caplog.at_level(logging.INFO, logger="research_agent.reason"):
        clusters, _ = await _graph([{"statement": "x", "members": members}], adversarial=True, counters=counters,
                                   adv_members=[{"source_id": "s1", "stance": "contradicts"}])
    assert [m.stance for m in clusters[0].members if m.source_id == "s1"] == ["supports", "supports"]
    assert "ambiguous_original" in " ".join(r.getMessage() for r in caplog.records)


async def test_conflicting_revisions_for_one_source_are_ignored(caplog):
    import logging
    members = [_member(), _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2")]
    with caplog.at_level(logging.INFO, logger="research_agent.reason"):
        clusters, _ = await _graph([{"statement": "x", "members": members}], adversarial=True,
                                   adv_members=[{"source_id": "s1", "stance": "contradicts"},
                                                {"source_id": "s1", "stance": "supports"}])
    assert all(m.stance == "supports" for m in clusters[0].members)
    assert "conflicting_revisions" in " ".join(r.getMessage() for r in caplog.records)


async def test_recheck_exception_keeps_naive_stances():
    async def fake(system: str, prompt: str, model: str):
        if "stress-test" in system:
            raise RuntimeError("recheck down")
        return {"clusters": [{"statement": "x", "members": [
            _member(), _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2")]}], "gaps": []}

    clusters, _ = await build_claim_graph("t", _grounded_sets(), call_model=fake, adversarial=True)
    assert clusters[0].classification == "consensus"


# --- gaps raised by an independent free-model review of the scenario list ------
# Its output was mostly non-committal, but these four cases were genuinely untested.

async def test_pairing_swapped_within_one_source_is_rejected():
    # Both halves are real and belong to s1, but they were never paired together.
    sets = [SourceClaims(source_id="s1", claims=[
        Claim(text="Adoption is rising", supporting_quote="adoption rose sharply"),
        Claim(text="Costs fell", supporting_quote="unit costs fell"),
    ])]
    swapped = _member(claim_text="Adoption is rising", quote="unit costs fell")
    import pytest
    with pytest.raises(ValueError, match="no member was grounded"):
        await _graph([{"statement": "x", "members": [swapped]}], sets=sets)


async def test_stance_in_wrong_case_is_rejected_not_normalized():
    clusters, _ = await _graph([{"statement": "x", "members": [
        _member(), _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2", stance="Supports")]}])
    assert [m.source_id for m in clusters[0].members] == ["s1"]


async def test_non_string_confidence_falls_back_to_medium():
    catalogue = build_claim_catalogue(_grounded_sets())
    member, reason = _validate_member({**_member(), "confidence": 5}, catalogue)
    assert reason == "" and member.confidence == "medium"


async def test_unusable_adversarial_response_keeps_naive_stances():
    for adv_response in ("not a dict", {"for": "f"}, {"members": "nope"}, {"members": [None, 7]}):
        async def fake(system: str, prompt: str, model: str, _r=adv_response):
            if "stress-test" in system:
                return _r
            return {"clusters": [{"statement": "x", "members": [
                _member(), _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2")]}], "gaps": []}

        clusters, _ = await build_claim_graph("t", _grounded_sets(), call_model=fake, adversarial=True)
        assert all(m.stance == "supports" for m in clusters[0].members), adv_response
        assert clusters[0].classification == "consensus"


async def test_every_ignored_revision_reason_is_logged(caplog):
    """Criterion 9: unknown, malformed, ambiguous and conflicting revisions all log a reason.

    Raised by the independent gpt-5.6-terra review of snapshot 3895ec58: only the
    ambiguous and conflicting cases were logged.
    """
    import logging

    cases = {
        "unknown_source": {"members": [{"source_id": "s404", "stance": "contradicts"}]},
        "malformed_revision": {"members": [None, {"source_id": 7, "stance": "supports"},
                                           {"source_id": "s1", "stance": "maybe"}]},
        "malformed_revision_collection": {"members": "not a list"},
        "malformed_recheck_response": "not an object",
    }
    members = [_member(), _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2")]
    for reason, adv in cases.items():
        async def fake(system: str, prompt: str, model: str, _a=adv):
            if "stress-test" in system:
                return _a
            return {"clusters": [{"statement": "x", "members": members}], "gaps": []}

        with caplog.at_level(logging.INFO, logger="research_agent.reason"):
            caplog.clear()
            clusters, _ = await build_claim_graph("t", _grounded_sets(), call_model=fake, adversarial=True)
        logged = " ".join(r.getMessage() for r in caplog.records)
        assert "recheck revisions ignored" in logged, reason
        assert reason in logged, (reason, logged)
        assert all(m.stance == "supports" for m in clusters[0].members)
        assert "adoption rose sharply" not in logged  # no source text in logs


# --- strengthened after the gpt-5.6-terra re-review of brief 756a0015 ----------

async def test_valid_unique_agreeing_revision_is_applied_after_validation(caplog):
    """Criterion 8: a revision that IS unambiguous must still be applied.

    Guards the opposite failure from the ignore-cases: an implementation that
    dropped every revision would pass those and fail here.
    """
    import logging
    members = [_member(), _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2")]
    with caplog.at_level(logging.INFO, logger="research_agent.reason"):
        clusters, _ = await _graph([{"statement": "x", "members": members}], adversarial=True,
                                   adv_members=[{"source_id": "s1", "stance": "supports"},
                                                {"source_id": "s2", "stance": "contradicts"}])
    stances = {m.source_id: m.stance for m in clusters[0].members}
    assert stances == {"s1": "supports", "s2": "contradicts"}
    assert clusters[0].classification == "contested"
    assert "recheck revisions ignored" not in " ".join(r.getMessage() for r in caplog.records)


async def test_no_claim_or_quote_text_reaches_any_log(caplog):
    """Criterion 15, checked across BOTH log paths and every fixture string."""
    import logging
    secrets = ["adoption rose sharply", "hiring slowed in Q2", "Adoption is rising", "Hiring slowed",
               "hiring collapsed everywhere"]
    members = [_member(), _member(source_id="s9", quote="invented"),
               _member(source_id="s2", claim_text="Hiring slowed", quote="hiring collapsed everywhere"),
               _member(source_id="s2", claim_text="Hiring slowed", quote="hiring slowed in Q2")]
    with caplog.at_level(logging.INFO, logger="research_agent.reason"):
        await _graph([{"statement": "x", "members": members}], adversarial=True,
                     adv_members=[{"source_id": "s404", "stance": "supports"}])
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "grounding rejected" in logged and "recheck revisions ignored" in logged
    for secret in secrets:
        assert secret not in logged, secret
        assert secret.lower() not in logged.lower(), secret


# --- the two golden fixtures, asserted in the test suite (not only the harness) -

def _load_fixture(name: str) -> dict:
    import json
    from pathlib import Path
    return json.loads((Path(__file__).parent / "fixtures" / "grounding" / f"{name}.json").read_text(encoding="utf-8"))


def _fixture_model(data: dict):
    async def fake(system: str, prompt: str, model: str):
        if "stress-test" in system:
            return {"for": "f", "against": "a", "members": data.get("adversarial_members", [])}
        return data["response"]
    return fake


async def _run_fixture(name: str, *, adversarial: bool):
    data = _load_fixture(name)
    sets = [SourceClaims.model_validate(s) for s in data["claim_sets"]]
    return await build_claim_graph(data["topic"], sets, call_model=_fixture_model(data), adversarial=adversarial)


async def test_golden_all_valid_fixture_output_is_stable_and_has_no_timestamps():
    first_clusters, first_gaps = await _run_fixture("all-valid", adversarial=True)
    second_clusters, second_gaps = await _run_fixture("all-valid", adversarial=True)
    dump = [c.model_dump_json() for c in first_clusters]
    assert dump == [c.model_dump_json() for c in second_clusters]  # byte-identical across runs
    assert [g.model_dump_json() for g in first_gaps] == [g.model_dump_json() for g in second_gaps]
    assert len(first_clusters) == 1
    assert [m.source_id for m in first_clusters[0].members] == ["s1", "s2"]
    assert first_clusters[0].classification == "consensus"
    assert [g.description for g in first_gaps] == ["No source covers small firms"]
    # Nothing time-varying is serialized by this stage, so the golden cannot drift.
    assert not any(key in dump[0] for key in ("generated_at", "timestamp", "20260"))


async def test_golden_mixed_fixture_survivors_relabeling_gaps_and_removal():
    clusters, gaps = await _run_fixture("mixed-invalid", adversarial=False)
    assert len(clusters) == 1, "the second cluster had nothing grounded and must be dropped"
    assert clusters[0].statement == "Adoption of AI tooling is rising"
    assert [(m.source_id, m.claim_text, m.supporting_quote) for m in clusters[0].members] == [
        ("s1", "adoption   IS rising", "Adoption  Rose   Sharply")
    ]
    assert clusters[0].classification == "outlier", "relabelled from the baseline's consensus"
    assert [g.description for g in gaps] == ["Only one source addresses: Adoption of AI tooling is rising"]


async def test_golden_mixed_fixture_drops_a_model_call_versus_the_baseline():
    """Fixture-only cost proxy: 2 calls become 1 once ungrounded members are gone."""
    data = _load_fixture("mixed-invalid")
    calls = {"n": 0}

    async def counting(system: str, prompt: str, model: str):
        calls["n"] += 1
        if "stress-test" in system:
            return {"for": "f", "against": "a", "members": data.get("adversarial_members", [])}
        return data["response"]

    sets = [SourceClaims.model_validate(s) for s in data["claim_sets"]]
    await build_claim_graph(data["topic"], sets, call_model=counting, adversarial=True)
    assert calls["n"] == 1, "only the clustering call: the survivor is single-source, so no recheck"
