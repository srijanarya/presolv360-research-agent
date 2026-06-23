"""E5 — pipeline wiring + brief writer (offline, injected fakes)."""

from __future__ import annotations

from research_agent.models import (
    Brief,
    Claim,
    ClaimCluster,
    ClaimMember,
    Meta,
    Source,
    SourceClaims,
    SourceDoc,
)
from research_agent.pipeline import run_pipeline
from research_agent.synthesize import write_brief


def _minimal_brief() -> Brief:
    return Brief(
        topic="t",
        generated_at="2026-06-23T00:00:00Z",
        sources=[Source(id="s1", url="u1", status="ok")],
        claim_clusters=[
            ClaimCluster(
                id="c1", statement="X", classification="outlier",
                members=[ClaimMember(source_id="s1", stance="supports", claim_text="a", supporting_quote="qa")],
            )
        ],
        gaps=[],
        meta=Meta(sources_ok=1, sources_failed=0),
    )


def test_write_brief_roundtrips_to_run_dir(tmp_path):
    brief = _minimal_brief()
    paths = write_brief(brief, tmp_path / "run1")
    assert paths["json"].exists() and paths["md"].exists() and paths["html"].exists()
    assert Brief.model_validate_json(paths["json"].read_text()) == brief


async def test_pipeline_wires_stages_and_carries_failed_source():
    async def fake_fetch(pairs):
        return [
            SourceDoc(id="s1", url="u1", status="ok", text="t1", title="T1"),
            SourceDoc(id="s2", url="u2", status="error", error="boom"),
        ]

    async def fake_extract(topic, docs):
        return [SourceClaims(source_id="s1", url="u1", claims=[Claim(text="a", supporting_quote="qa")])]

    async def fake_reason(topic, claim_sets, *, adversarial=True):
        cluster = ClaimCluster(
            id="c1", statement="X", classification="outlier",
            members=[ClaimMember(source_id="s1", stance="supports", claim_text="a", supporting_quote="qa")],
        )
        return [cluster], []

    events: list[str] = []
    brief = await run_pipeline(
        "topic",
        ["u1", "u2"],
        on_event=lambda e: events.append(e["type"]),
        fetch_fn=fake_fetch,
        extract_fn=fake_extract,
        reason_fn=fake_reason,
    )

    assert brief.meta.sources_ok == 1
    assert brief.meta.sources_failed == 1   # failed source carried into the brief
    assert len(brief.claim_clusters) == 1
    assert "done" in events
    assert events.count("source_status") == 2  # one per source
