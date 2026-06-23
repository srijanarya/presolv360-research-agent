"""E1.S2 — Agent-SDK auth smoke test (TDD exception: integration/auth).

Proves ``claude-agent-sdk``'s ``query()`` runs on the logged-in Claude Code (Max 20x)
session with **no** ``ANTHROPIC_API_KEY`` set. If this passes, ADR-2 holds: zero-key
model access on the subscription.

Run:  uv run python scripts/smoke.py
"""

from __future__ import annotations

import asyncio
import os

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

MODEL = "claude-sonnet-4-6"  # cheap model for the smoke test


async def main() -> None:
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"ANTHROPIC_API_KEY set? {has_key}  (want False — proving 20x-plan/session auth)")
    print(f"ANTHROPIC_BASE_URL = {os.environ.get('ANTHROPIC_BASE_URL', '<unset>')}")

    options = ClaudeAgentOptions(
        system_prompt="You are a terse echo. Reply with exactly the text the user asks for, nothing else.",
        model=MODEL,
        max_turns=1,
        allowed_tools=[],      # pure language call — no tools
        setting_sources=[],    # don't inherit user/project Claude Code settings (hooks, CLAUDE.md)
    )

    chunks: list[str] = []
    async for message in query(prompt="Reply with exactly: AUTH_OK", options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)

    reply = "".join(chunks).strip()
    print(f"model reply: {reply!r}")
    assert "AUTH_OK" in reply, f"unexpected reply (auth or API issue?): {reply!r}"
    print("SMOKE PASS — Agent SDK works on the logged-in session; no API key required.")


if __name__ == "__main__":
    asyncio.run(main())
