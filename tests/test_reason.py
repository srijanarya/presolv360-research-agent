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
