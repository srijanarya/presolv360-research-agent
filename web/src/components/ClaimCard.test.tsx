import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ClaimCard from './ClaimCard'
import { BRIEF_FIXTURE } from '../test/fixture'

describe('ClaimCard', () => {
  const contestedCluster = BRIEF_FIXTURE.claim_clusters.find(
    (c) => c.classification === 'contested',
  )!

  it('renders the cluster statement', () => {
    render(<ClaimCard cluster={contestedCluster} sources={BRIEF_FIXTURE.sources} />)
    expect(
      screen.getByText(/Vaccine effectiveness wanes after 6 months/i),
    ).toBeInTheDocument()
  })

  it('is collapsed by default — supporting_quote not visible', () => {
    render(<ClaimCard cluster={contestedCluster} sources={BRIEF_FIXTURE.sources} />)
    expect(
      screen.queryByText(/Six-month follow-up shows declining efficacy/i),
    ).not.toBeInTheDocument()
  })

  it('expands on click to reveal supporting_quote and source citation', async () => {
    const user = userEvent.setup()
    render(<ClaimCard cluster={contestedCluster} sources={BRIEF_FIXTURE.sources} />)

    const header = screen.getByRole('button')
    await user.click(header)

    // supporting quote is visible
    expect(
      screen.getByText(/Six-month follow-up shows declining efficacy/i),
    ).toBeInTheDocument()

    // Source citation link [s1]
    expect(screen.getByText('[s1]')).toBeInTheDocument()

    // Stance label
    expect(screen.getAllByText(/supports/i).length).toBeGreaterThan(0)
  })

  it('collapses again on second click', async () => {
    const user = userEvent.setup()
    render(<ClaimCard cluster={contestedCluster} sources={BRIEF_FIXTURE.sources} />)

    const header = screen.getByRole('button')
    await user.click(header)
    await user.click(header)

    expect(
      screen.queryByText(/Six-month follow-up shows declining efficacy/i),
    ).not.toBeInTheDocument()
  })
})
