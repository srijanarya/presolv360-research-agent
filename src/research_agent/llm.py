"""Thin model layer over the Claude Agent SDK.

`complete()` is the only place that touches the network/LLM — it's dependency-
injected into `call_model` and the stages so everything above it is tested with
fakes (ADR-8). `call_model` adds JSON parsing + one retry on malformed output,
which is the single most common real-world LLM failure mode.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

# Exact model ids confirmed against the running session (E1).
MODEL_REASON = "claude-opus-4-8"     # cross-source judgment + synthesis (the hard part)
MODEL_EXTRACT = "claude-sonnet-4-6"  # fast, parallel per-source extraction

CompleteFn = Callable[[str, str, str], Awaitable[str]]

_JSON_REMINDER = "\n\nReturn ONLY the JSON value — no preamble, no explanation, no code fences."


class ModelJSONError(Exception):
    """The model failed to return parseable JSON after a retry."""


def extract_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating code fences and surrounding prose.

    Raises ``ValueError`` (``json.JSONDecodeError`` is a subclass) if nothing parses.
    """
    s = text.strip()

    # Strip a ```json ... ``` or ``` ... ``` fence if present.
    if s.startswith("```"):
        s = s[3:]
        if s[:4].lower() == "json":
            s = s[4:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Last resort: grab the outermost {...} or [...] span and parse that.
    start = min((i for i in (s.find("{"), s.find("[")) if i != -1), default=-1)
    end = max(s.rfind("}"), s.rfind("]"))
    if start != -1 and end > start:
        return json.loads(s[start : end + 1])  # raises ValueError if still bad

    raise ValueError(f"no JSON found in model output: {text[:120]!r}")


async def complete(system: str, prompt: str, model: str) -> str:
    """Single-turn, tool-free model call on the logged-in Claude Code session.

    No API key needed on the Max plan (ADR-2). `setting_sources=[]` keeps the call
    clean of the user's local hooks / CLAUDE.md / output style.
    """
    options = ClaudeAgentOptions(
        system_prompt=system,
        model=model,
        max_turns=1,
        allowed_tools=[],
        setting_sources=[],
    )
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
    return "".join(chunks)


async def call_model(
    system: str,
    prompt: str,
    model: str,
    *,
    complete: CompleteFn = complete,
) -> Any:
    """Call the model and return parsed JSON, retrying once with a reminder.

    Two attempts total. Raises ``ModelJSONError`` if both fail to parse.
    """
    last_error: Exception | None = None
    for attempt in range(2):
        ask = prompt if attempt == 0 else prompt + _JSON_REMINDER
        raw = await complete(system, ask, model)
        try:
            return extract_json(raw)
        except ValueError as exc:
            last_error = exc
    raise ModelJSONError("model did not return valid JSON after a retry") from last_error
