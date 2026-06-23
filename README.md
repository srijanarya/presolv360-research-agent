# Cross-Source Research Agent — the Claim Graph

Give it a **topic + 3–5 source URLs**. It fetches and parses the (messy, real-world) pages,
extracts each source's atomic claims, **reasons across the sources**, and produces a structured
brief that distinguishes:

- **Consensus** — multiple sources agree
- **Contested** — sources disagree (surfaced explicitly, with both sides cited)
- **Outlier** — only one source asserts it
- **Gaps** — sub-topics no source covers

…every claim backed by a **verbatim quote** from its source. The agent decomposes the problem into
four visible stages (it does **not** one-shot a giant prompt), handles source failures gracefully,
and ships as both a CLI and a small web app.

```
fetch ──▶ extract ──▶ reason ──▶ synthesize
ladder    claims/src   Claim Graph   brief.json → .md / .html / web UI
```

## Requirements

- [`uv`](https://docs.astral.sh/uv/) (manages Python 3.11 for you)
- **Model access** — by default, a logged-in **Claude Code** session (e.g. a Claude Max
  subscription): **no API key needed**. Run `claude` once to log in. *(Reviewer without a Claude
  Code login? See [Auth](#auth-no-key-needed-on-the-max-plan).)*
- For the web UI only: Node 18+ / npm.

## Quickstart — CLI

```bash
uv sync                                   # install deps into a pinned venv
uv run playwright install chromium        # optional: JS/paywall fallback rung
uv run research-agent inputs/ai-jobs.json # run the agent
```

Outputs land in `out/<timestamp>/`:

- `brief.md` — the analyst deliverable (consensus / contested / outlier / gaps + a source table)
- `brief.html` — a standalone, self-contained styled report
- `brief.json` — the structured contract (every claim with its citation + classification)

Two sample inputs are included: [`inputs/ai-jobs.json`](inputs/ai-jobs.json) (the assignment's
topic + 5 URLs) and [`inputs/legal-odr.json`](inputs/legal-odr.json) (a legal-authority example).
Flags: `--no-adversarial` (faster, single-pass), `--out DIR`.

## Quickstart — web app (live progress + Claim Graph explorer)

```bash
# 1. build the SPA (served by the backend)
cd web && npm install && npm run build && cd ..

# 2. run the API + UI
uv run uvicorn research_agent.api:app --port 8000
# open http://localhost:8000  → enter a topic + URLs → watch the stages stream live
```

For frontend hot-reload during development: `cd web && npm run dev` (Vite proxies `/api` → `:8000`).

## How it works

1. **Fetch** (`fetch.py`, no LLM) — a fallback ladder per URL: `httpx` + `trafilatura` (clean
   main-text) → `readability` → headless **Playwright**. Each source returns a status
   (`ok | paywalled | js_required | timeout | empty | error`); a failure is reported, never fatal.
2. **Extract** (`extract.py`, Sonnet, parallel) — one scoped call per source decomposes it into
   atomic claims, each with a **verbatim** `supporting_quote` (unquotable claims are dropped). The
   prompt treats source text as untrusted data (prompt-injection-aware).
3. **Reason** (`reason.py`, Opus + Sonnet) — clusters equivalent claims across sources and assigns
   each source a stance; an **adversarial dual-perspective** recheck argues for/against each cluster
   and corrects stances; a **pure function** then labels each cluster consensus/contested/outlier
   and derives gaps.
4. **Synthesize** (`synthesize.py`) — renders the one `brief.json` to Markdown, a standalone HTML
   report, and (via the API) the web UI.

The model boundary (`call_model`) and the fetch boundary are dependency-injected, so the whole
pipeline is tested offline with fakes.

## Auth (no key needed on the Max plan)

`claude-agent-sdk` runs on your logged-in Claude Code session — **zero API keys**. If you don't have
a Claude Code login, set a fallback (no code change needed); see [`.env.example`](.env.example):

- `ANTHROPIC_API_KEY=sk-ant-…`, **or**
- `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` for an Anthropic-compatible endpoint (e.g. Z.AI/GLM).

## Tests

```bash
uv run pytest               # backend: pipeline logic, fetch, reasoning, rendering, API
cd web && npm run test      # frontend: component rendering against a brief fixture
```

The deterministic core — the consensus/contested/outlier classifier — is fully unit-tested; LLM
stages are tested by injecting recorded outputs (we assert schema-validity + invariants, never exact
model text).

## Layout

```
src/research_agent/  models · llm · fetch · extract · reason · synthesize · pipeline · api · cli
templates/           brief.html.j2          web/         Vite + React + TS + Tailwind SPA
inputs/              sample topics + URLs   tests/        pytest (offline, injected fakes)
scripts/smoke.py     Agent-SDK auth check   prompts.md    production prompts + build workflow
NOTES.md             approach · scope · tradeoffs
```

See [`NOTES.md`](NOTES.md) for the approach, the explicit scope decision, and tradeoffs.
