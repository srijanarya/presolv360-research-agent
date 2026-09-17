"""Criterion 14, CLI half: a reasoning failure escapes `main()` and no brief directory is written.

The SSE half is covered in tests/test_api.py. No production code is changed here: the CLI
imports `run_pipeline` into its own namespace, so the failure is injected at that seam.
"""
from __future__ import annotations

import json
import sys

import pytest

from research_agent import cli


def test_reasoning_failure_escapes_main_and_writes_no_output(tmp_path, monkeypatch):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps({"topic": "t", "urls": ["https://a.example", "https://b.example", "https://c.example"]}))
    out = tmp_path / "out"

    async def failing_pipeline(topic, urls, *, adversarial=True, on_event=None):
        raise ValueError("reasoning response is missing the 'clusters' key")

    monkeypatch.setattr(cli, "run_pipeline", failing_pipeline)
    monkeypatch.setattr(sys, "argv", ["research-agent", str(inp), "--out", str(out)])
    with pytest.raises(ValueError, match="missing the 'clusters' key"):
        cli.main()
    assert not out.exists(), "no brief directory may be created when reasoning fails"
