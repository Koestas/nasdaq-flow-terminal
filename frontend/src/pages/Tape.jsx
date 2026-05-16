import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { TableSkeleton } from '../components/LoadingSkeleton'
import { clsx } from 'clsx'

export default function Tape() {
  const { data, isLoading } = useQuery({
    queryKey: ['tape'],
    queryFn: () => apiFetch('/api/tape/live'),
    refetchInterval: 15_000,
  })

  const tape = data?.tape || []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-terminal-text">Options Tape</h1>
        <span className="text-xs text-terminal-muted">{tape.length} contracts</span>
      </div>

      <ErrorBoundary>
        <div className="card overflow-x-auto">
          {isLoading ? <TableSkeleton rows={10} /> : (
            <table className="w-full text-xs min-w-[600px]">
              <thead>
                <tr>
                  {['Contract', 'Exp', 'Strike', 'C/P', 'Last', 'Volume', 'Premium', 'Side Est', 'Signal', 'Size', 'Unusual'].map(h => (
                    <th key={h} className="table-header">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tape.map((c, i) => (
                  <tr key={i} className={clsx(
                    'hover:bg-terminal-border/20 transition-colors',
                    c.unusual && 'bg-terminal-yellow/5',
                    c.side === 'call' ? '' : 'opacity-90'
                  )}>
                    <td className={`table-cell font-semibold ${c.side === 'call' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {c.ticker} {c.strike} {c.side?.toUpperCase()}
                    </td>
                    <td className="table-cell text-terminal-muted">{c.expiration}</td>
                    <td className="table-cell">{c.strike}</td>
                    <td className={`table-cell font-bold ${c.side === 'call' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {c.side?.toUpperCase()[0]}
                    </td>
                    <td className="table-cell">{fmt.price(c.price)}</td>
                    <td className="table-cell">{fmt.num(c.volume)}</td>
                    <td className={`table-cell font-semibold ${c.side === 'call' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {fmt.premium(c.premium)}
                    </td>
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
                    <td className="table-cell">
                      {c.unusual ? <span className="text-terminal-yellow">⚡</span> : <span className="text-terminal-muted">—</span>}
                    </td>
                  </tr>
                ))}
                {tape.length === 0 && (
                  <tr><td colSpan={11} className="table-cell text-center text-terminal-muted py-8">No tape data yet</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </ErrorBoundary>

      <div className="card bg-terminal-card2 text-xs text-terminal-muted space-y-1">
        <div className="text-terminal-text font-semibold text-sm">Reading the Tape</div>
        <p><strong className="text-terminal-green">Repeated ask-side calls</strong> while QQQ holds VWAP = institutional buying, bullish momentum.</p>
        <p><strong className="text-terminal-red">Repeated ask-side puts</strong> while QQQ fails VWAP = institutional hedging/shorting, bearish pressure.</p>
        <p>Watch for <strong className="text-terminal-yellow">rhythm</strong> — one contract means little. Repeated buying at the same strike is meaningful.</p>
      </div>
    </div>
  )
}
