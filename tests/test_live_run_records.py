"""Offline checks for quest/live-runs/diagnose.py: coverage, unknown ids, failure metadata, schema.

The script is imported by path; it makes no model call at import time.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

from research_agent.models import Claim, SourceClaims
from research_agent.reason import _norm, _validate_member, build_claim_catalogue

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "quest" / "live-runs" / "diagnose.py"


def _load():
    spec = importlib.util.spec_from_file_location("diagnose", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


diag = _load()


def _sets():
    return [
        SourceClaims(source_id="s1", claims=[Claim(text="Adoption is rising", supporting_quote="adoption rose sharply"),
                                              Claim(text="Costs fell", supporting_quote="unit costs fell")]),
        SourceClaims(source_id="s2", claims=[Claim(text="Hiring slowed", supporting_quote="hiring slowed in Q2")]),
    ]


def _member(sid="s1", claim="Adoption is rising", quote="adoption rose sharply"):
    return {"source_id": sid, "stance": "supports", "claim_text": claim, "supporting_quote": quote, "confidence": "high"}


def _recorder(members):
    sets = _sets()
    catalogue = build_claim_catalogue(sets)
    rec = diag.Recorder()
    rec.note_extracted(sets, _norm)
    for m in members:
        rec.note_member(m, catalogue, _validate_member, _norm)
    return rec.counts()


def test_repeated_accepted_member_counts_once_for_coverage():
    c = _recorder([_member(), _member(), _member(quote="Adoption  Rose   Sharply")])
    assert c["proposed"] == 3 and c["accepted"] == 3
    assert c["distinct_accepted"] == 1 and c["distinct_extracted"] == 3
    assert c["coverage_overall"] == round(1 / 3, 4)
    assert c["per_source"]["s1"]["coverage"] == 0.5 and c["per_source"]["s2"]["coverage"] == 0.0
    assert c["sources_with_no_survivors"] == ["s2"]


def test_unknown_source_ids_go_to_the_fixed_bucket_never_as_keys():
    c = _recorder([_member(sid="s404"), _member(sid="../etc"), _member(sid=7), _member()])
    assert set(c["per_source"]) == {"s1", "s2"}
    assert c["unknown_source"] == {"proposed": 3, "rejected": 3}
    assert c["rejected_by_reason"] == {"missing_source_id": 1, "unknown_source": 2}


def test_zero_denominators_are_null_not_zero():
    sets = [SourceClaims(source_id="s1", claims=[])]
    rec = diag.Recorder()
    rec.note_extracted(sets, _norm)
    c = rec.counts()
    assert c["rejected_fraction"] is None and c["coverage_overall"] is None
    assert c["per_source"]["s1"]["coverage"] is None
    assert diag.ratio(0, 0) is None and diag.ratio(1, 4) == 0.25


def test_rejection_detail_classifies_rewritten_claim_over_matching_quote():
    c = _recorder([_member(claim="Adoption is exploding")])
    assert c["rejection_detail"] == {"quote_exact_claim_rewritten": 1}
    c = _recorder([_member(quote="adoption rose")])
    assert c["rejection_detail"] == {"quote_is_substring_of_real_quote": 1}


def test_failure_record_carries_metadata_and_only_a_vocabulary_error_type():
    base = diag.base_record(9, "inputs/ai-jobs.json", SCRIPT)
    assert base["status"] == "incomplete" and base["exit_code"] is None
    rec = diag.failure_record(base, TimeoutError("secret quote text must not leak"))
    assert rec["status"] == "failed" and rec["exit_code"] == 1 and rec["error_type"] == "TimeoutError"
    assert diag.error_type(KeyError("x")) == "OtherError"
    assert diag.error_type(ConnectionError()) == "ConnectionError"
    assert "secret" not in json.dumps(rec)
    diag.check_counts_only(rec)  # a failure record is itself a valid counts-only record


def test_input_path_must_be_repository_relative_under_inputs():
    assert diag.validate_input_path("inputs/ai-jobs.json") == "inputs/ai-jobs.json"
    for bad in ("/etc/passwd", "../inputs/x.json", "inputs/../x.json", "out/x.json", "inputs/x.txt", "inputs/a/b.json"):
        with pytest.raises(ValueError):
            diag.validate_input_path(bad)


def test_counts_only_validator_rejects_free_text_and_bad_numbers():
    base = diag.base_record(1, "inputs/ai-jobs.json", SCRIPT)
    with pytest.raises(ValueError):
        diag.check_counts_only({**base, "note": "free text"})
    with pytest.raises(ValueError):
        diag.check_counts_only({**base, "per_source": {"hiring slowed": {}}})
    with pytest.raises(ValueError):
        diag.check_counts_only({**base, "claims_extracted": -1})
    with pytest.raises(ValueError):
        diag.check_counts_only({**base, "coverage_overall": math.inf})
    with pytest.raises(ValueError):
        diag.check_counts_only({**base, "error_type": "boom: adoption rose sharply"})


@pytest.mark.parametrize("path", sorted((ROOT / "quest" / "live-runs").glob("run*.json")))
def test_tracked_run_records_are_counts_only(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    if "schema_version" not in record:
        pytest.skip("runs 1 and 2 predate the schema and are preserved byte-for-byte")
    diag.check_counts_only(record)
    assert record["status"] in ("completed", "failed"), "an incomplete attempt must not be tracked"
