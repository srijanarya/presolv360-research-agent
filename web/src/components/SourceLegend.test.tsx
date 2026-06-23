import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SourceLegend from './SourceLegend'
import { BRIEF_FIXTURE } from '../test/fixture'

describe('SourceLegend', () => {
  it('renders all sources', () => {
    render(<SourceLegend sources={BRIEF_FIXTURE.sources} />)

    expect(screen.getByText('Study A: High Efficacy')).toBeInTheDocument()
    expect(screen.getByText('Study B: Moderate Efficacy')).toBeInTheDocument()
    expect(screen.getByText('Paywalled Journal')).toBeInTheDocument()
  })

  it('shows a failed (paywalled) source with correct badge', () => {
    render(<SourceLegend sources={BRIEF_FIXTURE.sources} />)

    // The paywalled source shows a "Paywall" badge
    expect(screen.getByText('Paywall')).toBeInTheDocument()
  })

  it('shows the ok badge for successful sources', () => {
    render(<SourceLegend sources={BRIEF_FIXTURE.sources} />)

    const okBadges = screen.getAllByText('OK')
    expect(okBadges.length).toBe(2)
  })

  it('shows error text for failed sources that have an error field', () => {
    render(<SourceLegend sources={BRIEF_FIXTURE.sources} />)
    expect(screen.getByText('Access denied')).toBeInTheDocument()
  })
})
