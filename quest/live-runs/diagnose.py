"""Instrumented live run of the pipeline: how many proposed members the grounding gate rejects.

    uv run python quest/live-runs/diagnose.py inputs/ai-jobs.json quest/live-runs/run3.json

Writes a sanitized, counts-only record. Association sets stay in memory; no claim, quote or
source text is serialized. Exception messages go to stderr only (redirect it to a private log).
The record is written with status "incomplete" at start and replaced at the end, so an
interrupted attempt stays visibly incomplete. Instrumentation is restored in `finally`.
"""
from __future__ import annotations

import asyncio
import builtins
import collections
import datetime as _dt
import hashlib
import json
import math
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE_ID = re.compile(r"^s\d+$")
UNKNOWN = "unknown_source"
ERROR_VOCAB = ("ValueError", "RuntimeError", "TimeoutError", "ConnectionError", "OSError")
DETAIL_KEYS = ("quote_exact_claim_rewritten", "quote_exact_claim_belongs_to_other_quote",
               "quote_is_substring_of_real_quote", "quote_superset_of_real_quote",
               "quote_from_other_source", "quote_not_found_anywhere")
SCHEMA_VERSION = 2


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def ratio(num: int, den: int):
    """Counts-only ratio; `None` on a zero denominator, never an invented zero."""
    return None if den == 0 else round(num / den, 4)


def error_type(exc: BaseException) -> str:
    """Fixed safe vocabulary; TimeoutError and ConnectionError are checked before their parent OSError."""
    for name in ERROR_VOCAB:
        if isinstance(exc, getattr(builtins, name)):
            return name
    return "OtherError"


