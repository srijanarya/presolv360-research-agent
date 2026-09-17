# Review receipts

Raw reviewer output and host receipts behind `quest/review-log.md`, so a reader can check what each reviewer actually said against how the log characterizes it. Model identities come from host metadata (the CLI invocation or the API receipt), never from a model's own claim. Local paths are replaced with `<home>`; nothing else is edited. Numbering follows the review log.

| File | Review | Revision seen | What it is |
|---|---|---|---|
| `01b-free-lanes-attempt-incomplete.json` | planned free pair, first attempt | `92c59b5` | the helper's own record: `qwen38` timed out, `v4flash0731` missed its probe, `nemotron3ultra` answered but not in the required JSON shape; status `incomplete`, never approval |
| `02-terra-review-92c59b5.md` | 2, `gpt-5.6-terra` | `92c59b5` | full response; the accepted finding on unlogged ignored revisions |
| `03-terra-re-review-50b0a53.md` | 3, `gpt-5.6-terra` re-review | `50b0a53` | full response; five test-strength findings, four accepted, one partly rejected |
| `04-deepseek-flash-review-df6f9cc.md`, `04-deepseek-flash-receipt.json` | 4, DeepSeek `deepseek-flash` | `df6f9cc` | full response and the API receipt with provider, model, finish reason and token usage (15,292 prompt, 2,970 completion) |
| `05-terra-delta-review-9c2cc38.md` | 5, `gpt-5.6-terra`, delta only | `df6f9cc..9c2cc38` | full response; diagnostics-only delta confirmed |
| (not tracked) | 6, `gpt-5.6-terra` blind assessment | `b088b68` | the full output is a scored assessment and is kept private in the current checkout; the repository carries only its engineering findings and dispositions in `quest/review-log.md` section 6 and its snapshot hash `7681e748…`. Earlier public commits on this branch (`5d9935d` to `d364c58`) still contain the file; history was not rewritten. |

Not included: the CLI run logs, which carry session identifiers and local paths, and the prompts and snapshots themselves, which reproduce the repository files at those revisions. Review 1 (a free worker's prose-only scenario review, no repository access) produced no artifact worth tracking beyond the four test cases it prompted in `tests/test_reason.py`.
