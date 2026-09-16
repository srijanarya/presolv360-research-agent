"""Regenerate every number the Quest claims, from fixtures, offline.

Runs the SAME fixtures against the reasoning module at the recorded baseline SHA
and against the working tree, so before/after is reproducible rather than asserted.
Also regenerates comparison baselines for the problems that were NOT implemented.

    uv run python scripts/measure.py            # prints a table, writes quest/measurements.json
    uv run python scripts/measure.py --check    # also fails if a target regressed
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "grounding"
BASELINE_SHA = "f58b327"  # tag quest-baseline: public main + pre-Accept housekeeping
REASON_PATH = "src/research_agent/reason.py"

sys.path.insert(0, str(ROOT / "src"))
from research_agent.extract import _norm_ws  # noqa: E402  (unchanged in both versions)
from research_agent.models import SourceClaims  # noqa: E402
import research_agent.reason as current_reason  # noqa: E402


def _norm(text: str) -> str:
    return _norm_ws(text).lower()


def _catalogue(data: dict) -> set[tuple[str, str, str]]:
    """Every (source_id, claim_text, quote) association the fixture's extraction produced."""
    return {(s["source_id"], _norm(c["text"]), _norm(c["supporting_quote"]))
            for s in data["claim_sets"] for c in s["claims"]}


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True, stderr=subprocess.PIPE).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(
            f"cannot read git history ({' '.join(args)}): {exc}\n"
            "The before/after measurement needs this repository's history at "
            f"{BASELINE_SHA}. A shallow or exported copy cannot regenerate it."
        )


def load_baseline_reason():
    """Import reason.py as it was at BASELINE_SHA. Fails loudly, never silently."""
    resolved = _git("rev-parse", f"{BASELINE_SHA}^{{commit}}")
    source = _git("show", f"{BASELINE_SHA}:{REASON_PATH}")
    digest = hashlib.sha256(source.encode()).hexdigest()
    tmp = Path(tempfile.mkdtemp(prefix="baseline-reason-")) / "baseline_reason.py"
    tmp.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("baseline_reason", tmp)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "build_claim_catalogue"):
        raise SystemExit(f"{BASELINE_SHA} already contains the grounding change; baseline is not the 'before' state")
    return module, {"sha": resolved, "reason_py_sha256": digest}


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def responder(data: dict, counters: dict):
    async def fake(system: str, prompt: str, model: str):
        if "stress-test" in system:
            counters["model_calls"] += 1
            return {"for": "f", "against": "a", "members": data.get("adversarial_members", [])}
        counters["model_calls"] += 1
        return data["response"]
    return fake


async def run_one(module, data: dict, *, adversarial: bool) -> dict:
    counters = {"model_calls": 0}
    sets = [SourceClaims.model_validate(s) for s in data["claim_sets"]]
    try:
        clusters, gaps = await module.build_claim_graph(
            data["topic"], sets, call_model=responder(data, counters), adversarial=adversarial
        )
    except Exception as exc:  # noqa: BLE001 — the outcome IS the measurement
        return {"outcome": type(exc).__name__, "detail": str(exc)[:120], "model_calls": counters["model_calls"]}
    catalogue = _catalogue(data)
    survivors = [(m.source_id, _norm(m.claim_text), _norm(m.supporting_quote)) for c in clusters for m in c.members]
    return {
        "outcome": "ok",
        "model_calls": counters["model_calls"],
        # Full serialized output: the only thing "unchanged" may legitimately mean.
        "clusters": [c.model_dump() for c in clusters],
        "gaps": [g.model_dump() for g in gaps],
        "classifications": [c.classification for c in clusters],
        # Retention judged per association, not by counting heads.
        "valid_retained": sum(1 for t in survivors if t in catalogue),
        "invalid_retained": sum(1 for t in survivors if t not in catalogue),
    }


async def grounding_measurements(baseline) -> dict:
    valid, mixed = fixture("all-valid"), fixture("mixed-invalid")
    out = {}
    for label, module in (("baseline", baseline), ("current", current_reason)):
        out[label] = {
            "all_valid_no_adversarial": await run_one(module, valid, adversarial=False),
            "all_valid_adversarial": await run_one(module, valid, adversarial=True),
            "mixed_no_adversarial": await run_one(module, mixed, adversarial=False),
            "mixed_adversarial": await run_one(module, mixed, adversarial=True),
            "null_clusters": await run_one(module, {"topic": "t", "claim_sets": valid["claim_sets"], "response": {"clusters": None}}, adversarial=False),
        }
    return out


async def p1_call_count() -> dict:
    """P1 comparison baseline, NOT implemented: one recheck call per multi-source cluster."""
    data = fixture("all-valid")
    counters = {"model_calls": 0}
    sets = [SourceClaims.model_validate(s) for s in data["claim_sets"]]
    response = {"clusters": [dict(data["response"]["clusters"][0], statement=f"c{i}") for i in range(5)], "gaps": []}
    await current_reason.build_claim_graph(
        data["topic"], sets, call_model=responder({**data, "response": response}, counters), adversarial=True
    )
    return {"multi_source_clusters": 5, "total_model_calls": counters["model_calls"], "implemented": False}


