import type { Brief, Classification } from '../types'
import ClaimCard from './ClaimCard'

interface Props {
  brief: Brief
}

interface Column {
  key: Classification
  label: string
  accent: string
  border: string
  bg: string
  featured: boolean
}

const COLUMNS: Column[] = [
  {
    key: 'consensus',
    label: 'Consensus',
    accent: 'text-consensus',
    border: 'border-consensus/30',
    bg: 'bg-consensus/5',
    featured: false,
  },
  {
    key: 'contested',
    label: 'Contested',
    accent: 'text-contested',
    border: 'border-contested/50',
    bg: 'bg-contested/10',
    featured: true,
  },
  {
    key: 'outlier',
    label: 'Outlier',
    accent: 'text-outlier',
    border: 'border-outlier/30',
    bg: 'bg-outlier/5',
    featured: false,
  },
]

export default function ClaimGraph({ brief }: Props) {
  return (
    <div className="w-full">
      <h2 className="text-lg font-semibold text-ink mb-4">Claim Graph</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-start">
        {COLUMNS.map((col) => {
          const clusters = brief.claim_clusters.filter(
            (c) => c.classification === col.key,
          )
          return (
            <div
              key={col.key}
              className={[
                'rounded-xl border p-4 space-y-3',
                col.bg,
                col.border,
                col.featured ? 'ring-1 ring-contested/40 shadow-lg' : '',
              ].join(' ')}
            >
              <div className="flex items-center justify-between mb-1">
                <h3
                  className={[
                    'text-sm font-semibold uppercase tracking-wider',
                    col.accent,
                  ].join(' ')}
                >
                  {col.label}
                  {col.featured && (
                    <span className="ml-2 text-xs normal-case font-normal text-contested/70">
                      ← focus
                    </span>
                  )}
                </h3>
                <span className="text-xs text-muted">
                  {clusters.length} claim{clusters.length !== 1 ? 's' : ''}
                </span>
              </div>

              {clusters.length === 0 ? (
                <p className="text-muted text-xs py-4 text-center">
                  No {col.key} claims found
                </p>
              ) : (
                clusters.map((cluster) => (
                  <ClaimCard
                    key={cluster.id}
                    cluster={cluster}
                    sources={brief.sources}
                  />
                ))
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
