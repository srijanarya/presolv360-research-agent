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

Every proposed member is first checked against the claims extraction actually
produced (`build_claim_catalogue` + `_validate_member`): the whole
`(source_id, claim_text, supporting_quote)` association must match, so a model
cannot attach a real quote to rewritten claim text or invent provenance.
Validation runs BEFORE the adversarial pass, classification and the *derived*
gaps. Gaps the model surfaces itself are parsed as returned and are not grounded
(ADR 001 records this as a known limitation).

The label is a *pure function* of stances (testable, no LLM); the LLM only supplies
stances + clustering. `call_model` is dependency-injected (tested with fakes).
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter

# Imported, not reimplemented: grounding comparisons must not drift from the
# normalization that produced the extracted claims (ADR 001).
from research_agent.extract import _norm_ws
from research_agent.llm import MODEL_ADVERSARIAL, MODEL_REASON, call_model as _real_call_model
from research_agent.models import (
    Claim,
    ClaimCluster,
    ClaimMember,
    Classification,
    Gap,
    SourceClaims,
)

logger = logging.getLogger("research_agent.reason")


# ----------------------------- grounding ------------------------------------ #

def _norm(text: str) -> str:
    """Main's whitespace normalization, then lowercase (ADR 001)."""
    return _norm_ws(text).lower()


def build_claim_catalogue(claim_sets: list[SourceClaims]) -> dict[str, set[tuple[str, str]]]:
    """source_id -> the complete (claim_text, quote) associations extraction produced.

    Associations are unioned when an input source id repeats: two entries for one
    source are two legitimate claim sets, not a conflict.
    """
    catalogue: dict[str, set[tuple[str, str]]] = {}
    for source_claims in claim_sets:
        entries = catalogue.setdefault(str(source_claims.source_id), set())
        for claim in source_claims.claims:
            entries.add((_norm(claim.text), _norm(claim.supporting_quote)))
    return catalogue


def _validate_member(item, catalogue: dict[str, set[tuple[str, str]]]) -> tuple[ClaimMember | None, str]:
    """Return (member, "") when grounded, else (None, reason_code).

    An accepted member keeps the model's original formatting; only the comparison
    is normalized.
    """
    if not isinstance(item, dict):
        return None, "malformed_member"
    source_id = item.get("source_id")
    if not isinstance(source_id, str) or not source_id.strip():
        return None, "missing_source_id"
    claim_text = item.get("claim_text")
    if not isinstance(claim_text, str) or not claim_text.strip():
        return None, "missing_claim_text"
    quote = item.get("supporting_quote")
    if not isinstance(quote, str) or not quote.strip():
        return None, "missing_quote"
    if item.get("stance") not in ("supports", "contradicts"):
        return None, "invalid_stance"
    associations = catalogue.get(source_id)
    if associations is None:
        return None, "unknown_source"
    if (_norm(claim_text), _norm(quote)) not in associations:
        return None, "ungrounded_pair"
    confidence = item.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"  # the one deliberate fallback (ADR 001)
    return (
        ClaimMember(
            source_id=source_id,
            stance=item["stance"],
            claim_text=claim_text,
            supporting_quote=quote,
            confidence=confidence,
        ),
        "",
    )


# ----------------------------- pure logic ----------------------------------- #

def classify_cluster(members: list[ClaimMember]) -> Classification:
    """Label a cluster from its members' stances.

    - **contested**: a genuine *cross-source* disagreement — at least one source
      supports and a *different* source contradicts (≥2 distinct sources). One article
      citing conflicting studies is intra-source nuance, not contested.
    - **consensus**: ≥2 *distinct* sources agree (dedupe by source).
    - **outlier**: a single source's position.
    """
    supporters = {m.source_id for m in members if m.stance == "supports"}
    contradictors = {m.source_id for m in members if m.stance == "contradicts"}
    distinct = supporters | contradictors
    if supporters and contradictors and len(distinct) >= 2:
        return "contested"
    if len(distinct) >= 2:
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

