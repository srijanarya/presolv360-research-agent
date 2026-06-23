"""Stage 3 — cross-source reasoning (the Claim Graph). The graded "hard part".

Pipeline within the stage:
  1. **Cluster** (1 model call): group claims that assert the same thing across
     sources; each member carries the source's *stance* (supports/contradicts).
     Also surface coverage *gaps* (sub-topics no source addresses).
  2. **Adversarial cross-check** (1 model call per cluster, in parallel; the
     differentiator): argue the strongest case FOR and AGAINST each cluster, then
     correct stances — so a contradiction the naive clustering merged into agreement
     is exposed. Adapts arXiv 2602.18693 (prompt-based; Claude exposes no logprobs).
  3. **Classify** (pure, deterministic): `classify_cluster` labels each cluster
     consensus / contested / outlier from its members' stances.

The label is a *pure function* of stances (testable, no LLM); the LLM only supplies
stances + clustering. `call_model` is dependency-injected (tested with fakes).
"""

from __future__ import annotations

import asyncio
import logging

from research_agent.llm import MODEL_REASON, call_model as _real_call_model
from research_agent.models import (
    Claim,
    ClaimCluster,
    ClaimMember,
    Classification,
    Gap,
    SourceClaims,
)

logger = logging.getLogger("research_agent.reason")


# ----------------------------- pure logic ----------------------------------- #

def classify_cluster(members: list[ClaimMember]) -> Classification:
    """Label a cluster from its members' stances.

    - **contested**: at least one source supports and at least one contradicts.
    - **consensus**: ≥2 *distinct* sources agree (dedupe by source).
    - **outlier**: a single source's position.
    """
    stances = {m.stance for m in members}
    if "supports" in stances and "contradicts" in stances:
        return "contested"
    if len({m.source_id for m in members}) >= 2:
        return "consensus"
    return "outlier"


def derive_gaps(clusters: list[ClaimCluster]) -> list[Gap]:
    """Coverage gaps derivable from the graph: claims only ONE source addresses.

    (LLM-surfaced zero-coverage sub-topics are added separately in `build_claim_graph`.)
    """
    gaps: list[Gap] = []
    for cluster in clusters:
        if len({m.source_id for m in cluster.members}) == 1:
            gaps.append(
                Gap(
                    description=f"Only one source addresses: {cluster.statement}",
                    rationale="Single-source claim — not corroborated by any other source.",
                )
            )
    return gaps


# ----------------------------- prompts -------------------------------------- #

CLUSTER_SYSTEM = """You are a cross-source research analyst. You are given the claims that several \
sources made about a topic. Cluster claims that assert the SAME thing (even if worded differently) \
across sources, and surface coverage gaps.

For each cluster: write a neutral "statement" capturing the shared assertion, and list its \
"members" — one per (source, claim) — each with the source_id, the source's "stance" toward the \
cluster statement ("supports" or "contradicts"), the source's "claim_text", its "supporting_quote" \
(carried over verbatim), and "confidence".

Put genuinely CONTRADICTING claims about the same point in the SAME cluster, with opposing stances — \
do not split them apart — so disagreements surface. A claim only one source makes is a valid \
single-member cluster.

Also list "gaps": sub-topics clearly relevant to the topic that NONE of the sources adequately address.

Return ONLY valid JSON, no preamble, no code fences:
{"clusters":[{"statement":"...","members":[{"source_id":"s1","stance":"supports|contradicts","claim_text":"...","supporting_quote":"...","confidence":"high|medium|low"}]}],"gaps":[{"description":"...","rationale":"..."}]}"""

ADVERSARIAL_SYSTEM = """You are a skeptical analyst stress-testing one claim cluster. Given the cluster \
statement and each source's position, argue the STRONGEST case FOR the statement and the STRONGEST \
case AGAINST it, using ONLY the provided source claims and quotes (invent nothing).

Then return each member with a CORRECTED stance: if a source's claim actually contradicts the \
statement — or the case-against shows its position genuinely conflicts — set its stance to \
"contradicts"; otherwise "supports". Keep each source's claim_text and supporting_quote unchanged.

Return ONLY valid JSON, no preamble, no code fences:
{"for":"...","against":"...","members":[{"source_id":"...","stance":"supports|contradicts"}]}"""


