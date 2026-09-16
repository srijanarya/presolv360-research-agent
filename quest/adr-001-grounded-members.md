# ADR 001 — validate reasoning members against extracted claims

**Status:** accepted, implemented on `quest/p2-grounded-members`.
**Date:** 2026-09-16.

## Context

`extract.py` guarantees that every claim's `supporting_quote` is a verbatim substring of its source, and drops the claim otherwise. `reason.py` then re-asks a model to cluster those claims, and `_parse_members` accepts the result unchecked: any source identifier, any claim text, any quote. The extraction guarantee stops at the stage boundary.

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
| Check the quote only, against the union of that source's quotes | Cheaper, and it was my first instinct. It fails the measured case where a genuine quote arrives under opposite claim text, so the citation still lies. Rejected on evidence. |
| Substring containment, reusing `quote_in_source` | Already in the codebase, so tempting. Containment accepts a truncated quote that changes meaning, for example dropping a negation or a qualifier. Equality is the stricter contract and is what the catalogue can actually guarantee. |
| Aggressive canonicalization, such as smart quotes, dashes and punctuation | It would accept more well-meaning model output. It also cannot coexist with a promise that valid output stays byte-identical, and that normalization lives on a separate branch that is not in this baseline. Out of scope here. |
| Introduce claim identifiers and have the model echo them | The clean long-term fix. It changes the model protocol and the prompts, which this change forbids, and it would make the diff much harder to review. Recorded as the natural follow-up. |
| Repair invalid members instead of dropping them | Repair means guessing which claim the model meant. Guessing is what produced the defect. |
| Validate in `pipeline.py` instead | Keeps `reason.py` untouched but leaves the stage exporting unsound data, and every other caller of `build_claim_graph` unprotected. |

## Consequences

**Good.** The extraction guarantee now holds end to end. Labels and gaps derive from grounded members only. Malformed output stops the run instead of producing a confident brief. The change is one module, with a pure catalogue and pure validation that are cheap to unit test.

**Costs, stated plainly.** Strict equality drops members a human might accept, for example a lightly reworded quote, so recall drops in exchange for trustworthiness. A run can now fail where it previously produced a brief, which is deliberate: an SSE `error` beats a plausible fabrication. The catalogue holds normalized copies of claims and quotes in memory for the duration of the stage, which is small next to the source text already held.

**Reversibility.** The change is additive within one module and is reverted by dropping the filter call. The fixtures and measurements stay valid either way, so a revert can be evaluated against the same numbers.

**What this does not do.** It checks provenance, not truth. A correctly grounded claim can still be wrong, and a source can still be wrong. Nothing here judges that.
