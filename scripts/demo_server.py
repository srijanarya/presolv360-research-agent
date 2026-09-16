"""Demo server for recording the walkthrough video.

Serves the real SPA + API, but replaces the pipeline with a *replay* of a real prior
run (`scripts/fixtures/demo-replay-brief.json`) so it is fast, deterministic, and not
gated by model rate-limits. The UI, the SSE stream, and the rendered Claim Graph are
all the real thing — only the model invocation is replayed (standard demo practice).

Run:  uv run python scripts/demo_server.py   # serves on http://localhost:8009
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import uvicorn

from research_agent.api import create_app
from research_agent.models import Brief

BRIEF_PATH = Path(__file__).resolve().parent / "fixtures" / "demo-replay-brief.json"


async def replay(topic, urls, *, on_event=None, adversarial=True) -> Brief:
    brief = Brief.model_validate_json(BRIEF_PATH.read_text(encoding="utf-8"))

    async def emit(event: dict) -> None:
        if on_event is not None:
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result

    await emit({"type": "stage_started", "stage": "fetch", "total": len(brief.sources)})
    for source in brief.sources:
        await asyncio.sleep(1.1)  # one source badge appears at a time
        await emit({
            "type": "source_status",
            "id": source.id, "url": source.url, "status": source.status, "title": source.title,
        })
    await asyncio.sleep(0.4)
    await emit({"type": "stage_completed", "stage": "fetch",
                "ok": brief.meta.sources_ok, "failed": brief.meta.sources_failed})

    await emit({"type": "stage_started", "stage": "extract"})
    await asyncio.sleep(1.6)
    n_claims = sum(len(c.members) for c in brief.claim_clusters)
    await emit({"type": "stage_completed", "stage": "extract", "claims": n_claims})

    await emit({"type": "stage_started", "stage": "reason"})
    await asyncio.sleep(2.0)
    await emit({"type": "stage_completed", "stage": "reason",
                "clusters": len(brief.claim_clusters), "gaps": len(brief.gaps)})

    await emit({"type": "stage_started", "stage": "synthesize"})
    await asyncio.sleep(0.7)
    await emit({"type": "stage_completed", "stage": "synthesize"})
    return brief


app = create_app(pipeline_fn=replay)


if __name__ == "__main__":
    assert BRIEF_PATH.exists(), f"replay data missing: {BRIEF_PATH}"
    uvicorn.run(app, host="127.0.0.1", port=8009, log_level="warning")
