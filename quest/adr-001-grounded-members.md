# ADR 001 — validate reasoning members against extracted claims

**Status:** accepted, implemented on `quest/p2-grounded-members`.
**Date:** 2026-09-16.

## Context

`extract.py` keeps a claim only when its `supporting_quote` appears in the source once both are whitespace-normalized and lowercased (`quote_in_source`), and drops the claim otherwise. `reason.py` then re-asks a model to cluster those claims, and `_parse_members` accepts the result unchecked: any source identifier, any claim text, any quote. The extraction guarantee stops at the stage boundary.

Measured on the baseline: 3 of 3 invalid members retained, and a genuine quote carrying opposite claim text also retained. The brief renders normally, so a fabricated citation is indistinguishable from a verified one.

## Decision

Validate every proposed member against a catalogue of the associations extraction actually produced, and drop the ones that do not match.

1. **Identity is the whole association**, `(source_id, claim_text, supporting_quote)` together, not a quote in a pool of quotes. A genuine quote paired with rewritten or opposite claim text is rejected.
2. **Source identifiers match exactly.** Claim text and quotes are compared after the extraction stage's whitespace normalization followed by lowercase, and must be **completely equal**.
3. **Normalization is imported from the extraction stage**, not reimplemented, so the comparison cannot drift from the behaviour that produced the claims.
4. **Validation runs before** adversarial prompting, recheck eligibility, classification and gap derivation. Labels are then derived from survivors, and empty clusters disappear.
5. **Malformed output fails loudly.** A non-object response, a missing or non-list `clusters`, or a non-empty cluster list with no valid survivor raises `ValueError`. An explicitly empty list is a legitimate no-claims result.
6. **Stance revisions are applied only when unambiguous:** one surviving member for that source, and agreeing valid revisions.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Check the quote only, against the union of that source's quotes | Cheaper. It fails the measured case where a genuine quote arrives under opposite claim text, so the citation still lies. Rejected on evidence. |
| Substring containment, reusing `quote_in_source` | Already in the codebase, so tempting. Containment accepts a truncated quote that changes meaning, for example dropping a negation or a qualifier. Equality is the stricter contract and is what the catalogue can actually guarantee. |
| Aggressive canonicalization, such as smart quotes, dashes and punctuation | It would accept more well-meaning model output. It would also change which members are accepted, which is the contract this record sets; an accepted member keeps its original text under any comparison rule, so the retained output is not what changes. That normalization also lives on a separate branch that is not in this baseline. Out of scope here. |
| Introduce claim identifiers and have the model echo them | The clean long-term fix. It changes the model protocol and the prompts, which this change forbids, and it would make the diff much harder to review. Recorded as the natural follow-up. |
| Repair invalid members instead of dropping them | Repair means guessing which claim the model meant. Guessing is what produced the defect. |
| Validate in `pipeline.py` instead | Keeps `reason.py` untouched but leaves the stage exporting unsound data, and every other caller of `build_claim_graph` unprotected. |

## Consequences

**Good.** The extraction guarantee now carries into the reasoning stage for accepted member associations: a member reaches the brief only with a `(source_id, claim_text, supporting_quote)` triple that extraction produced. It does not extend to a cluster's `statement`, which is the model's own text, or to the gaps the model proposes. Labels and the derived gaps come from grounded members only; model-proposed gaps are parsed as returned and are not verified. Malformed output stops the run instead of producing a confident brief. The change is one module, with a pure catalogue and pure validation that are cheap to unit test.

**Costs, stated plainly.** Strict equality drops members a human might accept, for example a lightly reworded quote, so recall drops in exchange for trustworthiness. Live runs on one input measured the price as counts, not a rate: attempt 1 rejected 20 of 44 (45%) proposed members; attempt 2 rejected 5 of 64 (8%) proposed members; attempt 3 rejected 20 of 66 (30%) proposed members with distinct association coverage 46 of 66 (70%). Attempts 4 and 5 failed on model-call errors before producing counts and are recorded as failed, not replaced. See `quest/live-runs/README.md`. Rejected-of-proposed and distinct association coverage are reported separately; neither is a semantic recall rate, and a rewritten claim is not assumed to mean the same thing as the extracted one. A run can now fail where it previously produced a brief, which is deliberate: an SSE `error` beats a plausible fabrication. The catalogue holds normalized copies of claims and quotes in memory for the duration of the stage, which is small next to the source text already held.

**Reversibility.** The change is additive within one module and is reverted by dropping the filter call. The fixtures and measurements stay valid either way, so a revert can be evaluated against the same numbers.

**What this does not do.** It checks provenance, not truth. A correctly grounded claim can still be wrong, and a source can still be wrong. Nothing here judges that.

One known gap is in the module itself and is left unresolved for this submission: when the adversarial recheck call raises, `_adversarial_recheck` logs the exception text. A provider error can echo the prompt, and the prompt carries claim and quote text, so that line can put source text in the logs, against criterion 15 and AGENTS.md rule 5. It was found by an independent assessment after the reviewed revision and the walkthrough were frozen; production code stays at `9c2cc38`, so the fix (log a fixed reason code and the member count) is recorded as the first follow-up, not applied.

Two further gaps are deliberate, and both were named by the independent review of brief `756a0015`:

- **A cluster's `statement` is not grounded.** It is the model's own neutral summary of the cluster. Grounded members can therefore sit under a statement that overstates or drifts from what those sources actually said, and the cluster is then classified and presented against that statement. Checking it needs semantic comparison, not the whitespace- and case-normalized association matching this change uses.
- **Model-surfaced gaps are accepted as written.** Nothing verifies that a named sub-topic is genuinely unaddressed by every source. `derive_gaps`, the part that is computed from the graph rather than asserted by the model, is unaffected.

Both are out of scope here and are recorded as the next things worth fixing, not as solved.

One more consequence, raised by the DeepSeek review: because associations are **unioned** when an input source id repeats, two genuinely different documents that arrived under the same id would widen each other's accepted set. Criterion 1 mandates the union, and the pipeline assigns ids itself, so this is a design consequence rather than a defect, but it is the one place where "the association extraction produced" is weaker than it sounds.
