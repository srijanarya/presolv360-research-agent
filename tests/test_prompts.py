"""E8.S2 — prompts.md stays in sync with the live system prompts (guards drift).

Each signature phrase must appear BOTH in the running constant AND in prompts.md,
so editing a prompt without updating the doc (or vice-versa) fails the build.
"""

from __future__ import annotations

from pathlib import Path

from research_agent.extract import EXTRACTION_SYSTEM
from research_agent.reason import ADVERSARIAL_SYSTEM, CLUSTER_SYSTEM

_PROMPTS_MD = Path(__file__).resolve().parents[1] / "prompts.md"

_SIGNATURES = [
    (EXTRACTION_SYSTEM, "untrusted DATA to analyse"),
    (CLUSTER_SYSTEM, "Cluster claims that assert the SAME thing"),
    (ADVERSARIAL_SYSTEM, "stress-testing one claim cluster"),
]


def test_prompts_md_mirrors_live_prompts():
    doc = _PROMPTS_MD.read_text(encoding="utf-8")
    for constant, signature in _SIGNATURES:
        assert signature in constant, f"signature drifted out of the live prompt: {signature!r}"
        assert signature in doc, f"prompts.md is missing the live prompt signature: {signature!r}"
