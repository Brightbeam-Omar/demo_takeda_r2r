import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { ToastProvider } from './components/common/Toasts'

/** Renders a component that uses the query client or toasts (the Explain popover does). */
export function renderWithProviders(ui: ReactElement) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ToastProvider>{ui}</ToastProvider>
    </QueryClientProvider>,
  )
}
