import { render } from '@testing-library/react'
import { expect, test } from 'vitest'
import { highlight } from './highlight'

const html = (text: string, query: string) => {
  const { container } = render(<span>{highlight(text, query)}</span>)
  return container.innerHTML
}

test('F18-FR-05: every case-insensitive match is wrapped in <mark>, keeping the original casing', () => {
  expect(html('Batch b2077 and B2077', 'b2077')).toContain('<mark class="rounded-sm bg-yellow-200 px-0 text-inherit">b2077</mark>')
  expect(html('Batch b2077 and B2077', 'b2077').match(/<mark/g)).toHaveLength(2)
  expect(html('Batch b2077 and B2077', 'b2077')).toContain('>B2077</mark>')
})

test('F18-FR-05: an empty query, a blank query or no match leaves the text alone', () => {
  expect(html('B2077', '')).toBe('<span>B2077</span>')
  expect(html('B2077', '   ')).toBe('<span>B2077</span>')
  expect(html('B2077', 'zzz')).toBe('<span>B2077</span>')
  expect(html('', 'a')).toBe('<span></span>')
})

test('F18-FR-05: text around and between matches is kept in order', () => {
  expect(document.createElement('div').textContent).toBe('')
  const { container } = render(<span>{highlight('aXbXc', 'x')}</span>)
  expect(container.textContent).toBe('aXbXc')
  expect(container.querySelectorAll('mark')).toHaveLength(2)
})
