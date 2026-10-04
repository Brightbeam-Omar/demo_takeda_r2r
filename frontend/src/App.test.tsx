import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import App from './App'

test('F01-FR-05: shows the placeholder page title', () => {
  render(<App />)
  expect(screen.getByRole('heading', { name: 'R2R Intelligence Demo' })).toBeInTheDocument()
})