def _parse_members(
    raw_members, catalogue: dict[str, set[tuple[str, str]]], rejections: Counter | None = None
) -> list[ClaimMember]:
    """Keep only members grounded in `catalogue`; count why the rest were dropped.

    Duplicate valid members are kept: `classify_cluster` dedupes by source, so a
    duplicate cannot manufacture corroboration.
    """
    members: list[ClaimMember] = []
    if not isinstance(raw_members, list):
        if rejections is not None:
            rejections["malformed_member_collection"] += 1
        return members
    for item in raw_members:
        member, reason = _validate_member(item, catalogue)
        if member is None:
            if rejections is not None:
                rejections[reason] += 1
            continue
        members.append(member)
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
        raw = await call_model(ADVERSARIAL_SYSTEM, _adversarial_prompt(topic, statement, members), MODEL_ADVERSARIAL)
    except Exception as exc:  # noqa: BLE001 — resilience: keep the naive stances
        # Members count + exception only: the statement is model text derived from sources.
        logger.warning("adversarial recheck failed for a %d-member cluster: %s", len(members), exc)
        return members

    ignored: Counter = Counter()
    if not isinstance(raw, dict):
        ignored["malformed_recheck_response"] += 1
        revised = []
    else:
        revised = raw.get("members", [])
        if not isinstance(revised, list):
            ignored["malformed_revision_collection"] += 1
            revised = []
    known = {m.source_id for m in members}
    proposed: dict[str, set[str]] = {}
    for item in revised:
        if not isinstance(item, dict):
            ignored["malformed_revision"] += 1
            continue
        source_id, stance = item.get("source_id"), item.get("stance")
        if not isinstance(source_id, str) or stance not in ("supports", "contradicts"):
            ignored["malformed_revision"] += 1
            continue
        if source_id not in known:
            ignored["unknown_source"] += 1  # one per revision entry, not per distinct id
            continue
        proposed.setdefault(source_id, set()).add(stance)

    # Revisions are keyed only by source id, so they are applied only when that
    # key identifies exactly one surviving member and the returned stances agree.
    per_source = Counter(m.source_id for m in members)
    out: list[ClaimMember] = []
    for member in members:
        stances = proposed.get(member.source_id)
        if not stances:
            out.append(member)  # unknown or missing revision: keep the original
            continue
        if per_source[member.source_id] != 1:
            ignored["ambiguous_original"] += 1
            out.append(member)
            continue
        if len(stances) != 1:
            ignored["conflicting_revisions"] += 1
            out.append(member)
            continue
        out.append(member.model_copy(update={"stance": next(iter(stances))}))
    if ignored:
        # Counts and reason codes only; never raw claim, quote or source text.
        logger.info("recheck revisions ignored: %s", dict(sorted(ignored.items())))
    return out


async def build_claim_graph(
    topic: str,
    claim_sets: list[SourceClaims],
    *,
    call_model=_real_call_model,
    adversarial: bool = True,
) -> tuple[list[ClaimCluster], list[Gap]]:
    """Cluster → ground members → (adversarial recheck) → classify.

    Raises ``ValueError`` on a response that cannot be trusted at all: not an
    object, a missing or non-list ``clusters``, or proposed clusters of which
    nothing survived grounding validation. An explicitly empty ``clusters`` list
    is a legitimate no-claims result; a list with some malformed entries keeps
    the usable ones.
    """
    raw = await call_model(CLUSTER_SYSTEM, _cluster_prompt(topic, claim_sets), MODEL_REASON)
    if not isinstance(raw, dict):
        raise ValueError(f"reasoning response was not a JSON object (got {type(raw).__name__})")
    if "clusters" not in raw:
        raise ValueError("reasoning response is missing the 'clusters' key")
    raw_clusters = raw["clusters"]
    if not isinstance(raw_clusters, list):
        raise ValueError(f"reasoning 'clusters' must be a list (got {type(raw_clusters).__name__})")
    llm_gaps = _parse_gaps(raw.get("gaps", []))

    catalogue = build_claim_catalogue(claim_sets)
    rejections: Counter = Counter()

    async def _finalize(index: int, raw_cluster: dict) -> ClaimCluster | None:
        if not isinstance(raw_cluster, dict):
            rejections["malformed_cluster"] += 1
            return None
        members = _parse_members(raw_cluster.get("members"), catalogue, rejections)
        if not members:
            logger.info("cluster %d dropped: no grounded members", index)
            return None
        statement = str(raw_cluster.get("statement", "")).strip() or "(unnamed cluster)"
        # A single-source cluster is always `outlier` regardless of stance, so the
        # recheck cannot change its classification — skip it (saves a model call).
        # The member keeps its naive stance; that is a deliberate choice, not a no-op.
        if adversarial and len({m.source_id for m in members}) >= 2:
            members = await _adversarial_recheck(topic, statement, members, call_model)
        return ClaimCluster(
            id=f"c{index + 1}",
            statement=statement,
            classification=classify_cluster(members),
            members=members,
        )

    finalized = await asyncio.gather(*(_finalize(i, rc) for i, rc in enumerate(raw_clusters)))
    clusters = [c for c in finalized if c is not None]
    if rejections:
        # Counts and reason codes only — never raw claim or quote text.
        logger.warning(
            "grounding rejected %d proposed member(s)/cluster(s): %s",
            sum(rejections.values()),
            dict(sorted(rejections.items())),
        )
    if raw_clusters and not clusters:
        raise ValueError(
            f"reasoning proposed {len(raw_clusters)} cluster(s) but no member was grounded in the "
            f"extracted claims (rejections: {dict(sorted(rejections.items()))})"
        )
    gaps = llm_gaps + derive_gaps(clusters)
    return clusters, gaps