def _cluster_prompt(topic: str, claim_sets: list[SourceClaims]) -> str:
    lines = [f"TOPIC: {topic}", "", "CLAIMS BY SOURCE:"]
    for sc in claim_sets:
        lines.append(f"\n[{sc.source_id}] {sc.url}")
        for claim in sc.claims:
            lines.append(f'  - {claim.text}  (quote: "{claim.supporting_quote}")')
    lines.append("\nCluster these claims across sources and list coverage gaps.")
    return "\n".join(lines)


def _adversarial_prompt(topic: str, statement: str, members: list[ClaimMember]) -> str:
    lines = [f"TOPIC: {topic}", f"CLUSTER STATEMENT: {statement}", "", "SOURCE POSITIONS:"]
    for m in members:
        lines.append(f'  [{m.source_id}] ({m.stance}) {m.claim_text}  (quote: "{m.supporting_quote}")')
    lines.append("\nArgue for and against, then return corrected stances.")
    return "\n".join(lines)


# ----------------------------- parsing -------------------------------------- #

def _parse_members(raw_members) -> list[ClaimMember]:
    members: list[ClaimMember] = []
    if not isinstance(raw_members, list):
        return members
    for item in raw_members:
        if not isinstance(item, dict) or not item.get("source_id"):
            continue
        stance = item.get("stance")
        if stance not in ("supports", "contradicts"):
            stance = "supports"
        confidence = item.get("confidence", "medium")
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        members.append(
            ClaimMember(
                source_id=str(item["source_id"]),
                stance=stance,
                claim_text=str(item.get("claim_text", "")),
                supporting_quote=str(item.get("supporting_quote", "")),
                confidence=confidence,
            )
        )
    return members


def _parse_gaps(raw_gaps) -> list[Gap]:
    gaps: list[Gap] = []
    if not isinstance(raw_gaps, list):
        return gaps
    for item in raw_gaps:
        if isinstance(item, dict) and item.get("description"):
            gaps.append(Gap(description=str(item["description"]), rationale=str(item.get("rationale", ""))))
    return gaps


# ----------------------------- orchestration -------------------------------- #

async def _adversarial_recheck(
    topic: str, statement: str, members: list[ClaimMember], call_model
) -> list[ClaimMember]:
    """Re-examine a cluster for/against; return members with corrected stances.

    Provenance is preserved: we only update each ORIGINAL member's stance from the
    recheck (keyed by source_id); quotes/claim_text are never touched.
    """
    try:
        raw = await call_model(ADVERSARIAL_SYSTEM, _adversarial_prompt(topic, statement, members), MODEL_REASON)
    except Exception as exc:  # noqa: BLE001 — resilience: keep the naive stances
        logger.warning("adversarial recheck failed for %r: %s", statement[:60], exc)
        return members

    revised = raw.get("members", []) if isinstance(raw, dict) else []
    new_stance = {
        m["source_id"]: m["stance"]
        for m in revised
        if isinstance(m, dict) and m.get("source_id") and m.get("stance") in ("supports", "contradicts")
    }
    return [m.model_copy(update={"stance": new_stance.get(m.source_id, m.stance)}) for m in members]


async def build_claim_graph(
    topic: str,
    claim_sets: list[SourceClaims],
    *,
    call_model=_real_call_model,
    adversarial: bool = True,
) -> tuple[list[ClaimCluster], list[Gap]]:
    """Cluster → (adversarial recheck) → classify. Returns (clusters, gaps)."""
    raw = await call_model(CLUSTER_SYSTEM, _cluster_prompt(topic, claim_sets), MODEL_REASON)
    raw_clusters = raw.get("clusters", []) if isinstance(raw, dict) else []
    llm_gaps = _parse_gaps(raw.get("gaps", []) if isinstance(raw, dict) else [])

    async def _finalize(index: int, raw_cluster: dict) -> ClaimCluster | None:
        if not isinstance(raw_cluster, dict):
            return None
        members = _parse_members(raw_cluster.get("members", []))
        if not members:
            return None
        statement = str(raw_cluster.get("statement", "")).strip() or "(unnamed cluster)"
        if adversarial:
            members = await _adversarial_recheck(topic, statement, members, call_model)
        return ClaimCluster(
            id=f"c{index + 1}",
            statement=statement,
            classification=classify_cluster(members),
            members=members,
        )

    finalized = await asyncio.gather(*(_finalize(i, rc) for i, rc in enumerate(raw_clusters)))
    clusters = [c for c in finalized if c is not None]
    gaps = llm_gaps + derive_gaps(clusters)
    return clusters, gaps
