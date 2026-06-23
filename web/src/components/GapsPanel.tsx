import type { Gap } from '../types'

interface Props {
  gaps: Gap[]
}

export default function GapsPanel({ gaps }: Props) {
  if (gaps.length === 0) return null

  return (
    <div className="bg-panel border border-line rounded-xl p-6">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted mb-4">
        Research Gaps
      </h2>
      <div className="space-y-4">
        {gaps.map((gap, i) => (
          <div key={i} className="space-y-1">
            <p className="text-sm font-medium text-ink">{gap.description}</p>
            <p className="text-xs text-muted leading-relaxed">{gap.rationale}</p>
            {i < gaps.length - 1 && (
              <div className="border-b border-line mt-3" />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
