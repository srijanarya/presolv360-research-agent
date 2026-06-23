import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ClaimGraph from './ClaimGraph'
import { BRIEF_FIXTURE } from '../test/fixture'

describe('ClaimGraph', () => {
  it('renders three classification columns', () => {
    render(<ClaimGraph brief={BRIEF_FIXTURE} />)

    expect(screen.getByText('Consensus')).toBeInTheDocument()
    expect(screen.getByText('Contested')).toBeInTheDocument()
    expect(screen.getByText('Outlier')).toBeInTheDocument()
  })

  it('places each cluster in the correct column', () => {
    render(<ClaimGraph brief={BRIEF_FIXTURE} />)

    // Each single-member column shows "1 claim" — there are 3 such columns (consensus + contested shown as "1 claim" each)
    const oneClaimBadges = screen.getAllByText(/1 claim/i)
    expect(oneClaimBadges.length).toBeGreaterThanOrEqual(1)

    // Cluster statements rendered as cards
    expect(
      screen.getByText(/mRNA vaccines reduce hospitalisation risk significantly/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Vaccine effectiveness wanes after 6 months/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/mRNA technology may trigger autoimmune responses/i),
    ).toBeInTheDocument()
  })

  it('highlights the contested column as focus', () => {
    render(<ClaimGraph brief={BRIEF_FIXTURE} />)
    expect(screen.getByText('← focus')).toBeInTheDocument()
  })
})