def p3_run_retention() -> dict:
    """P3 comparison baseline, NOT implemented: created runs are never evicted."""
    from fastapi.testclient import TestClient
    from research_agent.api import create_app

    async def noop(topic, urls, *, on_event=None, adversarial=True):
        raise RuntimeError("not driven")

    with TestClient(create_app(pipeline_fn=noop)) as client:
        ids = [client.post("/api/research", json={"topic": "t", "urls": ["u1", "u2", "u3"]}).json()["run_id"]
               for _ in range(100)]
        still_known = sum(1 for run_id in ids if client.get(f"/api/research/{run_id}").status_code != 404)
    return {"runs_created": len(ids), "runs_still_retained": still_known, "implemented": False}


def p4_unsafe_urls() -> dict:
    """P4 comparison baseline, NOT implemented: POST accepts URLs the fetch layer would refuse."""
    from fastapi.testclient import TestClient
    from research_agent.api import create_app

    async def noop(topic, urls, *, on_event=None, adversarial=True):
        raise RuntimeError("not driven")

    unsafe = ["file:///etc/passwd", "http://169.254.169.254/latest/meta-data/", "not-a-url", "ftp://example.org/x"]
    with TestClient(create_app(pipeline_fn=noop)) as client:
        codes = {url: client.post("/api/research", json={"topic": "t", "urls": [url, "https://a.example", "https://b.example"]}).status_code
                 for url in unsafe}
    return {"post_status_codes": codes, "rejected_at_post": sum(1 for c in codes.values() if c == 422), "implemented": False}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if a stated target regressed")
    args = parser.parse_args()

    baseline, identity = load_baseline_reason()
    grounding = await grounding_measurements(baseline)
    report = {
        "baseline": identity,
        "labels": {
            "measured": "regenerated by this script from tracked fixtures",
            "fixture_only_cost_proxy": "model-call counts on fixtures; not a production cost",
            "unavailable": "not measurable from this repository",
        },
        "grounding": grounding,
        "p1_recheck_calls": await p1_call_count(),
        "p3_run_retention": p3_run_retention(),
        "p4_unsafe_url_posts": p4_unsafe_urls(),
        "unavailable": ["production p95 latency", "monetary savings", "bug-recurrence rate", "DORA change-failure rate"],
    }

    b, c = grounding["baseline"], grounding["current"]
    # The mixed fixture proposes 5 members: 1 valid (a whitespace/case variant of a
    # real s1 association) and 4 invalid (unknown source x2, wrong-source quote,
    # fabricated quote). It is a superset of the 3-invalid pre-Accept probe.
    bm, cm = b["mixed_no_adversarial"], c["mixed_no_adversarial"]
    same_valid = (json.dumps(b["all_valid_adversarial"], sort_keys=True)
                  == json.dumps(c["all_valid_adversarial"], sort_keys=True))
    rows = [
        ("invalid members retained (of 4, mixed fixture)", bm["invalid_retained"], cm.get("invalid_retained", 0), "measured"),
        ("valid normalized member retained (of 1)", bm["valid_retained"], cm.get("valid_retained", 0), "measured"),
        ("mixed fixture classification", bm["classifications"][0], cm["classifications"][0], "measured"),
        ("mixed fixture model calls (adversarial)", b["mixed_adversarial"]["model_calls"], c["mixed_adversarial"]["model_calls"], "fixture-only cost proxy"),
        ("all-valid full output, baseline vs current", "reference", "identical" if same_valid else "DIFFERS", "measured"),
        ("null clusters outcome", b["null_clusters"]["outcome"], c["null_clusters"]["outcome"], "measured"),
    ]
    width = max(len(r[0]) for r in rows)
    print(f"{'measurement'.ljust(width)}  {'baseline':>22}  {'current':>22}  label")
    for name, before, after, label in rows:
        print(f"{name.ljust(width)}  {str(before):>22}  {str(after):>22}  {label}")
    print(f"\nbaseline {identity['sha'][:12]} reason.py sha256 {identity['reason_py_sha256'][:12]}")

    (ROOT / "quest").mkdir(exist_ok=True)
    (ROOT / "quest" / "measurements.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("wrote quest/measurements.json")

    if args.check:
        failures = []
        if cm["classifications"] != ["outlier"]:
            failures.append("surviving mixed cluster must be outlier")
        if not same_valid:
            failures.append("all-valid output differs between baseline and current (full serialization)")
        if c["null_clusters"]["outcome"] != "ValueError":
            failures.append("null clusters must raise ValueError")
        if (bm["invalid_retained"], bm["valid_retained"]) != (4, 1):
            failures.append("baseline must retain all 4 invalid and the 1 valid association (the defect)")
        if (cm.get("invalid_retained"), cm.get("valid_retained")) != (0, 1):
            failures.append("current must retain 0 invalid and exactly the 1 valid association")
        expected_dir = FIXTURES
        for name, key in (("all-valid", "all_valid_adversarial"), ("mixed-invalid", "mixed_no_adversarial")):
            expected = json.loads((expected_dir / f"{name}.expected.json").read_text(encoding="utf-8"))
            got = {"clusters": c[key]["clusters"], "gaps": c[key]["gaps"]}
            if json.dumps(expected, sort_keys=True) != json.dumps(got, sort_keys=True):
                failures.append(f"{name} output differs from its tracked expected file")
        for f in failures:
            print("FAIL:", f)
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
