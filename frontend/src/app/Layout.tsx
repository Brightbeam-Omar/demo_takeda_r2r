import { Outlet, useLocation } from 'react-router-dom'
import { TermsProvider } from '../hooks/useTerms'
import { ErrorBoundary } from '../components/common/ErrorBoundary'
import { FeedbackButton } from '../components/shell/FeedbackButton'
import { pageTitle } from '../components/shell/nav'
import { Sidebar } from '../components/shell/Sidebar'
import { TopBar } from '../components/shell/TopBar'

export function Layout() {
  const { pathname } = useLocation()
  return (
    <TermsProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar title={pageTitle(pathname)} />
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
        <FeedbackButton />
      </div>
    </TermsProvider>
  )
}
