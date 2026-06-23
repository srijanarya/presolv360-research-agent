"""Stage 4 — synthesis. Render a `Brief` into the analyst-facing views.

`brief.json` is the source of record; Markdown and HTML are pure projections of it
(ADR-3). Every claim carries its source citation; failed sources are shown, not
hidden (the graceful-failure story reaches every view).
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from research_agent.models import Brief, ClaimCluster, Gap, Meta, Source, SourceDoc

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

# Contested first — the disagreement a blended summary hides is the product's reason to exist.
_ORDER = ("contested", "consensus", "outlier")
_TITLES = {
    "consensus": "Consensus — multiple sources agree",
    "contested": "Contested — sources disagree",
    "outlier": "Outlier — single-source claims",
}


def derive_meta(sources: list[Source], *, model_reason: str = "", model_extract: str = "") -> Meta:
    ok = sum(1 for s in sources if s.status == "ok")
    return Meta(
        sources_ok=ok,
        sources_failed=len(sources) - ok,
        model_reason=model_reason,
        model_extract=model_extract,
    )


def _group(clusters: list[ClaimCluster]) -> dict[str, list[ClaimCluster]]:
    groups: dict[str, list[ClaimCluster]] = {"consensus": [], "contested": [], "outlier": []}
    for cluster in clusters:
        groups[cluster.classification].append(cluster)
    return groups


def assemble_brief(
    topic: str,
    generated_at: str,
    docs: list[SourceDoc],
    clusters: list[ClaimCluster],
    gaps: list[Gap],
    *,
    model_reason: str,
    model_extract: str,
) -> Brief:
    sources = [d.to_source() for d in docs]
    return Brief(
        topic=topic,
        generated_at=generated_at,
        sources=sources,
        claim_clusters=clusters,
        gaps=gaps,
        meta=derive_meta(sources, model_reason=model_reason, model_extract=model_extract),
    )


def render_markdown(brief: Brief) -> str:
    m = brief.meta
    total = m.sources_ok + m.sources_failed
    lines = [
        f"# Research Brief: {brief.topic}",
        "",
        f"_Generated {brief.generated_at} · {m.sources_ok}/{total} sources fetched · "
        f"reasoning `{m.model_reason}`, extraction `{m.model_extract}`_",
        "",
    ]
    groups = _group(brief.claim_clusters)
    for key in _ORDER:
        clusters = groups[key]
        lines.append(f"## {_TITLES[key]} ({len(clusters)})")
        lines.append("")
        if not clusters:
            lines.append("_None._")
            lines.append("")
            continue
        for cluster in clusters:
            lines.append(f"### {cluster.statement}")
            for mem in cluster.members:
                lines.append(
                    f'- [{mem.source_id}] **{mem.stance}** — {mem.claim_text} · '
                    f'"{mem.supporting_quote}" _({mem.confidence})_'
                )
            lines.append("")

    lines.append(f"## Gaps ({len(brief.gaps)})")
    lines.append("")
    if brief.gaps:
        for gap in brief.gaps:
            lines.append(f"- **{gap.description}** — {gap.rationale}")
    else:
        lines.append("_None identified._")
    lines.append("")

    lines.append("## Sources")
    lines.append("")
    lines.append("| id | status | method | title | url |")
    lines.append("|----|--------|--------|-------|-----|")
    for s in brief.sources:
        lines.append(f"| {s.id} | {s.status} | {s.fetch_method or '—'} | {s.title or '—'} | {s.url} |")
    lines.append("")
    return "\n".join(lines)


def render_html(brief: Brief) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template("brief.html.j2")
    return template.render(brief=brief, groups=_group(brief.claim_clusters), order=_ORDER, titles=_TITLES)


def write_brief(brief: Brief, out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out / "brief.json",
        "md": out / "brief.md",
        "html": out / "brief.html",
    }
    paths["json"].write_text(brief.model_dump_json(indent=2), encoding="utf-8")
    paths["md"].write_text(render_markdown(brief), encoding="utf-8")
    paths["html"].write_text(render_html(brief), encoding="utf-8")
    return paths
