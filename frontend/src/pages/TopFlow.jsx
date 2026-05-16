import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { TableSkeleton } from '../components/LoadingSkeleton'
import { useState } from 'react'
import { clsx } from 'clsx'

export default function TopFlow() {
  const [filter, setFilter] = useState('all')
  const { data, isLoading } = useQuery({
    queryKey: ['top-flow'],
    queryFn: () => apiFetch('/api/flow/top?limit=30'),
    refetchInterval: 20_000,
  })

  const contracts = (data?.contracts || []).filter(c => filter === 'all' || c.side === filter)

  const filters = [
    { id: 'all', label: 'All' },
    { id: 'call', label: 'Calls Only' },
    { id: 'put', label: 'Puts Only' },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-terminal-text">Top Flow</h1>
        <div className="flex gap-1">
          {filters.map(f => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={clsx('px-3 py-1 rounded text-xs transition-colors', filter === f.id
                ? 'bg-terminal-blue text-white'
                : 'bg-terminal-border text-terminal-muted hover:text-terminal-text'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <ErrorBoundary>
        <div className="card overflow-x-auto">
          {isLoading ? <TableSkeleton rows={10} /> : (
            <table className="w-full text-xs min-w-[700px]">
              <thead>
                <tr>
                  {['Contract', 'Exp', 'Strike', 'C/P', 'Premium', 'Volume', 'OI', 'V/OI', 'Side Est', 'Signal', 'Size'].map(h => (
                    <th key={h} className="table-header">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {contracts.map((c, i) => (
                  <tr key={i} className={clsx('hover:bg-terminal-border/20 transition-colors',
                    c.side === 'call' ? 'bg-terminal-green/3' : 'bg-terminal-red/3'
                  )}>
                    <td className="table-cell font-semibold">
                      QQQ {c.strike} {c.side?.toUpperCase()}
                    </td>
                    <td className="table-cell text-terminal-muted">{c.expiration}</td>
                    <td className="table-cell">{c.strike}</td>
                    <td className={`table-cell font-bold ${c.side === 'call' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {c.side?.toUpperCase()}
                    </td>
                    <td className={`table-cell font-semibold ${c.side === 'call' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {fmt.premium(c.estimated_premium)}
                    </td>
                    <td className="table-cell">{fmt.num(c.volume)}</td>
                    <td className="table-cell text-terminal-muted">{fmt.num(c.openInterest)}</td>
                    <td className="table-cell">{c.volume_oi_ratio?.toFixed(1)}x</td>
                    <td className="table-cell text-terminal-muted">{c.side_estimate}</td>
                    <td className="table-cell">
                      <span className={c.signal === 'bullish' ? 'badge-green' : 'badge-red'}>
                        {c.signal === 'bullish' ? '▲ Bull' : '▼ Bear'}
                      </span>
                    </td>
                    <td className="table-cell">
                      <span className={clsx('badge',
                        c.premium_size === 'whale' ? 'bg-terminal-purple/20 text-terminal-purple border border-terminal-purple/30' :
                        c.premium_size === 'large' ? 'badge-yellow' :
                        c.premium_size === 'medium' ? 'badge-blue' : 'badge-muted'
                      )}>
                        {c.premium_size}
                      </span>
                    </td>
                  </tr>
                ))}
                {contracts.length === 0 && (
                  <tr><td colSpan={11} className="table-cell text-center text-terminal-muted py-8">No contracts found</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </ErrorBoundary>

      <div className="card bg-terminal-card2 text-xs text-terminal-muted space-y-1">
        <div className="text-terminal-text font-semibold text-sm">How to Use Top Flow</div>
        <p>These are the largest options trades by premium. "Whale" = $5M+, "Large" = $1M+.</p>
        <p><strong className="text-terminal-green">Ask-side calls</strong> while QQQ is above VWAP = bullish confirmation.</p>
        <p><strong className="text-terminal-red">Ask-side puts</strong> while QQQ is below VWAP = bearish confirmation.</p>
        <p><strong className="text-terminal-yellow">Warning:</strong> Large flow can be hedging or institutional position management — always confirm with price structure.</p>
      </div>
    </div>
  )
}
