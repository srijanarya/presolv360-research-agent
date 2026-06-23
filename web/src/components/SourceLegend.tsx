import type { BriefSource, SourceStatus } from '../types'

interface Props {
  sources: BriefSource[]
}

const STATUS_BADGE: Record<SourceStatus, { label: string; cls: string }> = {
  ok: { label: 'OK', cls: 'bg-consensus/20 text-consensus border-consensus/30' },
  paywalled: {
    label: 'Paywall',
    cls: 'bg-contested/20 text-contested border-contested/30',
  },
  js_required: {
    label: 'JS Required',
    cls: 'bg-contested/20 text-contested border-contested/30',
  },
  timeout: {
    label: 'Timeout',
    cls: 'bg-contested/20 text-contested border-contested/30',
  },
  empty: {
    label: 'Empty',
    cls: 'bg-contested/20 text-contested border-contested/30',
  },
  error: {
    label: 'Error',
    cls: 'bg-red-500/20 text-red-400 border-red-500/30',
  },
}

export default function SourceLegend({ sources }: Props) {
  return (
    <div className="bg-panel border border-line rounded-xl p-6">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted mb-4">
        Sources
      </h2>
      <div className="space-y-3">
        {sources.map((s) => {
          const badge = STATUS_BADGE[s.status]
          const failed = s.status !== 'ok'
          return (
            <div
              key={s.id}
              className={[
                'flex items-start gap-3 text-sm p-3 rounded-lg border',
                failed ? 'border-line bg-bg' : 'border-line bg-bg',
              ].join(' ')}
            >
              <span className="font-mono text-xs text-muted w-6 flex-shrink-0 mt-0.5">
                {s.id}
              </span>
              <span
                className={[
                  'px-1.5 py-0.5 rounded border text-xs font-medium flex-shrink-0',
                  badge.cls,
                ].join(' ')}
              >
                {badge.label}
              </span>
              <div className="flex-1 min-w-0">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ink hover:text-outlier transition-colors block truncate"
                  title={s.url}
                >
                  {s.title || s.url}
                </a>
                {s.error && (
                  <p className="text-xs text-red-400 mt-0.5 truncate">
                    {s.error}
                  </p>
                )}
                {s.fetch_method && !failed && (
                  <p className="text-xs text-muted mt-0.5">
                    via {s.fetch_method}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
