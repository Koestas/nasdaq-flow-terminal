import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { CheckCircle, XCircle, AlertTriangle, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'

function StatusCard({ name, status, message, features }) {
  const ok = status === 'ok' || status === 'ready'
  const notConfigured = status === 'not_configured'
  return (
    <div className={clsx('card border', ok ? 'border-terminal-green/30' : notConfigured ? 'border-terminal-muted/30' : 'border-terminal-red/30')}>
      <div className="flex items-center gap-2 mb-2">
        {ok ? <CheckCircle size={16} className="text-terminal-green" /> :
         notConfigured ? <AlertTriangle size={16} className="text-terminal-yellow" /> :
         <XCircle size={16} className="text-terminal-red" />}
        <span className="font-semibold text-terminal-text capitalize">{name}</span>
        <span className={clsx('badge ml-auto', ok ? 'badge-green' : notConfigured ? 'badge-yellow' : 'badge-red')}>
          {status}
        </span>
      </div>
      {message && <div className="text-xs text-terminal-muted">{message}</div>}
      {features?.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {features.map(f => <span key={f} className="badge-muted">{f}</span>)}
        </div>
      )}
    </div>
  )
}

export default function Diagnostics() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ['providers'],
    queryFn: () => apiFetch('/api/providers/status'),
    refetchInterval: 60_000,
  })

  const providers = data?.providers || {}

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-terminal-text">Provider Diagnostics</h1>
        <div className="flex items-center gap-2">
          {dataUpdatedAt && <span className="text-xs text-terminal-muted">Updated {fmt.timeAgo(new Date(dataUpdatedAt).toISOString())}</span>}
          <button onClick={() => refetch()} className="flex items-center gap-1 text-xs text-terminal-blue hover:underline">
            <RefreshCw size={11} /> Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => <div key={i} className="card h-28 animate-pulse bg-terminal-border/20" />)
        ) : (
          <>
            {providers.yahoo && (
              <StatusCard
                name="Yahoo Finance"
                status={providers.yahoo.status}
                message={providers.yahoo.message}
                features={providers.yahoo.features}
              />
            )}
            {providers.schwab && (
              <StatusCard
                name="Schwab API"
                status={providers.schwab.status}
                message={providers.schwab.message}
              />
            )}
            {providers.sqlite && (
              <StatusCard
                name="SQLite Database"
                status={providers.sqlite.status}
                message={`${providers.sqlite.path} · ${(providers.sqlite.size_bytes / 1024).toFixed(1)} KB`}
              />
            )}
          </>
        )}
      </div>

      <div className="card bg-terminal-card2 space-y-3 text-xs">
        <div className="text-terminal-text font-semibold text-sm">Setup Guide</div>
        <div>
          <div className="text-terminal-green font-semibold mb-1">Yahoo Finance (active by default)</div>
          <div className="text-terminal-muted">Free data via yfinance. No API key needed. Options chain data may be delayed 15 minutes.</div>
        </div>
        <div>
          <div className="text-terminal-yellow font-semibold mb-1">Charles Schwab API (optional)</div>
          <div className="text-terminal-muted">Copy <code className="bg-terminal-border px-1 rounded">.env.example</code> to <code className="bg-terminal-border px-1 rounded">.env</code> and add your Schwab developer credentials.</div>
          <div className="text-terminal-muted mt-1">Get keys at <span className="text-terminal-blue">developer.schwab.com</span> — free for Schwab account holders. Provides real-time quotes, options chains, and futures data.</div>
        </div>
        <div>
          <div className="text-terminal-blue font-semibold mb-1">Databento (future)</div>
          <div className="text-terminal-muted">~$20/mo for real-time MNQ/NQ futures data. Best option for actual futures orderflow and DOM data.</div>
        </div>
      </div>
    </div>
  )
}
