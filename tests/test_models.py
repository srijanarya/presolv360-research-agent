"""E1.S3 — Claim Graph contract round-trips and rejects bad data."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_agent.models import (
    Brief,
    ClaimCluster,
    ClaimMember,
    Gap,
    Meta,
    Source,
)


def _sample_brief() -> Brief:
    return Brief(
        topic="AI's impact on the job market",
        generated_at="2026-06-23T00:00:00Z",
        sources=[
            Source(id="s1", url="https://a.example", title="A", status="ok", fetch_method="httpx"),
            Source(id="s2", url="https://b.example", title="B", status="error", error="boom"),
        ],
        claim_clusters=[
            ClaimCluster(
                id="c1",
                statement="AI displaces entry-level jobs",
                classification="consensus",
                members=[
                    ClaimMember(source_id="s1", stance="supports", claim_text="entry-level hit hardest", supporting_quote="hitting before careers can start", confidence="high"),
                    ClaimMember(source_id="s2", stance="supports", claim_text="juniors most exposed", supporting_quote="junior roles automate first", confidence="medium"),
                ],
            ),
            ClaimCluster(
                id="c2",
                statement="Net employment effect is positive",
                classification="contested",
                members=[
                    ClaimMember(source_id="s1", stance="contradicts", claim_text="net loss near term", supporting_quote="destruction outpaces creation", confidence="low"),
                ],
            ),
        ],
        gaps=[Gap(description="Wage effects unaddressed", rationale="no source quantifies pay")],
        meta=Meta(sources_ok=1, sources_failed=1, model_reason="claude-opus-4-8", model_extract="claude-sonnet-4-6"),
    )


def test_brief_roundtrips_through_json():
    brief = _sample_brief()
    restored = Brief.model_validate_json(brief.model_dump_json())
    assert restored == brief


def test_brief_rejects_unknown_classification():
    payload = _sample_brief().model_dump()
    payload["claim_clusters"][0]["classification"] = "maybe"
    with pytest.raises(ValidationError):
        Brief.model_validate(payload)


def test_brief_rejects_unknown_status():
    payload = _sample_brief().model_dump()
    payload["sources"][0]["status"] = "exploded"
    with pytest.raises(ValidationError):
        Brief.model_validate(payload)
