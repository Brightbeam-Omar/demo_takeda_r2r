import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './app/Layout'
import { ToastProvider } from './components/common/Toasts'
import { Audit } from './pages/Audit'
import { Overview } from './pages/Overview'
import { Sync } from './pages/Sync'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { useEffect, useState } from 'react'
import { onPersonaChange } from './state/persona'

const createQueryClient = () =>
  new QueryClient({ defaultOptions: { queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: false } } })

export default function App() {
  const [queryClient] = useState(createQueryClient)
  useEffect(() => onPersonaChange(() => void queryClient.invalidateQueries()), [queryClient])
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/overview" replace />} />
              <Route path="/overview" element={<Overview />} />
              <Route path="/agents" element={<PlaceholderPage title="Agents" feature="F12" />} />
              <Route path="/sync" element={<Sync />} />
              <Route path="/audit" element={<Audit />} />
              <Route path="/admin" element={<PlaceholderPage title="Admin" feature="F11" />} />
              <Route path="*" element={<Navigate to="/overview" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}
