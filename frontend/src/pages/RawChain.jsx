import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { TableSkeleton } from '../components/LoadingSkeleton'
import { useState } from 'react'
import { clsx } from 'clsx'

export default function RawChain() {
  const [expiration, setExpiration] = useState('')
  const [side, setSide] = useState('')
  const [minVol, setMinVol] = useState(0)
  const [page, setPage] = useState(1)

  const params = new URLSearchParams({ page, per_page: 50 })
  if (expiration) params.set('expiration', expiration)
  if (side) params.set('side', side)
  if (minVol > 0) params.set('min_volume', minVol)

  const { data, isLoading } = useQuery({
    queryKey: ['raw-chain', expiration, side, minVol, page],
    queryFn: () => apiFetch(`/api/flow/raw-chain?${params}`),
  })

  const contracts = data?.contracts || []
  const expirations = data?.expirations || []
  const total = data?.total || 0

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-terminal-text">Raw Options Chain — QQQ</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div>
          <label className="text-xs text-terminal-muted mr-1">Expiration</label>
          <select
            value={expiration}
            onChange={e => { setExpiration(e.target.value); setPage(1) }}
            className="bg-terminal-card border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text"
          >
            <option value="">All</option>
            {expirations.map(exp => <option key={exp} value={exp}>{exp}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-terminal-muted mr-1">Side</label>
          <select
            value={side}
            onChange={e => { setSide(e.target.value); setPage(1) }}
            className="bg-terminal-card border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text"
          >
            <option value="">Both</option>
            <option value="call">Calls</option>
            <option value="put">Puts</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-terminal-muted mr-1">Min Volume</label>
          <input
            type="number"
            value={minVol}
            onChange={e => { setMinVol(Number(e.target.value)); setPage(1) }}
            className="bg-terminal-card border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text w-20"
            min={0}
          />
        </div>
        <span className="text-xs text-terminal-muted ml-auto">{total} contracts</span>
      </div>

      <ErrorBoundary>
        <div className="card overflow-x-auto">
          {isLoading ? <TableSkeleton rows={12} /> : (
            <table className="w-full text-xs min-w-[800px]">
              <thead>
                <tr>
                  {['Exp', 'Strike', 'C/P', 'Last', 'Bid', 'Ask', 'Volume', 'OI', 'IV', 'Delta', 'Gamma', 'Premium', 'V/OI', 'Unusual'].map(h => (
                    <th key={h} className="table-header">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {contracts.map((c, i) => (
                  <tr key={i} className={clsx(
                    'hover:bg-terminal-border/20',
                    c.unusual_flag && 'bg-terminal-yellow/5',
                    c.side === 'call' ? 'border-l-2 border-l-terminal-green/20' : 'border-l-2 border-l-terminal-red/20'
                  )}>
                    <td className="table-cell text-terminal-muted">{c.expiration}</td>
                    <td className="table-cell font-semibold">{c.strike}</td>
                    <td className={`table-cell font-bold ${c.side === 'call' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {c.side?.toUpperCase()[0]}
                    </td>
                    <td className="table-cell">{fmt.price(c.lastPrice)}</td>
                    <td className="table-cell text-terminal-muted">{c.bid?.toFixed(2)}</td>
                    <td className="table-cell text-terminal-muted">{c.ask?.toFixed(2)}</td>
                    <td className="table-cell">{fmt.num(c.volume)}</td>
                    <td className="table-cell text-terminal-muted">{fmt.num(c.openInterest)}</td>
                    <td className="table-cell">{c.impliedVolatility ? `${(c.impliedVolatility * 100).toFixed(1)}%` : '--'}</td>
                    <td className="table-cell">{c.delta?.toFixed(3) ?? '--'}</td>
                    <td className="table-cell">{c.gamma?.toFixed(4) ?? '--'}</td>
                    <td className={`table-cell font-semibold ${c.side === 'call' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {fmt.premium(c.estimated_premium)}
                    </td>
                    <td className="table-cell">{c.volume_oi_ratio?.toFixed(1)}x</td>
                    <td className="table-cell">
                      {c.unusual_flag ? <span className="badge-yellow">⚡</span> : <span className="text-terminal-muted">—</span>}
                    </td>
                  </tr>
                ))}
                {contracts.length === 0 && (
                  <tr><td colSpan={14} className="table-cell text-center text-terminal-muted py-8">No contracts</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </ErrorBoundary>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center gap-2 justify-center text-xs">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1 rounded bg-terminal-border text-terminal-muted disabled:opacity-40">
            ← Prev
          </button>
          <span className="text-terminal-muted">Page {page} of {Math.ceil(total / 50)}</span>
          <button disabled={page >= Math.ceil(total / 50)} onClick={() => setPage(p => p + 1)} className="px-3 py-1 rounded bg-terminal-border text-terminal-muted disabled:opacity-40">
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
