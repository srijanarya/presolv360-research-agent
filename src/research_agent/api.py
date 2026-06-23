"""FastAPI backend — exposes the pipeline as an API with live SSE progress.

The live decomposition *is* the demo: a run streams `stage_started` / `source_status`
/ `stage_completed` events as they happen, ending in a `done` event carrying the full
`brief.json`. The pipeline is run inside the SSE request via a per-request queue (no
global background tasks), and `pipeline_fn` is injectable for testing.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from research_agent.models import Brief
from research_agent.pipeline import run_pipeline
from research_agent.synthesize import render_html, render_markdown

_WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


class ResearchRequest(BaseModel):
    topic: str = Field(min_length=1)
    urls: list[str] = Field(min_length=3, max_length=5)  # the brief's 3–5 sources → 422 otherwise
    adversarial: bool = True


@dataclass
class RunState:
    run_id: str
    topic: str
    urls: list[str]
    adversarial: bool = True
    status: str = "pending"  # pending | running | done | error
    events: list[dict] = field(default_factory=list)
    brief: Brief | None = None
    error: str | None = None


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def create_app(pipeline_fn=run_pipeline) -> FastAPI:
    app = FastAPI(title="Cross-Source Research Agent")
    runs: dict[str, RunState] = {}

    def _get(run_id: str) -> RunState:
        state = runs.get(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        return state

    def _require_brief(run_id: str) -> Brief:
        state = _get(run_id)
        if state.brief is None:
            raise HTTPException(status_code=409, detail=f"run not finished (status={state.status})")
        return state.brief

    @app.post("/api/research")
    async def start_research(req: ResearchRequest) -> dict:
        run_id = uuid.uuid4().hex[:12]
        runs[run_id] = RunState(run_id=run_id, topic=req.topic, urls=req.urls, adversarial=req.adversarial)
        return {"run_id": run_id}

    def _ensure_driving(state: RunState) -> None:
        """Start the pipeline exactly once per run.

        The status check + set is synchronous (no await between), so concurrent
        stream connections can't launch duplicate runs — the first flips `pending`
        → `running` and drives; the rest just tail the shared `events` list.
        """
        if state.status != "pending":
            return
        state.status = "running"

        async def on_event(event: dict) -> None:
            if event.get("type") != "done":  # the API appends its own authoritative terminal
                state.events.append(event)

        async def drive() -> None:
            try:
                brief = await pipeline_fn(
                    state.topic, state.urls, on_event=on_event, adversarial=state.adversarial
                )
                state.brief, state.status = brief, "done"
                state.events.append({"type": "done", "brief": brief.model_dump()})
            except Exception as exc:  # noqa: BLE001 — surface failures as an SSE error event
                state.status, state.error = "error", str(exc)
                state.events.append({"type": "error", "error": str(exc)})

        asyncio.create_task(drive())

    @app.get("/api/research/{run_id}/stream")
    async def stream(run_id: str) -> StreamingResponse:
        state = _get(run_id)
        _ensure_driving(state)

        async def gen():
            # Tail the shared events list (works for the driver and any later/extra connection).
            idx = 0
            while True:
                if idx < len(state.events):
                    event = state.events[idx]
                    idx += 1
                    yield _sse(event)
                    if event["type"] in ("done", "error"):
                        return
                elif state.status in ("done", "error"):
                    return  # terminal already emitted
                else:
                    await asyncio.sleep(0.05)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/api/research/{run_id}")
    async def get_brief(run_id: str) -> JSONResponse:
        return JSONResponse(_require_brief(run_id).model_dump())

    @app.get("/api/research/{run_id}/brief.md")
    async def get_brief_md(run_id: str) -> PlainTextResponse:
        return PlainTextResponse(render_markdown(_require_brief(run_id)), media_type="text/markdown")

    @app.get("/api/research/{run_id}/brief.html")
    async def get_brief_html(run_id: str) -> HTMLResponse:
        return HTMLResponse(render_html(_require_brief(run_id)))

    # Serve the built SPA at "/" in production (skipped in dev/tests if not built).
    if _WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="spa")

    return app


app = create_app()
