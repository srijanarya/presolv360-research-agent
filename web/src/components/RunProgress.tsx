import type { PipelineStage, SourceStatus } from '../types'

interface StageInfo {
  key: PipelineStage
  label: string
}

const STAGES: StageInfo[] = [
  { key: 'fetch', label: 'Fetch' },
  { key: 'extract', label: 'Extract' },
  { key: 'reason', label: 'Reason' },
  { key: 'synthesize', label: 'Synthesize' },
]

type StageState = 'pending' | 'running' | 'done'

interface SourceBadge {
  id: string
  url: string
  status: SourceStatus
  title: string
}

interface Props {
  activeStage: PipelineStage | null
  completedStages: Set<PipelineStage>
  sources: SourceBadge[]
}

const STATUS_STYLES: Record<SourceStatus, string> = {
  ok: 'bg-consensus/20 text-consensus border-consensus/30',
  paywalled: 'bg-contested/20 text-contested border-contested/30',
  js_required: 'bg-contested/20 text-contested border-contested/30',
  timeout: 'bg-contested/20 text-contested border-contested/30',
  empty: 'bg-contested/20 text-contested border-contested/30',
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
}

const STATUS_LABELS: Record<SourceStatus, string> = {
  ok: 'OK',
  paywalled: 'Paywall',
  js_required: 'JS',
  timeout: 'Timeout',
  empty: 'Empty',
  error: 'Error',
}

function stageState(
  key: PipelineStage,
  activeStage: PipelineStage | null,
  completedStages: Set<PipelineStage>,
): StageState {
  if (completedStages.has(key)) return 'done'
  if (activeStage === key) return 'running'
  return 'pending'
}

export default function RunProgress({
  activeStage,
  completedStages,
  sources,
}: Props) {
  return (
    <div className="bg-panel border border-line rounded-xl p-6 space-y-6 w-full max-w-2xl mx-auto">
      {/* Stage chips */}
      <div>
        <p className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
          Pipeline
        </p>
        <div className="flex gap-3 flex-wrap">
          {STAGES.map(({ key, label }) => {
            const state = stageState(key, activeStage, completedStages)
            return (
              <div
                key={key}
                className={[
                  'flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors',
                  state === 'done'
                    ? 'border-consensus/40 bg-consensus/10 text-consensus'
                    : state === 'running'
                      ? 'border-outlier/60 bg-outlier/10 text-outlier animate-pulse'
                      : 'border-line bg-bg text-muted',
                ].join(' ')}
              >
                {state === 'done' && (
                  <span className="text-consensus text-xs">✓</span>
                )}
                {state === 'running' && (
                  <span className="inline-block w-2 h-2 rounded-full bg-outlier animate-pulse" />
                )}
                {state === 'pending' && (
                  <span className="inline-block w-2 h-2 rounded-full bg-line" />
                )}
                {label}
              </div>
            )
          })}
        </div>
      </div>

      {/* Per-source status */}
      {sources.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
            Sources
          </p>
          <div className="space-y-2">
            {sources.map((s) => (
              <div
                key={s.id}
                className="flex items-center gap-3 text-sm"
              >
                <span className="font-mono text-xs text-muted w-6 flex-shrink-0">
                  {s.id}
                </span>
                <span
                  className={[
                    'px-1.5 py-0.5 rounded border text-xs font-medium flex-shrink-0',
                    STATUS_STYLES[s.status],
                  ].join(' ')}
                >
                  {STATUS_LABELS[s.status]}
                </span>
                <span className="text-muted truncate flex-1 min-w-0">
                  {s.title || s.url}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
