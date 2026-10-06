import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './app/Layout'
import { ToastProvider } from './components/common/Toasts'
import { ADMIN, VIEWS } from './components/shell/nav'
import { AdminFeedback } from './pages/AdminFeedback'
import { Audit } from './pages/Audit'
import { SchemaReference } from './pages/admin/SchemaReference'
import { TeamDashboard } from './pages/admin/TeamDashboard'
import { SyncStatus } from './pages/admin/SyncStatus'
import { WebhookStatus } from './pages/admin/WebhookStatus'
import { Overview } from './pages/Overview'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { Reports } from './pages/Reports'
import { onPersonaChange } from './state/persona'

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: false },
    },
  })

// Pages that exist. Every other menu item renders a titled placeholder (F15-FR-02, OQ-081).
const BUILT = new Set(['/overview', '/reports', '/admin/audit', '/admin/team', '/admin/schema', '/admin/sync', '/admin/webhooks', '/admin/feedback'])
const PLACEHOLDERS = [...VIEWS, ...ADMIN].filter((item) => !BUILT.has(item.to))

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
              <Route path="/reports" element={<Reports />} />
              <Route path="/admin/team" element={<TeamDashboard />} />
              <Route path="/admin/schema" element={<SchemaReference />} />
              <Route path="/admin/sync" element={<SyncStatus />} />
              <Route path="/admin/webhooks" element={<WebhookStatus />} />
              <Route path="/admin/audit" element={<Audit />} />
              <Route path="/sync" element={<Navigate to="/admin/sync" replace />} />
              <Route path="/sync/webhook" element={<Navigate to="/admin/webhooks" replace />} />
              <Route path="/audit" element={<Navigate to="/admin/audit" replace />} />
              <Route path="/admin/feedback" element={<AdminFeedback />} />
              {PLACEHOLDERS.map((item) => (
                <Route
                  key={item.to}
                  path={item.to}
                  element={<PlaceholderPage title={item.label} note={item.coming ?? 'Coming soon'} />}
                />
              ))}
              <Route path="*" element={<Navigate to="/overview" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}
