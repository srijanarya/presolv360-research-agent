"""Cross-source reasoning — the Claim Graph.

The deterministic heart is `classify_cluster`: given the labeled members of a
cluster (each a source's stance on the cluster's statement), decide whether the
cluster is consensus / contested / outlier. Keeping this a *pure function* is what
makes the hardest part of the system unit-testable (architecture.md §5, E4.S2).

The LLM-driven clustering + adversarial cross-check (E4.S1/S5) build on top of
this and land here in E4.
"""

from __future__ import annotations

from research_agent.models import ClaimMember, Classification


def classify_cluster(members: list[ClaimMember]) -> Classification:
    """Label a cluster from its members' stances.

    - **contested**: at least one source supports and at least one contradicts
      (a genuine cross-source disagreement — surfaced liberally; it's the point).
    - **consensus**: ≥2 *distinct* sources agree (dedupe by source — one voice
      repeating itself is not agreement).
    - **outlier**: a single source's position.
    """
    stances = {m.stance for m in members}
    if "supports" in stances and "contradicts" in stances:
        return "contested"
    if len({m.source_id for m in members}) >= 2:
        return "consensus"
    return "outlier"
