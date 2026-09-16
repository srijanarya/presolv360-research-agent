# Review log — who reviewed what, and what I did about it

Model identities below come from host-recorded metadata: the router lane or the exact CLI invocation. None of them comes from a model's own claim about itself. The raw reviewer outputs and host receipts behind this log are tracked in [`quest/reviews/`](reviews/README.md), so the summaries here can be checked against what each reviewer actually returned.

## What each review actually saw

The reviews did **not** all see the same revision. Production code changed after each of the first three, and the last production change is covered by a focused delta review. Review 1 has no row because it was a prose-only scenario review with no repository snapshot, so there is no revision or hash to record. Review 6 is an assessment of the whole package after the production freeze; it changed no code.

| # | Reviewer | Revision reviewed | Snapshot or brief sha256 | Production code changed afterwards? |
|---|---|---|---|---|
| 2 | `gpt-5.6-terra` | `92c59b5` | `3895ec58…` | yes, `50b0a53` (log reasons) |
| 3 | `gpt-5.6-terra` re-review | `50b0a53` | `756a0015…` | yes, `9c2cc38` via `df6f9cc` (harness only) |
| 4 | `deepseek-flash` | `df6f9cc` | `456d9140…` | yes, `9c2cc38` (diagnostics) |
| 5 | `gpt-5.6-terra`, delta only | `df6f9cc..9c2cc38` | `55eb8376…` | no; every later commit is documentation, tests or live-run records |
| 6 | `gpt-5.6-terra`, blind assessment of the whole package | `b088b68` | `7681e748…` | no; one production finding is disclosed and deferred, see below |

So the two vendors reviewed different revisions. Coverage is cross-vendor in the sense that OpenAI and DeepSeek each reviewed the full module at some revision, and the final production delta was reviewed once, by OpenAI. It is not two vendors on one identical snapshot.

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

### 4. Independent blind review, DeepSeek `deepseek-flash`, direct API, the second model family

- **Snapshot:** sha256 `456d9140…` at commit `df6f9cc`: contract, diff, full module, tests, fixtures, tracked expected outputs, host-run evidence.
- **Identity and cost, from the host receipt:** provider `deepseek`, model `deepseek-flash`, finish reason `stop`, usage 15,292 prompt and 2,970 completion tokens, settled at an estimated $0.0082 under the $2 Quest ledger. Thinking was disabled so that every generated token was visible content.
- **A first attempt is on the ledger too:** with thinking enabled, the model spent all 16,384 permitted tokens on hidden reasoning and returned no visible content. It was billed at about $0.024, recorded as incomplete, and **not retried as the same request**; the second attempt is a reconfigured one.
- **Correctness:** none found that produces a wrong member, label or gap. Three reporting notes were accepted and fixed: unknown-source revisions are now counted per entry, a cluster with no `members` key is now reported as malformed, and a pre-existing exception log line that carried 60 characters of model-written statement text now logs only a member count.
- **Seven test-strength findings, all accepted:** the exception-path test now asserts unchanged stances; the two call-count tests now assert the stated reason; each malformed-shape test matches a message unique to its shape, including the type received; the all-rejected test asserts the reason codes in the message; the no-source-text test now whitelists the shape of every log line instead of spot-checking five strings; and the timestamp check became an assertion on the exact serialized field sets.
- **Six "could mislead a reader" findings.** Accepted and fixed: the module docstring overclaimed that gap derivation is filtered, when model-surfaced gaps are not; a docstring said "no usable `clusters` list", looser than the code; a pre-existing comment called the single-source skip a "no-op", which is true only for the label; and the harness's baseline column said "reference" when the baseline is recomputed from the recorded SHA on every run. **Rejected:** the claim that the mixed fixture holds "four proposed members, three invalid" reads only its first cluster; the fixture proposes five across two clusters, four invalid, which the evidence table states. The row was reworded anyway so no reader trips the same way. Also noted: the one pytest warning in the evidence is the pre-existing `starlette` TestClient deprecation, unrelated to this change.
- **Out of the reviewer's reach, stated by it:** criterion 14's pipeline and API path was not in the snapshot; it is covered by the SSE test, which the host-run evidence shows passing.

### 5. Focused delta review, `gpt-5.6-terra`, of `df6f9cc..9c2cc38`

- **Why:** commit `9c2cc38` changed production code after the DeepSeek review, so that delta had not been independently seen.
- **Brief:** sha256 `55eb8376…`: the production, test and harness deltas, the full module, and evidence at `9c2cc38`.
- **Verdict, verified from the diff:** the delta changes diagnostics only, which are rejection and log counts and the text of the all-rejected error. Returned members, classifications and gaps are unchanged. No defect introduced. Its one stated assumption is that model construction has no hidden side effects, which is true of the plain pydantic models.
- **Disposition:** nothing to change.

With reviews 2 to 5, both vendors have reviewed the full module, and every production change has been reviewed by at least one of them. See the table at the top for which revision each saw.

