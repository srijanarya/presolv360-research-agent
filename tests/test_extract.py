"""E3 — Per-source claim extraction (parallel, resilient, quote-grounded).

`call_model` (the JSON-returning model wrapper) is injected as a fake, so no
network/LLM is touched. The load-bearing invariant: every surviving claim's
`supporting_quote` is a verbatim substring of its source (hallucinated quotes are
dropped).
"""

from __future__ import annotations

from research_agent.extract import extract_all, extract_claims, quote_in_source
from research_agent.llm import ModelJSONError
from research_agent.models import SourceDoc


def _doc(id: str, text: str) -> SourceDoc:
    return SourceDoc(id=id, url=f"https://x.example/{id}", status="ok", text=text)


# --- E3.S2 — quote_in_source (pure) ---

def test_supporting_quote_is_substring_of_source():
    text = "AI will reshape   knowledge\n work over the next decade in many fields."
    assert quote_in_source("reshape knowledge work", text)
    assert not quote_in_source("reshape financial work", text)


def test_quote_in_source_normalizes_whitespace():
    assert quote_in_source("foo bar", "foo\n   bar baz qux")


def test_quote_in_source_rejects_empty():
    assert not quote_in_source("   ", "any source text here")


# --- E3.S1 — extraction returns schema-valid claims ---

async def test_extracted_claims_validate_against_schema():
    doc = _doc("s1", "Junior roles are most exposed to automation according to the new study.")

    async def fake_call_model(system: str, prompt: str, model: str):
        return {
            "claims": [
                {
                    "text": "Junior roles are most exposed to automation",
                    "supporting_quote": "Junior roles are most exposed to automation",
                    "confidence": "high",
                }
            ]
        }

    sc = await extract_claims("AI's impact on jobs", doc, call_model=fake_call_model)
    assert sc.source_id == "s1"
    assert len(sc.claims) == 1
    claim = sc.claims[0]
    assert claim.text
    assert claim.supporting_quote
    assert claim.confidence in ("high", "medium", "low")


# --- E3.S2 — hallucinated quotes are dropped (provenance invariant) ---

async def test_claims_with_unfindable_quote_are_dropped():
    doc = _doc("s1", "The study covers many occupations and industries worldwide in detail.")

    async def fake_call_model(system: str, prompt: str, model: str):
        return {
            "claims": [
                {"text": "broad coverage", "supporting_quote": "covers many occupations", "confidence": "medium"},
                {"text": "fabricated", "supporting_quote": "this phrase never appears in the source", "confidence": "high"},
            ]
        }

    sc = await extract_claims("topic", doc, call_model=fake_call_model)
    assert len(sc.claims) == 1
    assert sc.claims[0].supporting_quote == "covers many occupations"


# --- E3.S3 — resilient parallel extraction ---

async def test_junk_from_one_source_is_dropped_not_fatal():
    docs = [_doc(f"s{i}", f"SRC{i} marker: the report makes a claim about jobs and wages.") for i in (1, 2, 3)]

    async def fake_call_model(system: str, prompt: str, model: str):
        if "SRC2" in prompt:
            raise ModelJSONError("model returned junk twice")
        return {"claims": [{"text": "jobs change", "supporting_quote": "a claim about jobs", "confidence": "high"}]}

    results = await extract_all("AI jobs", docs, call_model=fake_call_model)
    by_id = {s.source_id: s for s in results}
    assert len(by_id["s1"].claims) == 1
    assert len(by_id["s3"].claims) == 1
    assert by_id["s2"].claims == []  # junk source contributes nothing, no crash


async def test_extract_all_skips_non_ok_sources():
    docs = [
        _doc("s1", "SRC1 marker: a claim about jobs here in the body text."),
        SourceDoc(id="s2", url="u", status="error", text=""),
    ]

    async def fake_call_model(system: str, prompt: str, model: str):
        return {"claims": [{"text": "x", "supporting_quote": "a claim about jobs", "confidence": "low"}]}

    results = await extract_all("AI jobs", docs, call_model=fake_call_model)
    ids = {s.source_id for s in results}
    assert ids == {"s1"}  # the failed source is not sent to the model