def validate_input_path(path: str) -> str:
    """Repository-relative path under inputs/, no absolute or parent components."""
    p = pathlib.PurePosixPath(path.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or len(p.parts) != 2 or p.parts[0] != "inputs" or not p.name.endswith(".json"):
        raise ValueError("input must be a repository-relative path like inputs/<name>.json")
    return str(p)


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


class Recorder:
    """Counts proposed/accepted/rejected members and distinct association coverage, in memory."""

    def __init__(self) -> None:
        self.proposed = collections.Counter()   # sid -> proposed occurrences
        self.accepted = collections.Counter()   # sid -> accepted occurrences
        self.rejected = collections.Counter()   # sid -> rejected occurrences
        self.reasons = collections.Counter()    # reason code -> count
        self.detail = collections.Counter()     # ungrounded_pair sub-category -> count
        self.accepted_assoc: dict[str, set] = collections.defaultdict(set)   # sid -> normalized triples
        self.extracted_assoc: dict[str, set] = {}
        self.extracted_claims: dict[str, int] = {}

    @staticmethod
    def sid_key(sid, known) -> str:
        return sid if isinstance(sid, str) and sid in known and SOURCE_ID.match(sid) else UNKNOWN

    def note_extracted(self, claim_sets, norm) -> None:
        for s in claim_sets:
            sid = str(s.source_id)
            self.extracted_claims[sid] = self.extracted_claims.get(sid, 0) + len(s.claims)
            self.extracted_assoc.setdefault(sid, set()).update((norm(c.text), norm(c.supporting_quote)) for c in s.claims)

    def note_member(self, item, catalogue, validate, norm) -> None:
        if not isinstance(item, dict):
            return
        sid = item.get("source_id")
        key = self.sid_key(sid, catalogue)
        self.proposed[key] += 1
        member, reason = validate(item, catalogue)
        if member is not None:
            self.accepted[key] += 1
            self.accepted_assoc[key].add((norm(member.claim_text), norm(member.supporting_quote)))
            return
        self.rejected[key] += 1
        self.reasons[reason] += 1
        if reason == "ungrounded_pair":
            self.detail[self.classify(sid, item.get("claim_text"), item.get("supporting_quote"), catalogue, norm)] += 1

    @staticmethod
    def classify(sid, claim_text, quote, catalogue, norm) -> str:
        assoc = catalogue.get(sid, set())
        quotes = {q for _, q in assoc}
        claims = {c for c, _ in assoc}
        nq, nc = norm(quote), norm(claim_text)
        if nq in quotes and nc not in claims:
            return "quote_exact_claim_rewritten"
        if nq in quotes:
            return "quote_exact_claim_belongs_to_other_quote"
        if any(nq in q for q in quotes):
            return "quote_is_substring_of_real_quote"
        if any(q in nq for q in quotes):
            return "quote_superset_of_real_quote"
        if any(nq in q or q in nq for s2, a in catalogue.items() if s2 != sid for _, q in a):
            return "quote_from_other_source"
        return "quote_not_found_anywhere"

    def counts(self) -> dict:
        known = sorted(self.extracted_assoc, key=lambda s: int(s[1:]) if SOURCE_ID.match(s) else 0)
        per_source = {}
        for sid in known:
            if not SOURCE_ID.match(sid):
                continue
            de = len(self.extracted_assoc[sid])
            da = len(self.accepted_assoc.get(sid, ()))
            per_source[sid] = {"extracted": self.extracted_claims.get(sid, 0), "distinct_extracted": de,
                               "proposed": self.proposed[sid], "accepted": self.accepted[sid],
                               "rejected": self.rejected[sid], "distinct_accepted": da, "coverage": ratio(da, de)}
        proposed = sum(self.proposed.values())
        distinct_extracted = sum(len(v) for k, v in self.extracted_assoc.items() if SOURCE_ID.match(k))
        distinct_accepted = sum(len(v) for k, v in self.accepted_assoc.items() if k != UNKNOWN)
        return {
            "sources_ok": len(per_source),
            "claims_extracted": sum(self.extracted_claims.values()),
            "proposed": proposed,
            "accepted": sum(self.accepted.values()),
            "rejected": sum(self.rejected.values()),
            "rejected_by_reason": dict(sorted(self.reasons.items())),
            "rejected_fraction": ratio(sum(self.rejected.values()), proposed),
            "distinct_extracted": distinct_extracted,
            "distinct_accepted": distinct_accepted,
            "coverage_overall": ratio(distinct_accepted, distinct_extracted),
            "per_source": per_source,
            "sources_with_no_survivors": [s for s, v in per_source.items() if v["distinct_extracted"] > 0 and v["distinct_accepted"] == 0],
            UNKNOWN: {"proposed": self.proposed[UNKNOWN], "rejected": self.rejected[UNKNOWN]},
            "rejection_detail": {k: self.detail[k] for k in DETAIL_KEYS if self.detail[k]},
        }


def base_record(attempt: int, input_rel: str, script: pathlib.Path) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "attempt": attempt,
        "git_sha": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "input_path": input_rel,
        "input_sha256": hashlib.sha256((ROOT / input_rel).read_bytes()).hexdigest(),
        "started_utc": utc_now(),
        "finished_utc": None,
        "status": "incomplete",
        "exit_code": None,
        "error_type": None,
    }


def failure_record(record: dict, exc: BaseException) -> dict:
    return {**record, "finished_utc": utc_now(), "status": "failed", "exit_code": 1, "error_type": error_type(exc)}


def write(path: pathlib.Path, record: dict) -> None:
    check_counts_only(record)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


ALLOWED_TOP = {"schema_version", "attempt", "git_sha", "git_dirty", "script_sha256", "input_path", "input_sha256",
               "started_utc", "finished_utc", "status", "exit_code", "error_type", "sources_ok", "claims_extracted",
               "proposed", "accepted", "rejected", "rejected_by_reason", "rejected_fraction", "distinct_extracted",
               "distinct_accepted", "coverage_overall", "per_source", "sources_with_no_survivors", UNKNOWN,
               "rejection_detail", "final_clusters", "final_members", "classification"}
PER_SOURCE_KEYS = {"extracted", "distinct_extracted", "proposed", "accepted", "rejected", "distinct_accepted", "coverage"}
HEX = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
REASON = re.compile(r"^[a-z_]+$")


def _num(v, label: str) -> None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        raise ValueError(f"{label}: numbers must be finite and non-negative")


