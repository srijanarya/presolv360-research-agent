import { useState, useCallback } from 'react'
import type { Brief, PipelineStage, SourceStatus, SSEEvent } from './types'
import { postResearch, streamRun } from './api'
import InputForm from './components/InputForm'
import RunProgress from './components/RunProgress'
import ClaimGraph from './components/ClaimGraph'
import GapsPanel from './components/GapsPanel'
import SourceLegend from './components/SourceLegend'
import ExportBar from './components/ExportBar'

type AppState = 'idle' | 'running' | 'done' | 'error'

interface SourceBadge {
  id: string
  url: string
  status: SourceStatus
  title: string
}

interface RunState {
  runId: string
  activeStage: PipelineStage | null
  completedStages: Set<PipelineStage>
  sources: SourceBadge[]
}

export default function App() {
  const [appState, setAppState] = useState<AppState>('idle')
  const [runState, setRunState] = useState<RunState | null>(null)
  const [brief, setBrief] = useState<Brief | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleSubmit = useCallback(
    async (topic: string, urls: string[], adversarial: boolean) => {
      setAppState('running')
      setErrorMsg(null)
      setBrief(null)

      let runId: string
      try {
        runId = await postResearch(topic, urls, adversarial)
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : String(err))
        setAppState('error')
        return
      }

      setRunState({
        runId,
        activeStage: null,
        completedStages: new Set(),
        sources: [],
      })

      const stop = streamRun(runId, (event: SSEEvent) => {
        switch (event.type) {
          case 'stage_started':
            setRunState((prev) =>
              prev ? { ...prev, activeStage: event.stage } : prev,
            )
            break

          case 'source_status':
            setRunState((prev) => {
              if (!prev) return prev
              const existing = prev.sources.find((s) => s.id === event.id)
              if (existing) {
                return {
                  ...prev,
                  sources: prev.sources.map((s) =>
                    s.id === event.id
                      ? { ...s, status: event.status, title: event.title }
                      : s,
                  ),
                }
              }
              return {
                ...prev,
                sources: [
                  ...prev.sources,
                  {
                    id: event.id,
                    url: event.url,
                    status: event.status,
                    title: event.title,
                  },
                ],
              }
            })
            break

          case 'stage_completed':
            setRunState((prev) => {
              if (!prev) return prev
              const next = new Set(prev.completedStages)
              next.add(event.stage)
              return { ...prev, completedStages: next, activeStage: null }
            })
            break

          case 'done':
            stop()
            setBrief(event.brief)
            setAppState('done')
            break

          case 'error':
            stop()
            setErrorMsg(event.error)
            setAppState('error')
            break
        }
      })
    },
    [],
  )

  const handleReset = () => {
    setAppState('idle')
    setRunState(null)
    setBrief(null)
    setErrorMsg(null)
  }

  return (
    <div className="min-h-screen bg-bg text-ink">
      <div className="max-w-6xl mx-auto px-4 py-12 space-y-8">
        {/* Header bar */}
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xs font-mono text-muted uppercase tracking-widest">
              Presolve 360
            </span>
            <div className="w-16 h-px bg-line mt-1" />
          </div>
          {(appState === 'done' || appState === 'error') && (
            <button
              onClick={handleReset}
              className="text-sm text-muted hover:text-ink transition-colors"
            >
              ← New research
            </button>
          )}
        </div>

        {/* Input form — shown when idle or errored */}
        {(appState === 'idle' || appState === 'error') && (
          <InputForm
            onSubmit={handleSubmit}
            disabled={false}
          />
        )}

        {/* Error message */}
        {appState === 'error' && errorMsg && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-6 py-4 text-sm text-red-400 max-w-2xl mx-auto">
            <span className="font-medium">Error: </span>
            {errorMsg}
          </div>
        )}

        {/* Live progress */}
        {appState === 'running' && runState && (
          <RunProgress
            activeStage={runState.activeStage}
            completedStages={runState.completedStages}
            sources={runState.sources}
          />
        )}

        {/* Results */}
        {appState === 'done' && brief && runState && (
          <div className="space-y-8">
            {/* Brief header */}
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold text-ink">{brief.topic}</h1>
              <p className="text-xs text-muted">
                Generated{' '}
                {new Date(brief.generated_at).toLocaleString()} ·{' '}
                {brief.meta.sources_ok} sources OK ·{' '}
                {brief.meta.sources_failed} failed
              </p>
            </div>

            <ExportBar runId={runState.runId} />

            <ClaimGraph brief={brief} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <GapsPanel gaps={brief.gaps} />
              <SourceLegend sources={brief.sources} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
