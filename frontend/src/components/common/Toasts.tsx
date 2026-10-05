import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

interface Toast {
  id: number
  text: string
  tone: 'info' | 'error'
}

interface ToastApi {
  notify: (text: string, tone?: Toast['tone']) => void
}

const ToastContext = createContext<ToastApi>({ notify: () => undefined })
let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const notify = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = nextId++
    setToasts((current) => [...current, { id, text, tone }])
    setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4000)
  }, [])
  const api = useMemo(() => ({ notify }), [notify])
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex flex-col gap-2" aria-live="polite">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={`rounded-card px-4 py-2 text-sm text-white shadow-lg ${toast.tone === 'error' ? 'bg-red-700' : 'bg-slate-800'}`}
          >
            {toast.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  return useContext(ToastContext)
}
