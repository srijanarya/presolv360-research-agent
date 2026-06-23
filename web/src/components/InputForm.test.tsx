import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InputForm from './InputForm'

describe('InputForm', () => {
  it('submit button is disabled with fewer than 3 URLs', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<InputForm onSubmit={onSubmit} disabled={false} />)

    // Fill topic
    await user.type(screen.getByPlaceholderText(/effectiveness of mRNA/i), 'Test topic')

    // Fill only 2 URL fields (form starts with 3 empty rows)
    const urlInputs = screen.getAllByPlaceholderText(/https:\/\/example\.com/i)
    await user.type(urlInputs[0], 'https://example.com/a')
    await user.type(urlInputs[1], 'https://example.com/b')
    // leave urlInputs[2] empty

    const btn = screen.getByRole('button', { name: /run research/i })
    expect(btn).toBeDisabled()
  })

  it('submit button is enabled when topic and 3 valid URLs are filled', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<InputForm onSubmit={onSubmit} disabled={false} />)

    await user.type(screen.getByPlaceholderText(/effectiveness of mRNA/i), 'Test topic')

    const urlInputs = screen.getAllByPlaceholderText(/https:\/\/example\.com/i)
    await user.type(urlInputs[0], 'https://example.com/a')
    await user.type(urlInputs[1], 'https://example.com/b')
    await user.type(urlInputs[2], 'https://example.com/c')

    const btn = screen.getByRole('button', { name: /run research/i })
    expect(btn).not.toBeDisabled()
  })

  it('calls onSubmit with topic, urls, and adversarial=false by default', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<InputForm onSubmit={onSubmit} disabled={false} />)

    await user.type(screen.getByPlaceholderText(/effectiveness of mRNA/i), 'My topic')

    const urlInputs = screen.getAllByPlaceholderText(/https:\/\/example\.com/i)
    await user.type(urlInputs[0], 'https://example.com/a')
    await user.type(urlInputs[1], 'https://example.com/b')
    await user.type(urlInputs[2], 'https://example.com/c')

    await user.click(screen.getByRole('button', { name: /run research/i }))

    expect(onSubmit).toHaveBeenCalledOnce()
    expect(onSubmit).toHaveBeenCalledWith(
      'My topic',
      ['https://example.com/a', 'https://example.com/b', 'https://example.com/c'],
      false,
    )
  })

  it('submit is disabled when the disabled prop is true', () => {
    const onSubmit = vi.fn()
    render(<InputForm onSubmit={onSubmit} disabled={true} />)
    expect(screen.getByRole('button', { name: /running/i })).toBeDisabled()
  })
})
