# Intent — what I chose to fix, and why

**Quest:** make AI-assisted code easier to trust and change.
**Repository:** this one, my own public solution to a June 2026 take-home. Baseline for this work: tag `quest-baseline` (`f58b327`), which is public `main` `476522b` plus pre-Accept housekeeping.

## The problem I chose

**Stage 3 reasoning accepts ungrounded members.** `build_claim_graph` asks a model to cluster extracted claims across sources. `_parse_members` then accepts whatever the model returns: any `source_id` string, any `claim_text`, any `supporting_quote`. Nothing checks those against the claims that extraction actually produced.

Stage 2 is strict about provenance. `extract.py` discards any claim whose `supporting_quote` is not a verbatim substring of the source. Stage 3 then throws that guarantee away, because a quote can arrive attached to a different source, to different claim text, or be invented outright, and it still reaches `brief.json` and every view built on it.

This is a trust defect, not a crash. The brief still renders. A reader sees a citation that looks exactly like a verified one.

### Evidence

Measured before any change, by a stage-level probe against the baseline with the adversarial pass disabled:

| Observation | Measured |
|---|---|
| Invalid members supplied, being an unknown source, a quote belonging to another source, and a fabricated quote | 3 |
| Invalid members **retained** in the output | **3 of 3** |
| Valid member whose quote differs only in whitespace and case, retained | 1 of 1 |
| Mixed cluster's classification | `consensus`, where only the valid single-source member should survive and make it `outlier` |
| Opposite claim text attached to a genuine quote, retained | 1 of 1 |
| Model returning `{"clusters": null}` | `TypeError` |

Honest limits. Three synthetic cases prove the hole exists and is reachable. They do not establish a production failure rate. `main` shows repeated work on reasoning trust, in `8edb3da`, and stance and normalization fixes exist on a separate `r2-review-fixes` branch, in `76fd4af`, which is not part of this baseline. **Recurrence of this exact bug is unproven, and I am not claiming it.**

## What I compared

Impact, maintenance effort and operating cost below are **subjective planning scores**, not measurements.

| # | Problem | Category | Evidence today | Impact / Effort / Cost |
|---|---|---|---|---|
| P1 | The adversarial recheck makes one model call per multi-source cluster | expensive repeated work | `main` already skips single-source clusters, in `e3f07d7`, and tuned the model, in `1ea46d1`. No new cost or latency benchmark was run. | 3 / 3 / 5 |
| **P2, chosen** | Reasoning accepts ungrounded members | missing validation, trust | Measured above, 3 of 3 retained | 5 / 3 / 1 |
| P3 | The in-memory run registry never evicts | expensive repeated work | A pre-existing stress note. Its load harness is untracked, and the garbage-collection claim is a hypothesis. | 4 / 2 / 4 |
| P4 | URL safety is enforced at fetch time, not at `POST /api/research` | missing validation | The fetch-layer guard exists. The API rejection baseline is not measured. | 3 / 2 / 2 |

**Why P2 wins.** It is the cheapest to verify offline and the most expensive to get wrong. A wrong number in a brief is worse than a slow brief, because the reader cannot see it. P1 and P3 cost money and memory, which an operator notices. P2 costs credibility silently. P2 also sits in the component this codebase calls its own hard part, so a guard there is where a reviewer looks first.

**Why not the others, now.** P1 and P3 are efficiency work whose benefit I cannot currently measure without a benchmark I would have to build. P4 is real but small, and I use it as the handoff exercise instead, so someone else can execute it from my notes.

## Non-goals

- No P1, P3 or P4 implementation in this change.
- No claim identifiers and no change to the model protocol.
- No extraction prompt or reasoning prompt changes.
- No API schema, response shape or web interface changes.
- No authentication, rate limiting or PDF ingestion.
- No smart-quote or typographic normalization; that lives on a separate branch and is not in this baseline.
- No attempt to judge whether a grounded claim is *true*. This change checks provenance only.

## What "done" means

Invalid members reach 0 of 3 while the valid normalized member stays at 1 of 1, classifications and gaps derive from survivors, malformed model output fails loudly instead of silently producing a brief, and one `make check` regenerates every number from the recorded baseline.
