"""E1.S4 — `extract_json` parsing + `call_model` JSON retry-once.

The real model call (`complete`) is the injected boundary; here we drive it with
fakes so no network/LLM is touched.
"""

from __future__ import annotations

import pytest

from research_agent.llm import ModelJSONError, call_model, extract_json


def test_extract_json_strips_code_fences():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_strips_bare_fences():
    assert extract_json('```\n[1, 2, 3]\n```') == [1, 2, 3]


def test_extract_json_parses_bare_object():
    assert extract_json('{"x": [1, 2, 3]}') == {"x": [1, 2, 3]}


def test_extract_json_recovers_object_amid_prose():
    assert extract_json('Sure! Here you go:\n{"ok": true}\nHope that helps.') == {"ok": True}


def test_extract_json_raises_on_junk():
    with pytest.raises(ValueError):
        extract_json("not json at all")


async def test_call_model_retries_once_on_bad_json():
    calls: list[str] = []

    async def fake(system: str, prompt: str, model: str) -> str:
        calls.append(prompt)
        return "garbage{not json" if len(calls) == 1 else '{"ok": 1}'

    out = await call_model("sys", "extract claims", "m", complete=fake)
    assert out == {"ok": 1}
    assert len(calls) == 2  # initial + one retry


async def test_call_model_raises_after_second_bad_json():
    calls: list[int] = []

    async def fake(system: str, prompt: str, model: str) -> str:
        calls.append(1)
        return "still not json"

    with pytest.raises(ModelJSONError):
        await call_model("sys", "extract claims", "m", complete=fake)
    assert len(calls) == 2  # exactly two attempts, then give up
