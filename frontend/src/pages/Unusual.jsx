import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { TableSkeleton } from '../components/LoadingSkeleton'
import { Zap } from 'lucide-react'
import { clsx } from 'clsx'

export default function Unusual() {
  const { data, isLoading } = useQuery({
    queryKey: ['unusual'],
    queryFn: () => apiFetch('/api/flow/unusual'),
    refetchInterval: 20_000,
  })

  const contracts = data?.contracts || []

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Zap size={18} className="text-terminal-yellow" />
        <h1 className="text-lg font-bold text-terminal-text">Unusual Activity</h1>
        {contracts.length > 0 && (
          <span className="badge-yellow">{contracts.length} flagged</span>
        )}
      </div>

      {!isLoading && contracts.length === 0 && (
        <div className="card text-center py-12 text-terminal-muted">
          <Zap size={32} className="mx-auto mb-3 opacity-30" />
          <div>No unusual activity detected</div>
          <div className="text-xs mt-1">Data refreshes every 20 seconds</div>
        </div>
      )}

      <ErrorBoundary>
        <div className="card overflow-x-auto">
          {isLoading ? <TableSkeleton rows={8} /> : contracts.length > 0 && (
            <table className="w-full text-xs min-w-[600px]">
              <thead>
                <tr>
                  {['Contract', 'Exp', 'Strike', 'C/P', 'Premium', 'Volume', 'OI', 'V/OI', 'Signal', 'Why Unusual'].map(h => (
                    <th key={h} className="table-header">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {contracts.map((c, i) => (
                  <tr key={i} className={clsx(
                    'hover:bg-terminal-border/20',
                    c.side === 'call' ? 'bg-terminal-green/5' : 'bg-terminal-red/5'
                  )}>
                    <td className="table-cell font-bold">
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
                    <td className="table-cell font-semibold text-terminal-yellow">{c.volume_oi_ratio?.toFixed(1)}x</td>
                    <td className="table-cell">
                      <span className={c.side === 'call' ? 'badge-green' : 'badge-red'}>
                        {c.side === 'call' ? '▲ Bullish' : '▼ Bearish'}
                      </span>
                    </td>
                    <td className="table-cell text-terminal-muted text-xs">
                      {c.unusual_reasons?.join(', ') || '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </ErrorBoundary>

      <div className="card bg-terminal-card2 text-xs text-terminal-muted space-y-1">
        <div className="text-terminal-text font-semibold text-sm">About Unusual Activity</div>
        <p>Flags: <strong className="text-terminal-text">Volume &gt; 2x Open Interest</strong> (new positioning, not normal hedging) or <strong className="text-terminal-text">Premium &gt; $500K</strong> (significant capital at risk).</p>
        <p><strong className="text-terminal-green">Unusual calls + QQQ above VWAP</strong> = high-quality bullish signal.</p>
        <p><strong className="text-terminal-red">Unusual puts + QQQ below VWAP</strong> = high-quality bearish signal.</p>
        <p><strong className="text-terminal-yellow">Divergence warning:</strong> If unusual activity goes against price direction, it may be large hedging — be cautious.</p>
      </div>
    </div>
  )
}
