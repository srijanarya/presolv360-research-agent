"""Second live run: classify why the reasoning stage rejects members. Writes JSON, no source text."""
import asyncio, json, sys, collections
from research_agent import reason, pipeline
from research_agent.reason import _norm

record = {"proposed": 0, "accepted": 0, "rejected": collections.Counter(), "detail": collections.Counter(), "per_source": collections.Counter(), "extracted_per_source": {}}
catalogue_ref = {}

orig_parse = reason._parse_members
def wrapped_parse(raw_members, catalogue, rejections=None):
    catalogue_ref["c"] = catalogue
    if isinstance(raw_members, list):
        for item in raw_members:
            if not isinstance(item, dict): continue
            record["proposed"] += 1
            sid, ct, q = item.get("source_id"), item.get("claim_text"), item.get("supporting_quote")
            member, reason_code = reason._validate_member(item, catalogue)
            if member: record["accepted"] += 1; record["per_source"][f"{sid}:accepted"] += 1; continue
            record["rejected"][reason_code] += 1; record["per_source"][f"{sid}:rejected"] += 1
            if reason_code == "ungrounded_pair":
                assoc = catalogue.get(sid, set())
                quotes = {qq for _, qq in assoc}; claims = {cc for cc, _ in assoc}
                nq, nc = _norm(q), _norm(ct)
                if nq in quotes and nc not in claims: record["detail"]["quote_exact_claim_rewritten"] += 1
                elif nq in quotes: record["detail"]["quote_exact_claim_belongs_to_other_quote"] += 1
                elif any(nq in qq for qq in quotes): record["detail"]["quote_is_substring_of_real_quote"] += 1
                elif any(qq in nq for qq in quotes): record["detail"]["quote_superset_of_real_quote"] += 1
                elif any(nq in qq or qq in nq for s2, a in catalogue.items() if s2 != sid for _, qq in a): record["detail"]["quote_from_other_source"] += 1
                else: record["detail"]["quote_not_found_anywhere"] += 1
    return orig_parse(raw_members, catalogue, rejections)
reason._parse_members = wrapped_parse

orig_extract = pipeline.extract_all
async def extract_wrapped(topic, docs):
    sets = await orig_extract(topic, docs)
    record["extracted_per_source"] = {s.source_id: len(s.claims) for s in sets}
    return sets

inp = json.load(open(sys.argv[1]))
brief = asyncio.run(pipeline.run_pipeline(inp["topic"], inp["urls"], extract_fn=extract_wrapped))
clusters = brief.claim_clusters
record["final_clusters"] = len(clusters)
record["final_members"] = sum(len(c.members) for c in clusters)
record["classification"] = dict(collections.Counter(c.classification for c in clusters))
for k in ("rejected", "detail", "per_source"): record[k] = dict(record[k])
json.dump(record, open(sys.argv[2], "w"), indent=2)
print(json.dumps(record, indent=2))
