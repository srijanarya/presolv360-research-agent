"""E4.S2 — `classify_cluster` pure logic (the deterministic core of the Claim Graph).

Written during E1 (highest-risk core retired first). No network/LLM: given labeled
members, the classification is a pure function. This is THE unit-tested core.
"""

from __future__ import annotations

from research_agent.models import ClaimMember
from research_agent.reason import classify_cluster


def _m(source_id: str, stance: str = "supports") -> ClaimMember:
    return ClaimMember(source_id=source_id, stance=stance, claim_text="c", supporting_quote="q")


def test_two_sources_supporting_is_consensus():
    assert classify_cluster([_m("s1"), _m("s2")]) == "consensus"


def test_support_plus_contradict_is_contested():
    assert classify_cluster([_m("s1", "supports"), _m("s2", "contradicts")]) == "contested"


def test_single_member_is_outlier():
    assert classify_cluster([_m("s1")]) == "outlier"


def test_two_distinct_sources_same_stance_not_outlier():
    assert classify_cluster([_m("s1"), _m("s2")]) != "outlier"


def test_same_source_twice_does_not_make_consensus():
    # Dedupe by source: one source repeating itself is still a single voice → outlier.
    assert classify_cluster([_m("s1"), _m("s1")]) == "outlier"


def test_three_sources_one_dissent_is_contested():
    # Any genuine contradiction surfaces as contested (the differentiator is liberal here).
    members = [_m("s1"), _m("s2"), _m("s3", "contradicts")]
    assert classify_cluster(members) == "contested"
