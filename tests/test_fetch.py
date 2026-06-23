"""E2 — Robust fetch ladder with graceful failure (no real network).

Every test injects an httpx MockTransport and/or a fake renderer, so the ladder's
behaviour is asserted deterministically. The contract: ``fetch_source`` / ``fetch_all``
NEVER raise — a failure becomes a status on the returned ``SourceDoc``.
"""

from __future__ import annotations

import httpx

from research_agent.fetch import (
    PlaywrightUnavailable,
    classify_fetch,
    fetch_all,
    fetch_source,
)

ARTICLE_HTML = """<!doctype html><html><head><title>Enhance or Eliminate</title></head>
<body>
<nav>Home About Subscribe NAVLINK_SENTINEL</nav>
<article>
<h1>Enhance or Eliminate</h1>
<p>Artificial intelligence will reshape knowledge work over the coming decade in profound and uneven ways across the economy.</p>
<p>Researchers found that junior analysts face the highest exposure to task automation, while senior roles tend to see augmentation rather than replacement. BODY_SENTENCE_SENTINEL appears here in the main body text of the article for the test to find.</p>
<p>The study tracked thousands of occupations across multiple industries and labor markets worldwide, weighting each by its share of routine cognitive work.</p>
<p>Its authors caution that adoption speed, not technical capability, will determine how quickly these effects show up in real hiring data.</p>
</article>
<footer>Copyright 2026 FOOTER_SENTINEL</footer>
</body></html>"""

THIN_HTML = "<html><head><title>Loading</title></head><body><div id='app'>Loading…</div></body></html>"

PAYWALL_HTML = """<!doctype html><html><head><title>Members Only</title></head>
<body><article><p>This is a short preview of the piece.</p></article>
<div class="gate">To continue reading, subscribe to continue.</div></body></html>"""


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- E2.S1 — classify_fetch (pure) ---

def test_status_ok_for_substantial_text():
    assert classify_fetch("word " * 100) == "ok"


def test_status_empty_for_blank_body():
    assert classify_fetch("   ") == "empty"


def test_status_timeout_maps_from_timeout_exc():
    assert classify_fetch(exc=httpx.ReadTimeout("slow")) == "timeout"


def test_status_error_maps_from_http_5xx():
    assert classify_fetch(status_code=503) == "error"


def test_status_paywalled_on_known_paywall_marker():
    assert classify_fetch("short preview", raw_html=PAYWALL_HTML) == "paywalled"


# --- E2.S2 — happy-path extraction (boilerplate stripped) ---

async def test_fetch_returns_clean_text_and_title():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html=ARTICLE_HTML)

    async with _client(handler) as client:
        doc = await fetch_source("s1", "https://x.example/a", client=client)

    assert doc.status == "ok"
    assert doc.fetch_method == "httpx"
    assert "BODY_SENTENCE_SENTINEL" in doc.text          # main content kept
    assert "NAVLINK_SENTINEL" not in doc.text            # nav stripped
    assert "FOOTER_SENTINEL" not in doc.text             # footer stripped
    assert "Enhance or Eliminate" in doc.title


# --- E2.S3 — fallback ladder + Playwright-absent degradation ---

async def test_falls_back_to_playwright_when_text_too_thin():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html=THIN_HTML)

    async def render(_url: str) -> str:
        return ARTICLE_HTML

    async with _client(handler) as client:
        doc = await fetch_source("s1", "https://x.example/a", client=client, render=render)

    assert doc.status == "ok"
    assert doc.fetch_method == "playwright"
    assert "BODY_SENTENCE_SENTINEL" in doc.text


async def test_js_required_when_playwright_unavailable():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html=THIN_HTML)

    async def render(_url: str) -> str:
        raise PlaywrightUnavailable("chromium not installed")

    async with _client(handler) as client:
        doc = await fetch_source("s1", "https://x.example/a", client=client, render=render)

    assert doc.status == "js_required"   # degraded, not crashed


# --- E2.S4 — one failing source never aborts the batch ---

async def test_one_failing_source_does_not_abort_others():
    def handler(request: httpx.Request) -> httpx.Response:
        if "boom" in str(request.url):
            raise httpx.ConnectError("boom")
        return httpx.Response(200, html=ARTICLE_HTML)

    async with _client(handler) as client:
        docs = await fetch_all(
            [
                ("s1", "https://x.example/a"),
                ("s2", "https://x.example/boom"),
                ("s3", "https://x.example/c"),
            ],
            client=client,
        )

    assert len(docs) == 3
    by_id = {d.id: d for d in docs}
    assert by_id["s1"].status == "ok"
    assert by_id["s3"].status == "ok"
    assert by_id["s2"].status == "error"
    assert by_id["s2"].error  # carries the failure message
