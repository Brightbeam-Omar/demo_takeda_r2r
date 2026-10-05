import { Outlet } from 'react-router-dom'
import { ErrorBoundary } from '../components/common/ErrorBoundary'
import { Sidebar } from '../components/shell/Sidebar'

export function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </div>
    </div>
  )
}
