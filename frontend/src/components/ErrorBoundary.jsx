import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="card flex flex-col items-center justify-center min-h-[200px] text-center gap-3">
          <AlertTriangle className="text-terminal-yellow" size={28} />
          <div className="text-terminal-yellow font-semibold">This panel failed to load</div>
          <div className="text-terminal-muted text-xs max-w-xs">
            {this.state.error?.message || 'Unknown error'}
          </div>
          <button
            className="mt-2 flex items-center gap-1 text-xs text-terminal-blue hover:underline"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
