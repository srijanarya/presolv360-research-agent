import { jsonUrl, markdownUrl, htmlUrl } from '../api'

interface Props {
  runId: string
}

interface ExportButton {
  label: string
  href: string
  title: string
}

export default function ExportBar({ runId }: Props) {
  const buttons: ExportButton[] = [
    { label: 'JSON', href: jsonUrl(runId), title: 'Download raw brief JSON' },
    { label: 'Markdown', href: markdownUrl(runId), title: 'Download Markdown report' },
    { label: 'HTML', href: htmlUrl(runId), title: 'View HTML report' },
  ]

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <span className="text-xs text-muted uppercase tracking-wider">
        Export:
      </span>
      {buttons.map(({ label, href, title }) => (
        <a
          key={label}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          title={title}
          className="px-4 py-1.5 rounded-lg border border-line text-sm text-muted hover:text-ink hover:border-outlier/50 transition-colors"
        >
          {label}
        </a>
      ))}
    </div>
  )
}
