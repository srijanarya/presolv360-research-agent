import { useState } from 'react'
import type { ClaimCluster, BriefSource } from '../types'

interface Props {
  cluster: ClaimCluster
  sources: BriefSource[]
}

const STANCE_STYLES = {
  supports: 'text-consensus',
  contradicts: 'text-contested',
}

const CONFIDENCE_DOT = {
  high: 'bg-consensus',
  medium: 'bg-contested',
  low: 'bg-muted',
}

export default function ClaimCard({ cluster, sources }: Props) {
  const [expanded, setExpanded] = useState(false)

  const sourceMap = Object.fromEntries(sources.map((s) => [s.id, s]))

  return (
    <div className="bg-bg border border-line rounded-lg overflow-hidden transition-all">
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left px-5 py-4 flex items-start gap-3 group"
      >
        <span
          className={[
            'mt-1 text-sm flex-shrink-0 transition-transform',
            expanded ? 'rotate-90' : '',
          ].join(' ')}
          aria-hidden
        >
          ▶
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-ink text-sm font-medium leading-snug">
            {cluster.statement}
          </p>
          <p className="text-muted text-xs mt-1">
            {cluster.members.length} source
            {cluster.members.length !== 1 ? 's' : ''}
          </p>
        </div>
      </button>

      {/* Expanded members */}
      {expanded && (
        <div className="border-t border-line divide-y divide-line">
          {cluster.members.map((m, i) => {
            const src = sourceMap[m.source_id]
            return (
              <div key={i} className="px-5 py-4 space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  {src ? (
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-xs px-1.5 py-0.5 rounded bg-panel border border-line text-outlier hover:text-blue-300 transition-colors"
                    >
                      [{m.source_id}]
                    </a>
                  ) : (
                    <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-panel border border-line text-muted">
                      [{m.source_id}]
                    </span>
                  )}
                  <span
                    className={[
                      'text-xs font-medium capitalize',
                      STANCE_STYLES[m.stance],
                    ].join(' ')}
                  >
                    {m.stance}
                  </span>
                  <div className="flex items-center gap-1 ml-auto">
                    <span
                      className={[
                        'inline-block w-2 h-2 rounded-full',
                        CONFIDENCE_DOT[m.confidence],
                      ].join(' ')}
                    />
                    <span className="text-xs text-muted capitalize">
                      {m.confidence}
                    </span>
                  </div>
                </div>

                <p className="text-sm text-ink">{m.claim_text}</p>

                {m.supporting_quote && (
                  <blockquote className="border-l-2 border-line pl-3 text-xs text-muted italic leading-relaxed">
                    "{m.supporting_quote}"
                  </blockquote>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
