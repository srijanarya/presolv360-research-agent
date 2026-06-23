import type { SSEEvent } from './types'

const BASE = '/api'

// ── REST ──────────────────────────────────────────────────────────────────────

export async function postResearch(
  topic: string,
  urls: string[],
  adversarial: boolean,
): Promise<string> {
  const res = await fetch(`${BASE}/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, urls, adversarial }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`POST /api/research failed (${res.status}): ${text}`)
  }
  const data = (await res.json()) as { run_id: string }
  return data.run_id
}

// ── SSE stream ────────────────────────────────────────────────────────────────

export function streamRun(
  runId: string,
  onEvent: (event: SSEEvent) => void,
): () => void {
  const es = new EventSource(`${BASE}/research/${runId}/stream`)
  let stopped = false

  const stop = () => {
    stopped = true
    es.close()
  }

  es.onmessage = (msg) => {
    if (stopped) return
    try {
      onEvent(JSON.parse(msg.data) as SSEEvent)
    } catch {
      // ignore malformed frames
    }
  }

  es.onerror = () => {
    // The server closes the connection after the terminal event; the caller calls
    // stop() on done/error (setting `stopped`), so reaching here while not stopped
    // means a genuine unexpected drop — surface it once, then stop.
    if (stopped) return
    onEvent({ type: 'error', error: 'Stream connection lost.' })
    stop()
  }

  return stop
}

// ── View endpoints ────────────────────────────────────────────────────────────

export function jsonUrl(runId: string) {
  return `${BASE}/research/${runId}`
}

export function markdownUrl(runId: string) {
  return `${BASE}/research/${runId}/brief.md`
}

export function htmlUrl(runId: string) {
  return `${BASE}/research/${runId}/brief.html`
}
