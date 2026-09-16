# Live runs — the fixed code against real model output

Two end-to-end runs of `inputs/ai-jobs.json` at commit `bccc008` on 2026-09-16, live model calls, five sources fetched successfully both times. These are **two runs on one input**, not a production rate. Rerun with `uv run python quest/live-runs/diagnose.py inputs/ai-jobs.json out.json`; it costs model calls and needs model access.

| Run | Claims extracted | Members proposed | Accepted | Rejected | Sources with zero survivors | Final clusters |
|---|---|---|---|---|---|---|
| 1, plain CLI | 66 | 44 | 24 | 20 (45%) | one, `s4` | 14 |
| 2, instrumented | 66 | 64 | 59 | 5 (8%) | none | 21 |

Every rejection in both runs carried reason code `ungrounded_pair`. In run 2, where each rejection was classified, all five were the same shape: the quote was verbatim and matched the source, and the claim text had been rewritten by the clustering model. Run 1's rejections were not classified because the plain CLI logs counts only.

What this shows: the gate rejects real output, at a rate that varied from 8% to 45% between two runs of the same input, and in the classified run every loss was a paraphrased claim over a genuine quote. That is the recall cost ADR 001 names, now measured, and it is the case claim identifiers echoed by the model would remove.
