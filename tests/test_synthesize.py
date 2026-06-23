"""E5 — Synthesis & output views (pure rendering over a Brief)."""

from __future__ import annotations

import re

from research_agent.models import (
    Brief,
    ClaimCluster,
    ClaimMember,
    Gap,
    Meta,
    Source,
)
from research_agent.synthesize import derive_meta, render_html, render_markdown


def _brief() -> Brief:
    sources = [
        Source(id="s1", url="https://a.example/x", title="A", status="ok", fetch_method="httpx"),
        Source(id="s2", url="https://b.example/y", title="B", status="ok", fetch_method="httpx"),
        Source(id="s3", url="https://c.example/z", title="C", status="paywalled", error="paywalled"),
    ]
    clusters = [
        ClaimCluster(
            id="c1", statement="AI hits entry-level jobs first", classification="consensus",
            members=[
                ClaimMember(source_id="s1", stance="supports", claim_text="juniors most exposed", supporting_quote="hitting before careers can start", confidence="high"),
                ClaimMember(source_id="s2", stance="supports", claim_text="entry roles automate first", supporting_quote="entry-level demand fell", confidence="medium"),
            ],
        ),
        ClaimCluster(
            id="c2", statement="Net employment effect is positive", classification="contested",
            members=[
                ClaimMember(source_id="s1", stance="contradicts", claim_text="near-term net loss", supporting_quote="destruction outpaces creation", confidence="medium"),
                ClaimMember(source_id="s2", stance="supports", claim_text="net gain over time", supporting_quote="new roles emerge", confidence="low"),
            ],
        ),
        ClaimCluster(
            id="c3", statement="Wages will polarize", classification="outlier",
            members=[
                ClaimMember(source_id="s2", stance="supports", claim_text="wage polarization", supporting_quote="middle wages squeezed", confidence="low"),
            ],
        ),
    ]
    return Brief(
        topic="AI's impact on the job market",
        generated_at="2026-06-23T12:00:00Z",
        sources=sources,
        claim_clusters=clusters,
        gaps=[Gap(description="Geographic variation unaddressed", rationale="no source breaks out regions")],
        meta=derive_meta(sources, model_reason="claude-opus-4-8", model_extract="claude-sonnet-4-6"),
    )


# --- E5.S1 — meta counts ---

def test_meta_counts_match_sources():
    sources = [
        Source(id="s1", url="u1", status="ok"),
        Source(id="s2", url="u2", status="ok"),
        Source(id="s3", url="u3", status="ok"),
        Source(id="s4", url="u4", status="ok"),
        Source(id="s5", url="u5", status="error"),
    ]
    meta = derive_meta(sources, model_reason="r", model_extract="e")
    assert meta.sources_ok == 4
    assert meta.sources_failed == 1


# --- E5.S2 — markdown brief ---

def test_markdown_has_consensus_contested_outlier_sections():
    md = render_markdown(_brief())
    assert "Consensus" in md
    assert "Contested" in md
    assert "Outlier" in md


def test_every_claim_line_has_a_citation():
    md = render_markdown(_brief())
    claim_lines = [ln for ln in md.splitlines() if "supporting_quote" not in ln and re.search(r'"\w', ln) and ln.strip().startswith("-")]
    # Every rendered claim bullet must reference a source id like [s1].
    claim_bullets = [ln for ln in md.splitlines() if ln.strip().startswith("- ") and ("supports" in ln or "contradicts" in ln)]
    assert claim_bullets, "expected claim bullets to be rendered"
    assert all(re.search(r"\[s\d+\]", ln) for ln in claim_bullets)


def test_failed_sources_appear_in_status_table():
    md = render_markdown(_brief())
    assert "paywalled" in md
    assert "https://c.example/z" in md


# --- E5.S3 — standalone HTML report ---

def test_html_is_self_contained():
    html = render_html(_brief())
    assert "<style" in html                 # inline styling, not a CDN stylesheet
    assert "<link" not in html.lower()       # no external stylesheet
    assert "cdn" not in html.lower()         # no CDN/network asset deps


def test_html_contains_each_claim_statement():
    html = render_html(_brief())
    for statement in ("AI hits entry-level jobs first", "Net employment effect is positive", "Wages will polarize"):
        assert statement in html
