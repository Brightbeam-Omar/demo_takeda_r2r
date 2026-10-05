export function Skeleton({ height = 'h-20', label }: { height?: string; label: string }) {
  return (
    <div
      role="status"
      aria-label={`Loading ${label}`}
      className={`${height} animate-pulse rounded-card bg-slate-200/70`}
      data-testid="skeleton"
    />
  )
}

export function ErrorState({ what, error, onRetry }: { what: string; error: unknown; onRetry: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <span>
        Could not load {what}: {error instanceof Error ? error.message : 'unknown error'}
      </span>
      <button type="button" className="rounded-chip border border-red-300 bg-white px-3 py-1 hover:bg-red-100" onClick={onRetry}>
        Retry
      </button>
    </div>
  )
}

export function EmptyState({ children }: { children: string }) {
  return <p className="rounded-card border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-slate-500">{children}</p>
}
