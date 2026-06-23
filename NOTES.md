# NOTES

## Approach

A **code-orchestrated pipeline**: my Python owns the decomposition and the model is invoked
only at the language steps — four visible, inspectable, individually-tested stages:

```
fetch ──▶ extract ──▶ reason ──▶ synthesize
(ladder) (claims/src) (Claim Graph) (brief.json → md/html)
```

The output of record is **`brief.json`** (MD, HTML, and the web UI are projections of it). The
core idea is the **Claim Graph**: claims are clustered across sources and each cluster is labelled
**consensus** (≥2 sources agree) / **contested** (sources disagree) / **outlier** (one source),
plus **gaps** (sub-topics no source covers) — every claim cites a verbatim source quote. Runs on a
Claude Max subscription via `claude-agent-sdk` with **no API key**.

## Key judgment calls (the brief left these to me)

- **"A claim" = one atomic, checkable assertion** (Claimify-style decomposition), not a sentence
  or paragraph. Every `supporting_quote` is verified to be a **verbatim substring** of its source;
  hallucinated quotes are dropped before they reach the brief.
- **The hard part is reasoning, so I made it the testable core.** The LLM clusters claims and
  assigns each source a *stance*; a **pure function** (`classify_cluster`) then derives the
  consensus/contested/outlier label — deterministic and unit-tested. A per-cluster **adversarial
  dual-perspective** pass argues for/against and corrects stances, so a contradiction the naive
  pass merged into "agreement" surfaces as *contested*. (No tool I surveyed adjudicates conflicts;
  this is the differentiator.)
- **Graceful failure is first-class.** Any source can fail (paywall/JS/timeout/empty/error); it
  gets a status, is excluded from extraction but still shown, and the run completes on whatever
  succeeded. Bad model JSON → one re-ask, then drop that source. The run never crashes.

## Scope decision — I deliberately went beyond the suggested ~2h

This is a **considered choice, not a misread of scope.** The analyst deliverable (CLI →
`brief.{json,md,html}`) is complete and tested on its own. On top of the *same one JSON contract* I
added a FastAPI + SSE backend and a React SPA that renders the Claim Graph with live per-stage
progress — because "the kind of thing an analyst would open and use" is more convincing as a real
product, and it shows the AI-native build workflow end to end. Nothing is half-done: every layer is
a thin projection of the tested core, so if you only run the CLI you still get the full result.

## Tradeoffs I made for time / reliability

- **Adversarial recheck runs on Sonnet, not Opus, and skips single-source clusters.** Early runs
  fanned out one *Opus* call per cluster → ~15 min. The recheck is a narrow per-cluster task, so I
  moved it to Sonnet (the hard *global* clustering stays Opus) and skip clusters that can't change
  label (one source is always `outlier`). Runtime dropped to ~1–2 min.
- **Extraction caps ~8–15 claims/source** — keeps responses short (more reliable JSON) and the
  brief focused on substance.
- **Bounded model concurrency + retry-with-backoff.** Running nested `claude` subprocesses under
  load intermittently returns a spurious error result; I root-caused it in the SDK source and
  added a concurrency cap + transient retry rather than guessing.
- **No DB, no auth, in-memory run registry**; Playwright JS-fallback is wired but the 5 sample
  URLs didn't need it (all fetched cleanly via httpx + trafilatura).

## What I'd do differently in production

- **Eval-gate the Claim Graph** on a labelled fixture before trusting its labels — don't trust the
  agent's own classification until it's measured against ground truth.
- **Source-credibility weighting** (for the ODR sample: weight by court hierarchy / regulator
  precedence; a Constitution-Bench ruling > a practitioner blog).
- **Embedding-based claim dedup** for clustering at scale; **cache** fetched+extracted sources;
  stream extraction; a real per-account rate-limit queue instead of best-effort retry.
- **Harden the API for non-local deployment**: auth, rate-limiting, and run eviction (it's an
  in-memory localhost demo today), plus full SSRF protection — the fetch guard already blocks
  non-http(s) schemes and private/loopback/link-local IPs, but production also needs DNS-resolution
  checks and redirect re-validation.
- **PDF / court-document ingestion** and a "is this authority still current / not overruled?"
  checker (the natural next step for the legal domain).
