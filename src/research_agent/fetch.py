"""Stage 1 — fetch & parse messy real-world web content (our own tool, not the
agent's WebFetch; ADR-7).

A fallback ladder per URL: httpx + trafilatura → readability → headless Playwright
(JS/paywalled pages). Every source returns a `SourceDoc` carrying a `status`; the
functions here **never raise** — a failure is reported as a status, so one bad URL
can't abort the run (the graceful-failure axis). The httpx client and the JS
renderer are dependency-injected so the ladder is tested with no network/browser.
"""

from __future__ import annotations

import asyncio
import re
from html import unescape

import httpx
import trafilatura

from research_agent.models import FetchStatus, SourceDoc

# A realistic browser UA — some sites 403 the default httpx agent.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MIN_TEXT_LEN = 200  # below this, extracted text is "thin" → try the next rung
REQUEST_TIMEOUT = 20.0

# Specific phrases that signal a paywall/registration gate (not generic "subscribe").
PAYWALL_MARKERS = (
    "subscribe to continue",
    "to continue reading",
    "subscribers only",
    "for subscribers",
    "create a free account to read",
    "this content is for members",
    "already a subscriber",
    "metered paywall",
)


class PlaywrightUnavailable(RuntimeError):
    """Raised by the renderer when Playwright or its browser isn't installed."""


def _has_paywall_marker(html: str) -> bool:
    low = html.lower()
    return any(marker in low for marker in PAYWALL_MARKERS)


def classify_fetch(
    text: str | None = None,
    *,
    status_code: int | None = None,
    exc: Exception | None = None,
    raw_html: str | None = None,
) -> FetchStatus:
    """Map a fetch outcome (exception | HTTP status | extracted text) to a status.

    Pure function — the deterministic core of graceful failure (E2.S1).
    """
    if exc is not None:
        if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
            return "timeout"
        return "error"
    if status_code is not None and status_code >= 400:
        return "error"
    if text and len(text.strip()) >= MIN_TEXT_LEN:
        return "ok"
    # Thin or empty body: distinguish a paywall gate from a genuinely empty page.
    if raw_html and _has_paywall_marker(raw_html):
        return "paywalled"
    return "empty"


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return unescape(match.group(1)).strip() if match else ""


def _extract_main_text(html: str, url: str | None = None) -> str:
    """trafilatura (boilerplate-stripping) with a readability fallback."""
    text = trafilatura.extract(html, url=url, favor_recall=True) or ""
    if len(text.strip()) >= MIN_TEXT_LEN:
        return text
    try:
        from readability import Document

        summary_html = Document(html).summary()
        stripped = re.sub(r"<[^>]+>", " ", summary_html)
        stripped = unescape(re.sub(r"\s+", " ", stripped)).strip()
        if len(stripped) > len(text):
            return stripped
    except Exception:
        pass  # readability is best-effort; fall back to whatever trafilatura gave
    return text


async def _playwright_render(url: str) -> str:
    """Render a JS-heavy page to HTML. Raises PlaywrightUnavailable if not installed."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # package missing
        raise PlaywrightUnavailable("playwright not installed") from exc
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=HEADERS["User-Agent"])
                await page.goto(url, wait_until="networkidle", timeout=30_000)
                return await page.content()
            finally:
                await browser.close()
    except PlaywrightUnavailable:
        raise
    except Exception as exc:  # browser binary missing, launch failure, nav error
        raise PlaywrightUnavailable(str(exc)) from exc


async def fetch_source(
    source_id: str,
    url: str,
    *,
    client: httpx.AsyncClient,
    render=_playwright_render,
) -> SourceDoc:
    """Fetch one URL through the ladder. Never raises — failures become a status."""
    try:
        resp = await client.get(
            url, headers=HEADERS, follow_redirects=True, timeout=REQUEST_TIMEOUT
        )
    except Exception as exc:  # noqa: BLE001 — deliberately catch-all (graceful failure)
        return SourceDoc(id=source_id, url=url, status=classify_fetch(exc=exc), error=str(exc))

    if resp.status_code >= 400:
        return SourceDoc(
            id=source_id, url=url, status="error", error=f"HTTP {resp.status_code}"
        )

    html = resp.text
    text = _extract_main_text(html, url=url)
    title = _extract_title(html)
    status = classify_fetch(text, status_code=resp.status_code, raw_html=html)
    method = "httpx"

    # Rung 3 — JS render when the static fetch came back thin/empty/gated.
    if status != "ok" and render is not None:
        try:
            rendered = await render(url)
        except PlaywrightUnavailable:
            if status == "empty":
                status = "js_required"  # thin page that likely needs JS
        else:
            rendered_text = _extract_main_text(rendered, url=url)
            if len(rendered_text.strip()) >= MIN_TEXT_LEN:
                text, title, method, status = (
                    rendered_text,
                    _extract_title(rendered) or title,
                    "playwright",
                    "ok",
                )

    return SourceDoc(
        id=source_id,
        url=url,
        status=status,
        text=text if status == "ok" else text or "",
        title=title,
        fetch_method=method if status == "ok" else None,
        error=None if status == "ok" else status,
    )


async def fetch_all(
    sources: list[tuple[str, str]],
    *,
    client: httpx.AsyncClient | None = None,
    render=_playwright_render,
) -> list[SourceDoc]:
    """Fetch every (id, url) concurrently. One failure never aborts the batch."""
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient()
    try:
        docs = await asyncio.gather(
            *(fetch_source(sid, url, client=client, render=render) for sid, url in sources)
        )
    finally:
        if owns_client:
            await client.aclose()
    return list(docs)