def check_counts_only(record: dict) -> None:
    """Raise if the record carries anything but counts, ratios, ids, hashes, timestamps and fixed vocab."""
    extra = set(record) - ALLOWED_TOP
    if extra:
        raise ValueError(f"unexpected keys: {sorted(extra)}")
    if record["status"] not in ("completed", "failed", "incomplete"):
        raise ValueError("bad status")
    if record["error_type"] not in (None, "OtherError", *ERROR_VOCAB):
        raise ValueError("bad error_type")
    if validate_input_path(record["input_path"]) != record["input_path"]:
        raise ValueError("bad input_path")
    for k in ("git_sha", "script_sha256", "input_sha256"):
        if not HEX.match(record[k]):
            raise ValueError(f"{k} is not a hash")
    for k in ("started_utc", "finished_utc"):
        if record[k] is not None and not ISO.match(record[k]):
            raise ValueError(f"{k} is not an ISO UTC timestamp")
    if not isinstance(record["git_dirty"], bool):
        raise ValueError("git_dirty must be a bool")
    for k in ("schema_version", "attempt", "sources_ok", "claims_extracted", "proposed", "accepted", "rejected",
              "distinct_extracted", "distinct_accepted", "final_clusters", "final_members", "exit_code"):
        if k in record and record[k] is not None:
            _num(record[k], k)
    for k in ("rejected_fraction", "coverage_overall"):
        if k in record and record[k] is not None:
            _num(record[k], k)
    for k in ("rejected_by_reason", "rejection_detail", "classification"):
        for kk, v in record.get(k, {}).items():
            if not REASON.match(kk):
                raise ValueError(f"{k} key {kk!r} is not a reason code")
            _num(v, f"{k}.{kk}")
    for sid, v in record.get("per_source", {}).items():
        if not SOURCE_ID.match(sid) or set(v) != PER_SOURCE_KEYS:
            raise ValueError(f"per_source {sid!r} has bad shape")
        for kk, vv in v.items():
            if vv is not None:
                _num(vv, f"per_source.{sid}.{kk}")
    for sid in record.get("sources_with_no_survivors", []):
        if not SOURCE_ID.match(sid):
            raise ValueError("sources_with_no_survivors must hold pipeline ids")
    u = record.get(UNKNOWN, {"proposed": 0, "rejected": 0})
    if set(u) != {"proposed", "rejected"}:
        raise ValueError("unknown_source bucket has bad shape")


async def run(input_rel: str, attempt: int, out: pathlib.Path) -> int:
    from research_agent import pipeline, reason
    from research_agent.reason import _norm, _validate_member

    script = pathlib.Path(__file__).resolve()
    record = base_record(attempt, input_rel, script)
    write(out, record)  # visible as incomplete until replaced
    rec = Recorder()
    orig_parse, orig_extract = reason._parse_members, pipeline.extract_all

    def wrapped_parse(raw_members, catalogue, rejections=None):
        if isinstance(raw_members, list):
            for item in raw_members:
                rec.note_member(item, catalogue, _validate_member, _norm)
        return orig_parse(raw_members, catalogue, rejections)

    async def extract_wrapped(topic, docs):
        sets = await orig_extract(topic, docs)
        rec.note_extracted(sets, _norm)
        return sets

    reason._parse_members = wrapped_parse
    try:
        data = json.loads((ROOT / input_rel).read_text(encoding="utf-8"))
        brief = await pipeline.run_pipeline(data["topic"], data["urls"], extract_fn=extract_wrapped)
    except Exception as exc:  # noqa: BLE001 — the failure IS the measurement; message stays private
        print(f"attempt {attempt} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        write(out, failure_record(record, exc))
        return 1
    finally:
        reason._parse_members = orig_parse
    clusters = brief.claim_clusters
    record.update(rec.counts())
    record.update({
        "final_clusters": len(clusters),
        "final_members": sum(len(c.members) for c in clusters),
        "classification": dict(sorted(collections.Counter(c.classification for c in clusters).items())),
        "finished_utc": utc_now(), "status": "completed", "exit_code": 0,
    })
    write(out, record)
    print(json.dumps({k: record[k] for k in ("attempt", "status", "proposed", "accepted", "rejected",
                                             "rejected_fraction", "coverage_overall", "final_clusters")}))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: diagnose.py inputs/<name>.json quest/live-runs/runN.json", file=sys.stderr)
        return 2
    input_rel = validate_input_path(argv[1])
    out = pathlib.Path(argv[2])
    m = re.search(r"(\d+)", out.stem)
    attempt = int(m.group(1)) if m else 0
    return asyncio.run(run(input_rel, attempt, out))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
