"""E8.S4 — the shipped sample inputs are well-formed (topic + 3–5 http URLs)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_INPUTS = Path(__file__).resolve().parents[1] / "inputs"


@pytest.mark.parametrize("name", ["ai-jobs.json", "legal-odr.json"])
def test_sample_input_parses_and_has_3_to_5_urls(name: str):
    data = json.loads((_INPUTS / name).read_text(encoding="utf-8"))
    assert data["topic"].strip()
    assert 3 <= len(data["urls"]) <= 5
    assert all(u.startswith("http") for u in data["urls"])
