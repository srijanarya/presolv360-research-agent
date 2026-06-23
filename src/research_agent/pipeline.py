"""Orchestration — the four visible stages, wired together.

`run_pipeline` owns the decomposition explicitly (fetch → extract → reason →
synthesize) and emits progress *events* at each boundary, so the same run can drive
a CLI log or the SSE stream that powers the web UI. The stage functions are
dependency-injected for offline testing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from research_agent.extract import extract_all
from research_agent.fetch import fetch_all
from research_agent.llm import MODEL_EXTRACT, MODEL_REASON
from research_agent.models import Brief
from research_agent.reason import build_claim_graph
from research_agent.synthesize import assemble_brief


async def _emit(on_event, event: dict) -> None:
    if on_event is None:
        return
    result = on_event(event)
    if asyncio.iscoroutine(result):
        await result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_pipeline(
    topic: str,
    urls: list[str],
    *,
    adversarial: bool = True,
    on_event=None,
    fetch_fn=fetch_all,
    extract_fn=extract_all,
    reason_fn=build_claim_graph,
) -> Brief:
    pairs = [(f"s{i + 1}", url) for i, url in enumerate(urls)]

    await _emit(on_event, {"type": "stage_started", "stage": "fetch", "total": len(pairs)})
    docs = await fetch_fn(pairs)
    for doc in docs:
        await _emit(
            on_event,
            {"type": "source_status", "id": doc.id, "url": doc.url, "status": doc.status, "title": doc.title},
        )
    ok = sum(1 for d in docs if d.status == "ok")
    await _emit(on_event, {"type": "stage_completed", "stage": "fetch", "ok": ok, "failed": len(docs) - ok})

    await _emit(on_event, {"type": "stage_started", "stage": "extract"})
    claim_sets = await extract_fn(topic, docs)
    n_claims = sum(len(c.claims) for c in claim_sets)
    await _emit(on_event, {"type": "stage_completed", "stage": "extract", "claims": n_claims})

    await _emit(on_event, {"type": "stage_started", "stage": "reason"})
    clusters, gaps = await reason_fn(topic, claim_sets, adversarial=adversarial)
    await _emit(on_event, {"type": "stage_completed", "stage": "reason", "clusters": len(clusters), "gaps": len(gaps)})

    await _emit(on_event, {"type": "stage_started", "stage": "synthesize"})
    brief = assemble_brief(
        topic, _now_iso(), docs, clusters, gaps,
        model_reason=MODEL_REASON, model_extract=MODEL_EXTRACT,
    )
    await _emit(on_event, {"type": "stage_completed", "stage": "synthesize"})
    await _emit(on_event, {"type": "done"})
    return brief
