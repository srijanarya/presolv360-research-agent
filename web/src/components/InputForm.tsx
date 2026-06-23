import React, { useState } from 'react'

interface Props {
  onSubmit: (topic: string, urls: string[], adversarial: boolean) => void
  disabled: boolean
}

const MIN_URLS = 3
const MAX_URLS = 5

export default function InputForm({ onSubmit, disabled }: Props) {
  const [topic, setTopic] = useState('')
  const [urls, setUrls] = useState<string[]>(['', '', ''])
  const [adversarial, setAdversarial] = useState(false)

  const setUrl = (index: number, value: string) => {
    setUrls((prev) => {
      const next = [...prev]
      next[index] = value
      return next
    })
  }

  const addUrl = () => {
    if (urls.length < MAX_URLS) setUrls((prev) => [...prev, ''])
  }

  const removeUrl = (index: number) => {
    if (urls.length > MIN_URLS) {
      setUrls((prev) => prev.filter((_, i) => i !== index))
    }
  }

  const nonEmptyUrls = urls.filter((u) => u.trim() !== '')
  const canSubmit =
    !disabled &&
    topic.trim() !== '' &&
    nonEmptyUrls.length >= MIN_URLS &&
    nonEmptyUrls.length <= MAX_URLS

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    onSubmit(topic.trim(), nonEmptyUrls, adversarial)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-panel border border-line rounded-xl p-8 space-y-6 w-full max-w-2xl mx-auto"
    >
      <div>
        <h1 className="text-2xl font-semibold text-ink mb-1">
          Cross-Source Research
        </h1>
        <p className="text-muted text-sm">
          Enter a topic and 3–5 source URLs to analyse across sources.
        </p>
      </div>

      {/* Topic */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-muted uppercase tracking-wider">
          Topic
        </label>
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. The effectiveness of mRNA vaccines"
          disabled={disabled}
          className="w-full bg-bg border border-line rounded-lg px-4 py-2.5 text-ink placeholder:text-muted focus:outline-none focus:border-outlier disabled:opacity-50 transition-colors"
        />
      </div>

      {/* URL rows */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-muted uppercase tracking-wider">
          Source URLs{' '}
          <span className="normal-case font-normal">
            ({MIN_URLS}–{MAX_URLS} required)
          </span>
        </label>
        <div className="space-y-2">
          {urls.map((url, i) => (
            <div key={i} className="flex gap-2 items-center">
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(i, e.target.value)}
                placeholder={`https://example.com/article-${i + 1}`}
                disabled={disabled}
                className="flex-1 bg-bg border border-line rounded-lg px-4 py-2.5 text-ink placeholder:text-muted focus:outline-none focus:border-outlier disabled:opacity-50 transition-colors"
              />
              <button
                type="button"
                onClick={() => removeUrl(i)}
                disabled={disabled || urls.length <= MIN_URLS}
                aria-label={`Remove URL ${i + 1}`}
                className="w-8 h-8 flex items-center justify-center rounded-lg border border-line text-muted hover:border-red-500 hover:text-red-400 disabled:opacity-30 transition-colors flex-shrink-0"
              >
                ×
              </button>
            </div>
          ))}
        </div>
        {urls.length < MAX_URLS && (
          <button
            type="button"
            onClick={addUrl}
            disabled={disabled}
            className="text-sm text-outlier hover:text-blue-300 disabled:opacity-50 transition-colors"
          >
            + Add URL
          </button>
        )}
      </div>

      {/* Adversarial toggle */}
      <label className="flex items-center gap-3 cursor-pointer select-none">
        <div className="relative">
          <input
            type="checkbox"
            checked={adversarial}
            onChange={(e) => setAdversarial(e.target.checked)}
            disabled={disabled}
            className="sr-only peer"
          />
          <div className="w-10 h-6 rounded-full bg-bg border border-line peer-checked:bg-outlier peer-checked:border-outlier transition-colors" />
          <div className="absolute top-1 left-1 w-4 h-4 rounded-full bg-muted peer-checked:bg-white peer-checked:translate-x-4 transition-all" />
        </div>
        <span className="text-sm text-muted">
          Adversarial mode{' '}
          <span className="text-ink/50">(stress-test every claim)</span>
        </span>
      </label>

      {/* Submit */}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full py-3 rounded-lg font-medium text-sm transition-all bg-outlier text-white hover:bg-blue-400 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {disabled ? 'Running…' : 'Run Research'}
      </button>
    </form>
  )
}
