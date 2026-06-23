"""CLI entrypoint: `research-agent inputs/ai-jobs.json` → writes out/<run_id>/."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from research_agent.pipeline import run_pipeline
from research_agent.synthesize import write_brief


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _print_event(event: dict) -> None:
    kind = event["type"]
    if kind == "stage_started":
        print(f"  ▶ {event['stage']} …", flush=True)
    elif kind == "source_status":
        mark = "✓" if event["status"] == "ok" else "✗"
        print(f"      {mark} [{event['id']}] {event['status']:<11} {event['url']}", flush=True)
    elif kind == "stage_completed":
        extra = " ".join(f"{k}={v}" for k, v in event.items() if k not in ("type", "stage"))
        print(f"  ✔ {event['stage']} {extra}".rstrip(), flush=True)


async def _amain(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    topic, urls = data["topic"], data["urls"]
    if not (3 <= len(urls) <= 5):
        print(f"warning: brief expects 3–5 URLs, got {len(urls)} (continuing)", file=sys.stderr)

    print(f"Topic:   {topic}")
    print(f"Sources: {len(urls)}")
    print(f"Mode:    {'single-pass' if args.no_adversarial else 'adversarial cross-check'}\n")

    brief = await run_pipeline(
        topic, urls, adversarial=not args.no_adversarial, on_event=_print_event
    )

    paths = write_brief(brief, Path(args.out) / _run_id())
    counts = {"consensus": 0, "contested": 0, "outlier": 0}
    for cluster in brief.claim_clusters:
        counts[cluster.classification] += 1

    print(
        f"\nClaim Graph: {counts['consensus']} consensus · {counts['contested']} contested · "
        f"{counts['outlier']} outlier · {len(brief.gaps)} gaps"
    )
    print(f"Wrote:\n  {paths['md']}\n  {paths['html']}\n  {paths['json']}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="research-agent",
        description="Cross-source research agent → consensus/contested/outlier Claim Graph brief.",
    )
    parser.add_argument("input", help="input JSON file: {\"topic\": ..., \"urls\": [...]}")
    parser.add_argument("--out", default="out", help="output directory (default: out/)")
    parser.add_argument(
        "--no-adversarial", action="store_true", help="disable the adversarial cross-check (faster)"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_amain(args)))
