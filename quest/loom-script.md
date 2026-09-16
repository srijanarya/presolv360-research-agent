# Loom script — 4:30, four beats

Recorded by me, in my own voice. Timings are cues, not a read-aloud script.

## 0:00–1:00 — the problem, and the evidence it is real

Screen: `extract.py` `_parse_claims`, then `reason.py` `_parse_members` at the baseline.

"Stage two is strict. Every claim must carry a quote that appears verbatim in its source, and anything else is dropped. Stage three then asked a model to cluster those claims, and accepted whatever came back. Any source id, any claim text, any quote.

So the guarantee stopped at the stage boundary. I measured it before changing anything: four invalid members offered, four retained. An unknown source, a quote belonging to a different source, and a fabricated quote. The brief still rendered, and the fake citation looked exactly like a real one. That is the part that bothered me. This is not a crash you notice, it is a number you trust."

## 1:00–2:15 — what I changed, and what I chose not to

Screen: the diff, then `_validate_member`.

"One module changed, one hundred seventy-one lines added and thirty removed. I build a catalogue of the associations extraction actually produced, and a member is accepted only when the whole triple matches: source id exactly, claim text and quote completely equal after the same normalization extraction already uses. I import that normalizer rather than rewriting it, so the two cannot drift apart.

The decision I want to flag is the cheaper option that was rejected: checking the quote alone. The measurement rules it out. A real quote arrived under opposite claim text, and a quote-only check waves it through. So identity is the whole association.

I also chose not to repair bad members. Repair means guessing what the model meant, and guessing is what caused this."

## 2:15–3:15 — verification a stranger can run

Screen: `make check` running to completion, then the before and after table.

"One command. The test suite, then the measurement, then the publication check. A few seconds.

The before column is not a memory. The harness pulls `reason.py` out of the recorded baseline commit and runs the same fixtures against both versions, and it fails loudly if that history is missing. The fixture offers four invalid members, one more than the original three-member probe, and four retained becomes zero. The valid variant survives. The cluster relabels from consensus to outlier, because the label is now derived from what survived.

Every number carries a label. The model-call drop is a fixture proxy, not a production saving. Production latency and change-failure rate say unavailable, because this repository has no production traffic and I am not going to invent those."

## 3:15–4:30 — the review, my decisions, and the limits

Screen: `quest/review-log.md`.

"An independent GPT review caught something real. My directive said log a reason for every ignored stance revision, and I logged two of the four cases. Unknown and malformed revisions were dropped silently, so you could not tell a clean recheck from a discarded one. Fixed, with a test per reason code.

The re-review then went after my tests rather than my code, which is the more useful direction. Four findings I accepted, including that my golden fixtures were only used by the measurement script and not asserted anywhere. One I pushed back on, because a pre-existing test already covered it and the reviewer simply could not see it in what I sent.

Three limits I want said out loud. The free reviewers I planned never ran, and I have recorded that as incomplete rather than dressing it up; the second vendor came from a paid DeepSeek review that cost about three cents. A cluster's statement is still the model's own text and is not grounded. And three synthetic cases prove the hole is closed, not that it ever hurt anyone in production. What I can defend is narrower and better than what I could claim."
