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

  es.onmessage = (msg) => {
    try {
      const parsed = JSON.parse(msg.data) as SSEEvent
      onEvent(parsed)
    } catch {
      // ignore malformed frames
    }
  }

  es.onerror = () => {
    onEvent({ type: 'error', error: 'Stream connection lost.' })
    es.close()
  }

  return () => es.close()
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