### 6. Blind assessment of the whole package, `gpt-5.6-terra`, at `b088b68`

- **Snapshot:** sha256 `7681e748…` at commit `b088b68`: contract, full module, tests, fixtures, quest documents, live-run records, and host observations (a fresh `make check`, the PR and check-run queries, the Loom facts and its narration). No prior review output and no private notes were supplied. It is an assessment against the assignment rubric, not a code-review approval.
- **Finding, production, valid:** the `_adversarial_recheck` failure path logs the raw exception. A provider error can echo the prompt, which carries claim and quote text, so the line could put source text in the logs; the log-shape test admitted arbitrary text on that line. **Disposition: accepted and disclosed, not fixed.** Production code is frozen at `9c2cc38` for this submission so that the reviewed revision, the measurements and the walkthrough stay consistent. The concern is recorded in ADR 001 and the handoff checklist as the first follow-up; no test was added that would endorse the current line.
- **Finding, packaging, valid:** the appendix claimed an open pull request when none existed, listed the Loom as still to be recorded when it existed, and called the recording future work in the effort table. **Disposition: accepted and corrected** in the appendix, which now carries the walkthrough, the draft pull request and the hosted checks.
- **Finding, measurement, valid:** the `make check` wall clock was stated as "under 4 s" while the whole command took about 4.2 s in that host's run. **Disposition: accepted;** timings are now reported as measurements from identified runs.
- **Noted limitations, already recorded:** a cluster's `statement` and model-proposed gaps are ungrounded; strict equality rejects real members (the live-run cost); repeated source ids union their associations. Wording was tightened, nothing new was claimed.

## Preparation reviews, disclosed

Two reviews happened before the Quest was accepted, during preparation. They are AI reviewer findings with lead-agent dispositions. They are **not** Srijan's human design approval and **not** in-window rejection examples; the in-window examples are reviews 3 and 4 above.

- **Source review, 2026-09-15:** Codex CLI `gpt-5.6-terra`, read-only sandbox, brief sha256 `729ca45e…`, of the baseline module and a probe. Its seven findings (quote-only lookup does not bind claim to quote; the extraction helper checks containment, not equality; filter before recheck, classification and gaps; duplicate ids underspecified; null clusters abort the stage; fixtures need exact assertions; the size target) were accepted as clarifications to the contract, which is why the directive's criteria read as they do.
- **Plan review, 2026-09-15:** a text-only review of a plan summary by an agent configured as `gpt-5.6-terra` (`check_plan_consistency`), the same model family as the source review, with no repository access and no independent snapshot hash. Two of its recommendations were rejected by the lead agent: (1) tag the baseline before any housekeeping commit, rejected because a prepared baseline may include explicitly documented housekeeping as long as the original SHA and the preparation manifest are preserved; (2) require the golden brief to stay byte-for-byte unchanged outside removed members, rejected because membership changes classifications, empty-cluster retention, derived gaps and recheck eligibility, so an invalid fixture needs explicit expected graph changes and a separate all-valid fixture. Its caution on recurrence and provenance, the separation of P2 from P1 and P4, and the demand for genuine review evidence were adopted.

## Reviews that did NOT complete

Two free reviewers from distinct families were planned, `qwen38` plus NVIDIA DeepSeek Flash, with Nemotron Ultra as fallback. **Neither run produced a usable review.**

| Attempt | Route outcomes |
|---|---|
| First, 150 s per route | qwen38 timed out; DeepSeek Flash missed its probe; Nemotron Ultra answered but returned non-JSON |
| Retry, 420 s per route | all three unavailable: qwen38 timed out, and both NVIDIA endpoints missed their probes |

This is recorded as **incomplete, not as approval**. The snapshot was 34 KB, which those routes may simply not sustain; the cause was capacity, not review content. The second model family came instead from the budgeted DeepSeek review above.

## What a human reviewed

Srijan reviews the decision record, the diff and the measurements, and approves publication. Only decisions that the retained dispositions or the session record support are attributed to him here; a commit proves a change, not who asked for it.

- Preparation: he corrected the worker wiring four times, including replacing a guessed token allowance with the provider's documented limits and separating billing from task success, and he approved the exact brief and destination for the pre-Accept source review after two automatic rejections. Recorded in the preparation notes.
- In the window: his findings at about 10:55 IST opened a correction round: compare full output in the harness instead of counts, reconcile the effort log, remove an invented narrative, and track the scrubbed P4 evidence in the repository. Recorded in the effort log and in commits `df6f9cc` and `20e1bbf`.
- After the freeze: he set the scope of the closing round (production stays at `9c2cc38`; the log-line concern is disclosed, not fixed; the P4 branch is published without a pull request; three more live attempts; a draft pull request), and he approved the walkthrough for submission.

The findings themselves belong to the reviewers named above; the acceptance or rejection of each is a lead-agent disposition unless listed here as his.
