# Blind review — grounding validation in `reason.py` (df6f9cc)

**Verified in the text:** everything below is read from the supplied diff, full file, tests, fixtures and host-run evidence. **Assumed:** the behaviour of `run_pipeline`, the API SSE layer, `_client`, `_sse_events`, and the harness that produced the measurement table — none of those are shown, so criteria 14 and the SSE test are assessed only as written.

---

## 1. Correctness defects

**D1 — `_adversarial_recheck` counts `unknown_source` per proposed source, not per ignored revision, and counts it even when the revision is otherwise applied to nothing. (Low)**
Location: `_adversarial_recheck`, the `for source_id in proposed:` loop.
Trigger: a recheck returns `{"members":[{"source_id":"s404","stance":"supports"}]}` while `members` contains no `s404`.
Behaviour: `ignored["unknown_source"] += 1` is logged, which is correct in spirit, but the counter is incremented once per *distinct* unknown source id rather than once per revision, and the same id appearing twice in `revised` is counted once. Criterion 9 asks for a logged reason, not an exact count, so this is a reporting inaccuracy rather than a behavioural bug. It is only a defect if a reader treats the logged totals as revision counts.

**D2 — `_validate_member` accepts a `source_id` whose catalogue entry exists but whose `claim_text`/`quote` are matched against a *different* `SourceClaims` entry with the same id. (Low, arguably intended)**
Location: `build_claim_catalogue` unions associations per source id; `_validate_member` looks up only by `source_id`.
Trigger: two `SourceClaims` entries share `source_id="s1"`, one carrying `("a","qa")` and the other `("b","qb")`; the model proposes `("a","qb")`.
Behaviour: rejected, because the union set contains only the two original pairs. This is correct. The residual risk is the reverse: if extraction ever emits the same `source_id` for two genuinely different documents, the union widens the accepted set across documents. Criterion 1 explicitly mandates the union, so this is a design consequence, not a defect — flagged only because it is the one place where "match the association extraction produced" is weaker than it sounds.

**D3 — `_parse_members` treats a missing `members` key and a non-list `members` value identically. (Informational)**
Location: `_parse_members`, `raw_cluster.get("members", [])`.
Trigger: a cluster dict with no `members` key.
Behaviour: `raw_members` is `[]`, which is a list, so no `malformed_member_collection` is counted and the cluster is silently dropped by the `if not members:` branch in `_finalize`. Criterion 13 says skip malformed clusters while keeping partial results — this satisfies it — but the rejection counter under-reports. No wrong output.

No correctness defect was found that produces a wrong accepted member, a wrong classification, or a wrong gap from the code as written.

---

## 2. Acceptance criteria not met

**C11 — "Raise a descriptive `ValueError` … when a non-empty proposed cluster list yields no valid surviving members at all."**
The implementation raises only when `raw_clusters` is truthy *and* `clusters` is empty. That matches the criterion. However, the criterion also lists "when `clusters` is missing or not a list" — the code raises for `"clusters" not in raw` and for a non-list value, which matches. **Met.**

**C14 — "Let the failure propagate on the existing path: reasoning to pipeline to the API's SSE `error` event."**
The reasoning stage raises `ValueError`. Whether `run_pipeline` and the SSE layer convert that into an `error` event without also emitting `done` is **not verifiable from the supplied material** — the pipeline and API code are not in the diff. The SSE test asserts it, and the host-run evidence shows the test passing, but the test is the only evidence. **Assumed met, not verified.**

**C15 — "Log rejection totals and reason codes using indices or validated identifiers, never raw source text."**
The grounding log uses `dict(sorted(rejections.items()))` — reason codes and counts only. The recheck log uses `dict(sorted(ignored.items()))` — reason codes and counts only. The `logger.info("cluster %d dropped: no grounded members", index)` line uses the cluster index. **Met.** One caveat: `logger.warning("adversarial recheck failed for %r: %s", statement[:60], exc)` in the pre-existing exception path logs the first 60 characters of the cluster *statement*, which is model-generated text derived from source claims. That line is unchanged by this diff and is outside the new logging, but it is the one place where source-derived text reaches a log. If criterion 15 is read as covering the whole stage, this is a gap; if it covers only the new rejection logging, it is not.

All other criteria (1–10, 12, 13) are met by the code as written.

---

## 3. Tests weaker than the criterion they claim

**T1 — `test_null_non_list_and_missing_clusters_raise_descriptive_value_error` uses `pytest.raises(ValueError, match=...)` with substrings that a generic message would also satisfy.**
The `"not an object"` case matches `"not a JSON object"`; the `"must be a list"` case matches both the `clusters` and (hypothetically) any other list-typed field. A guard that raised `ValueError("clusters must be a list")` for *every* malformed input would pass all four cases. The test does not distinguish "descriptive" from "generic". It would still fail if the guard were removed entirely, so it is not vacuous — but it is weaker than criterion 11's "descriptive" wording.

**T2 — `test_all_members_rejected_raises_value_error` matches `"no member was grounded"`, which is a substring of the actual message.**
A guard that raised `ValueError("no member was grounded")` with no rejection detail would pass. Criterion 11 asks for a descriptive error; the test does not check that the rejection counts appear in the message. The host-run evidence shows the message includes `rejections: {...}`, but the test does not assert it.

**T3 — `test_no_claim_or_quote_text_reaches_any_log` checks a fixed list of five secrets.**
It would pass if the implementation logged a *different* source string not in the list. The test is a spot check, not a proof of criterion 15. It is strengthened by the `secret.lower() not in logged.lower()` line, which catches case variants of the listed secrets only.

