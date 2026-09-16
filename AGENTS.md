# Agent instructions

These are the rules that actually govern changes in this repository. They apply to any AI agent and to me.

## Scope of the current change

- Production code changes are limited to `src/research_agent/reason.py`.
- Tests, `scripts/`, `quest/`, `Makefile` and CI config may also change.
- Do not change: API schemas and response shapes, the extraction and reasoning prompts, `templates/`, `web/`, or the `Brief` contract in `models.py`.

## Non-negotiables

1. **Never invent provenance.** A claim, quote or source identifier that did not come from the extraction stage must not appear in a brief. Reformulating is fine; fabricating is not.
2. **Failures are loud.** Malformed model output raises with a descriptive message. Never silently substitute a default that makes bad output look valid. The existing confidence fallback to `medium` is the one deliberate exception, and it is documented in the ADR.
3. **No new runtime dependencies.** The standard library and what is already in `pyproject.toml` are enough.
4. **Tests run offline.** Every test injects a fake model. No test may make a network call or need credentials.
5. **Logs carry no source text.** Log counts, reason codes and validated identifiers or indices only.

## Verification

- `make check` is the single entrypoint: backend tests, the before-and-after measurement against the recorded baseline SHA, and the tracked-path exclusion check.
- A change is not done because an agent says tests should pass. It is done when `make check` has actually run and its output is in the record.
- Numbers must be labelled: measured, fixture-only proxy, or unavailable. Never present a fixture number as a production metric.

## Review responsibilities

- A human reviews the decision record, the diff and the measurements.
- AI reviewers cover style, coverage and defect hunting on a frozen snapshot.
- **Nothing merges on an AI review alone.** An unavailable review is incomplete; it never counts as approval.
- Model identity comes from host-recorded metadata, never from what a model says about itself.

## Never publish

`_bmad-output/` and any local `CLAUDE.md` are private notes. They are ignored, and they must never be force-added or quoted into tracked files.
