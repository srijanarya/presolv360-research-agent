# Review log — who reviewed what, and what I did about it

Model identities below come from host-recorded metadata: the router lane or the exact CLI invocation. None of them comes from a model's own claim about itself.

## Reviews that completed

### 1. Free worker, scenario coverage, before the first commit

- **Model:** `nvidia/nemotron-3-super-120b-a12b:free` via OpenRouter, recorded by the worker wrapper.
- **Input:** the 25 already-covered scenarios plus the validation rules, as prose. No repository access.
- **Output quality:** poor. It mostly listed questions to itself and was cut off mid-sentence without committing to findings.
- **Disposition:** I read it as a checklist rather than a review, and adopted **four** genuinely untested cases from it: a pairing swapped *within* one source, a stance in the wrong case, a non-string confidence value, and an unusable adversarial response. Tests for all four are in `tests/test_reason.py`. The rest was noise.

### 2. Independent review, `gpt-5.6-terra`, high reasoning, read-only sandbox

- **Snapshot:** sha256 `3895ec58…`, covering the contract, the production diff, the fixtures and host-run evidence. Commit `92c59b5`.
- **Finding, valid:** directive criterion 9 requires a logged reason for every ignored stance revision, but only ambiguous originals and conflicting revisions were logged. Unknown source ids, malformed entries, a non-list collection and a non-object response were dropped silently.
- **Disposition: accepted and fixed** in commit `50b0a53`, with a test that asserts each reason code and that no source text reaches the logs.
- **Also noted, valid:** the snapshot contained no test assertions, so test strength could not be judged. My snapshot's fault; the next one included the tests.

### 3. Independent re-review, `gpt-5.6-terra`, same settings

- **Brief:** sha256 `756a0015…`, the delta since `92c59b5` plus the full module, the tests, the fixtures and fresh evidence.
- **Verdict on correctness:** no defect verified in the module or the delta, and the earlier finding confirmed fixed.
- **Five findings on test strength, four accepted:**

| Finding | Disposition |
|---|---|
| Ambiguous and conflicting revisions were never asserted to *log* anything, despite the docstring claiming all four categories | **Accepted.** Both tests now assert their reason code. |
| The no-source-text check was one string on one path | **Accepted.** A new test runs a case that trips both log paths and asserts every fixture claim and quote is absent, case-insensitively. |
| `ValueError` was accepted without checking the message, while criterion 11 requires descriptive errors | **Accepted.** Each malformed shape now matches its own message. |
| The golden fixtures were exercised only by the measurement harness, not by tests | **Accepted.** Three tests now assert the all-valid fixture's stable output, the mixed fixture's exact survivors, relabeling, gaps and cluster removal, and the model-call drop. |
| Valid, unique, agreeing revisions were never tested, leaving criterion 8 unproven | **Partly rejected.** A pre-existing test already covers it, `test_contested_emerges_when_sources_conflict`; it was simply not in the supplied excerpt. I added an explicit post-validation assertion anyway, since the reviewer could not see it and neither could a future reader. |

- **Two trust limitations raised, both accepted as limitations rather than fixed:** a cluster's `statement` is the model's own text and is not grounded, and model-surfaced gaps are accepted as written. Both are now stated in ADR 001 and in the non-goals, because closing them needs semantic comparison, which this change deliberately does not attempt.

## Reviews that did NOT complete

Two free reviewers from distinct families were planned, `qwen38` plus NVIDIA DeepSeek Flash, with Nemotron Ultra as fallback. **Neither run produced a usable review.**

| Attempt | Route outcomes |
|---|---|
| First, 150 s per route | qwen38 timed out; DeepSeek Flash missed its probe; Nemotron Ultra answered but returned non-JSON |
| Retry, 420 s per route | all three unavailable: qwen38 timed out, and both NVIDIA endpoints missed their probes |

This is recorded as **incomplete, not as approval**. The snapshot was 34 KB, which those routes may simply not sustain; the cause was capacity, not review content. The completed independent review is the Terra pair above, which is a single model family and therefore **not** cross-vendor coverage of the diff.

## What a human reviewed

Srijan reviews the decision record, the diff and the measurements, and approves publication. He corrected this work four times during preparation, including replacing a guessed token allowance with the provider's documented limits and separating billing from task success. Those corrections are his, and they are recorded in the preparation notes rather than claimed here as AI output.