**T4 — `test_golden_all_valid_fixture_matches_tracked_expected_output` asserts `not any(key in json.dumps(got) for key in ("generated_at", "timestamp", "2026"))`.**
This is a weak proxy for "timestamps frozen". It would pass if the stage serialized a timestamp under a different key name, or a year other than 2026. The criterion says "byte-identical with timestamps frozen"; the test does not freeze anything, it only checks for three substrings. The real guarantee comes from the fact that this stage serializes no time-varying field at all, which the test comment acknowledges — so the assertion is decorative.

**T5 — `test_recheck_exception_keeps_naive_stances` asserts only `classification == "consensus"`.**
Criterion 10 says "keep the existing behaviour of returning naive stances when the recheck call raises". The test would pass if the exception path returned the members with *any* stances that happen to classify as consensus — e.g. if it flipped both to `contradicts`. It does not assert the stances are unchanged. A guard that swallowed the exception and returned `[]` would fail (no cluster), so it is not vacuous, but it is weaker than the criterion.

**T6 — `test_multiplicity_counted_after_validation_skips_recheck` asserts `counters["adv"] == 0`.**
This would also pass if the recheck were skipped for an unrelated reason (e.g. `adversarial=False` default, or a bug that skipped all rechecks). The companion test `test_valid_unique_agreeing_revision_is_applied_after_validation` guards the opposite direction, so the pair is adequate in combination, but this test alone is weak.

**T7 — `test_golden_mixed_fixture_drops_a_model_call_versus_the_baseline` asserts `calls["n"] == 1`.**
Same shape as T6: it would pass if the clustering call were the only call for any reason. The comment names the intended reason; the assertion does not verify it.

No test was found that would pass with the grounding guard removed entirely — the four "measured defects" tests (`test_unknown_source_is_rejected`, `test_quote_belonging_to_another_source_is_rejected`, `test_fabricated_quote_is_rejected`, `test_opposite_claim_text_on_a_genuine_quote_is_rejected`) all fail against the baseline, as the measurement table confirms (`invalid members retained: 4 → 0`).

---

## 4. Anything that could mislead a reader of the brief

**M1 — The measurement table's "invalid members retained (of 4, mixed fixture): 4 → 0" is labelled `measured`, but the mixed fixture contains four proposed members of which three are invalid and one is a valid whitespace/case variant.** The row conflates "invalid members" with "members dropped". A reader could conclude the stage drops valid variants too. The companion row "valid normalized member retained (of 1): 1 → 1" corrects this, but the first row's label is imprecise.

**M2 — "all-valid full output, baseline vs current: reference → identical" is labelled `measured`, but the baseline is described as `reference`, not as a re-run.** If the baseline output was captured from a prior run rather than recomputed, the row is a comparison against a stored artifact, not a measurement of the baseline. The brief does not say which. This matters because the all-valid fixture is the one case where the change is supposed to be a no-op.

**M3 — The docstring in `build_claim_graph` says "Raises `ValueError` on a response that cannot be trusted at all: not an object, no usable `clusters` list, or proposed clusters of which nothing survived grounding validation."** The phrase "no usable `clusters` list" is broader than the code: a `clusters` list containing only malformed entries does *not* raise if at least one entry is a dict with a grounded member; and an empty list does not raise. The docstring's "no usable" could be read as covering the empty case, which criterion 12 explicitly excludes. The code is correct; the docstring is loose.

**M4 — The module docstring says "Validation runs BEFORE the adversarial pass, classification and gap derivation."** True for the adversarial pass and classification. For gap derivation, `llm_gaps` are parsed from the raw response *before* validation and are concatenated with `derive_gaps(clusters)` *after*. So LLM-surfaced gaps are not filtered by grounding. Criterion 6 says "Recompute classification and derived gaps from survivors" — `derive_gaps` is recomputed, `llm_gaps` are not. The docstring's blanket claim is misleading for the LLM-gap half. This is arguably out of scope (the criteria speak of "derived gaps"), but a reader of the docstring would not expect unfiltered LLM gaps to survive.

**M5 — The comment "A single-source cluster is always `outlier` regardless of stance, so the adversarial recheck is a provable no-op — skip it" is correct for classification but not for stance.** The recheck can change a member's stance, and a single-source cluster's stance is not observable in the classification. But the *member's* stance is part of the output and is asserted in the golden fixtures. Skipping the recheck for single-source clusters means the output stance is the naive one, which is a deliberate choice, not a no-op. The word "no-op" is accurate only with respect to classification.

**M6 — The host-run evidence shows `100 passed, 1 warning in 1.45s` and `measure rc=0`, but the warning is not identified.** A reader cannot tell whether the warning is the pre-existing `TestClient` deprecation shown in the snippet or something new. The brief presents the run as clean; the warning is unexplained.

---

## Summary

| Category | Finding |
|---|---|
| Correctness defects | None that produce wrong output; D1–D3 are reporting/design notes. |
| Criteria not met | C14 unverifiable from supplied material; C15 met for new logging, with one pre-existing source-derived log line outside the change. |
| Weak tests | T1–T7, all non-vacuous but weaker than the criterion they name. |
| Misleading brief | M1–M6, chiefly the "measured" labels on rows that are comparisons against stored artifacts and the docstring's over-broad "validation runs before … gap derivation". |