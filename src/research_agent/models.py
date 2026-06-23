"""The Claim Graph contract — the single source of truth (`brief.json`).

MD, HTML, and the SPA are all *views* over a `Brief`. Pydantic gives us JSON
round-trip + validation (e.g. an unknown `classification` is rejected) for free.
See `architecture.md` §4.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# --- closed vocabularies (Literal => validation rejects anything off-list) ---
FetchStatus = Literal["ok", "paywalled", "js_required", "timeout", "empty", "error"]
Classification = Literal["consensus", "contested", "outlier"]
Stance = Literal["supports", "contradicts"]
Confidence = Literal["high", "medium", "low"]


class Source(BaseModel):
    id: str
    url: str
    title: str = ""
    status: FetchStatus = "ok"
    fetch_method: str | None = None
    error: str | None = None


class ClaimMember(BaseModel):
    source_id: str
    stance: Stance
    claim_text: str
    supporting_quote: str
    confidence: Confidence = "medium"


class ClaimCluster(BaseModel):
    id: str
    statement: str
    classification: Classification
    members: list[ClaimMember]


class Gap(BaseModel):
    description: str
    rationale: str = ""


class Meta(BaseModel):
    sources_ok: int = 0
    sources_failed: int = 0
    model_reason: str = ""
    model_extract: str = ""


class Brief(BaseModel):
    topic: str
    generated_at: str
    sources: list[Source]
    claim_clusters: list[ClaimCluster]
    gaps: list[Gap]
    meta: Meta
