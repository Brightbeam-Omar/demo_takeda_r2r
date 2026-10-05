import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

export class ErrorBoundary extends Component<Props, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI error', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" className="m-6 rounded-card border border-red-200 bg-red-50 p-6 text-red-800">
        <p className="font-semibold">Something went wrong on this page.</p>
        <p className="mt-1 text-sm">{this.state.error.message}</p>
        <button
          type="button"
          className="mt-3 rounded-chip bg-red-600 px-3 py-1.5 text-white hover:bg-red-700"
          onClick={() => this.setState({ error: null })}
        >
          Try again
        </button>
      </div>
    )
  }
}
