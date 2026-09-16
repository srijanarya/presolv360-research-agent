"""E6 — FastAPI backend + SSE (TestClient + injected fake pipeline, no network/LLM)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from research_agent.api import create_app
from research_agent.models import (
    Brief,
    ClaimCluster,
    ClaimMember,
    Meta,
    Source,
)


def _brief() -> Brief:
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


async def _fake_pipeline(topic, urls, *, on_event=None, adversarial=True):
    for stage in ("fetch", "extract", "reason", "synthesize"):
        if on_event is not None:
            await on_event({"type": "stage_started", "stage": stage})
    return _brief()


def _client(pipeline=_fake_pipeline) -> TestClient:
    return TestClient(create_app(pipeline_fn=pipeline))


def _sse_events(text: str) -> list[dict]:
    return [json.loads(line[5:].strip()) for line in text.splitlines() if line.startswith("data:")]


# --- E6.S1 — start a run ---

def test_post_research_returns_run_id():
    with _client() as c:
        r = c.post("/api/research", json={"topic": "t", "urls": ["u1", "u2", "u3"]})
        assert r.status_code == 200
        assert r.json()["run_id"]


def test_post_research_rejects_too_few_urls():
    with _client() as c:
        r = c.post("/api/research", json={"topic": "t", "urls": ["u1", "u2"]})
        assert r.status_code == 422


def test_post_research_rejects_too_many_urls():
    with _client() as c:
        r = c.post("/api/research", json={"topic": "t", "urls": ["u1", "u2", "u3", "u4", "u5", "u6"]})
        assert r.status_code == 422


# --- E6.S2 — SSE progress ordering ---

def test_sse_emits_ordered_events_ending_in_done():
    with _client() as c:
        run_id = c.post("/api/research", json={"topic": "t", "urls": ["u1", "u2", "u3"]}).json()["run_id"]
        events = _sse_events(c.get(f"/api/research/{run_id}/stream").text)
        stages = [e["stage"] for e in events if e["type"] == "stage_started"]
        assert stages == ["fetch", "extract", "reason", "synthesize"]
        assert events[-1]["type"] == "done"
        Brief.model_validate(events[-1]["brief"])  # terminal carries valid brief.json


def test_sse_emits_error_event_on_pipeline_failure():
    async def boom(topic, urls, *, on_event=None, adversarial=True):
        raise RuntimeError("kaboom")

    with _client(boom) as c:
        run_id = c.post("/api/research", json={"topic": "t", "urls": ["u1", "u2", "u3"]}).json()["run_id"]
        events = _sse_events(c.get(f"/api/research/{run_id}/stream").text)
        assert any(e["type"] == "error" for e in events)


# --- E6.S3 — result + view endpoints ---

def test_view_endpoints_content_types_and_404():
    with _client() as c:
        run_id = c.post("/api/research", json={"topic": "t", "urls": ["u1", "u2", "u3"]}).json()["run_id"]
        c.get(f"/api/research/{run_id}/stream")  # drive the run to completion

        rj = c.get(f"/api/research/{run_id}")
        assert rj.status_code == 200
        assert rj.headers["content-type"].startswith("application/json")

        rm = c.get(f"/api/research/{run_id}/brief.md")
        assert rm.status_code == 200
        assert "markdown" in rm.headers["content-type"]

        rh = c.get(f"/api/research/{run_id}/brief.html")
        assert rh.status_code == 200
        assert "text/html" in rh.headers["content-type"]

        assert c.get("/api/research/does-not-exist").status_code == 404


# --- P2 — a reasoning failure must reach the client, not a plausible brief -----

def test_reasoning_failure_yields_sse_error_no_done_and_no_brief():
    """Ungroundable model output ends the run with an SSE `error`.

    Wires the REAL pipeline and the REAL reasoning stage with fake fetch/extract
    and a model that returns `{"clusters": null}`, so the failure travels the
    production path: reason -> pipeline -> API.
    """
    import functools

    from research_agent.models import Claim, SourceClaims, SourceDoc
    from research_agent.pipeline import run_pipeline
    from research_agent.reason import build_claim_graph

    async def fake_fetch(pairs):
        return [SourceDoc(id=sid, url=url, status="ok", text="adoption rose sharply") for sid, url in pairs]

    async def fake_extract(topic, docs):
        return [
            SourceClaims(source_id=d.id, url=d.url, claims=[
                Claim(text="Adoption is rising", supporting_quote="adoption rose sharply")])
            for d in docs
        ]

    async def unusable_reason(topic, claim_sets, *, adversarial=True):
        async def model(system, prompt, model_name):
            return {"clusters": None}
        return await build_claim_graph(topic, claim_sets, call_model=model, adversarial=adversarial)

    pipeline = functools.partial(
        run_pipeline, fetch_fn=fake_fetch, extract_fn=fake_extract, reason_fn=unusable_reason
    )

    with _client(pipeline) as c:
        run_id = c.post("/api/research", json={"topic": "t", "urls": ["u1", "u2", "u3"]}).json()["run_id"]
        events = _sse_events(c.get(f"/api/research/{run_id}/stream").text)

        errors = [e for e in events if e["type"] == "error"]
        assert len(errors) == 1
        assert "clusters" in errors[0]["error"]
        assert not any(e["type"] == "done" for e in events)
        # No brief is retrievable in any view.
        assert c.get(f"/api/research/{run_id}").status_code == 409
        assert c.get(f"/api/research/{run_id}/brief.md").status_code == 409
        assert c.get(f"/api/research/{run_id}/brief.html").status_code == 409
