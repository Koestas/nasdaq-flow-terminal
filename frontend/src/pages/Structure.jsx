import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { CardSkeleton } from '../components/LoadingSkeleton'
import { clsx } from 'clsx'

function LevelRow({ label, value, status, highlight }) {
  return (
    <div className={clsx(
      'flex items-center justify-between py-3 px-4 border-b border-terminal-border/30 last:border-0',
      highlight && 'bg-terminal-blue/5'
    )}>
      <span className="text-terminal-muted text-sm">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-bold text-terminal-text">{value}</span>
        {status && (
          <span className={clsx('badge', status === 'above' || status === 'above_or' ? 'badge-green' : 'badge-red')}>
            {status === 'above_or' ? '↑ above OR' : status === 'below_or' ? '↓ below OR' : status === 'inside_or' ? '↔ inside OR' : status}
          </span>
        )}
      </div>
    </div>
  )
}

export default function Structure() {
  const { data, isLoading } = useQuery({
    queryKey: ['structure'],
    queryFn: () => apiFetch('/api/market/structure'),
    refetchInterval: 15_000,
  })

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-terminal-text">Market Structure</h1>

      <ErrorBoundary>
        {isLoading ? <CardSkeleton /> : (
          <div className="card">
            <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">Key Levels</div>
            <LevelRow label="Current Price" value={fmt.price(data?.price)} highlight />
            <LevelRow label="VWAP" value={fmt.price(data?.vwap)} status={data?.vwap_status} />
            <LevelRow label="Opening Range High" value={fmt.price(data?.opening_range_high)} />
            <LevelRow label="Opening Range Low" value={fmt.price(data?.opening_range_low)} />
            <LevelRow label="Day High" value={fmt.price(data?.day_high)} />
            <LevelRow label="Day Low" value={fmt.price(data?.day_low)} />
            <div className="mt-3 px-4 pt-3 border-t border-terminal-border/30">
              <div className="text-xs text-terminal-muted mb-1">OR Position</div>
              <span className={clsx('badge',
                data?.or_position === 'above_or' ? 'badge-green' :
                data?.or_position === 'below_or' ? 'badge-red' : 'badge-yellow'
              )}>
                {data?.or_position === 'above_or' ? '↑ Above Opening Range' :
                 data?.or_position === 'below_or' ? '↓ Below Opening Range' :
                 '↔ Inside Opening Range'}
              </span>
            </div>
          </div>
        )}
      </ErrorBoundary>

      <div className="card bg-terminal-card2 text-xs text-terminal-muted space-y-2">
        <div className="text-terminal-text font-semibold text-sm">About Market Structure</div>
        <p><strong className="text-terminal-text">VWAP</strong>: Volume Weighted Average Price. The most important intraday level. Institutions use VWAP as a benchmark — being above it is bullish, below is bearish.</p>
        <p><strong className="text-terminal-text">Opening Range</strong>: High and low of the first 15 minutes. Breakout above OR high = bullish momentum. Breakdown below OR low = bearish.</p>
        <p><strong className="text-terminal-yellow">For MNQ:</strong> Don't take flow signals in isolation. Bullish flow is worth much less if QQQ is below VWAP. Wait for structure confirmation.</p>
        <p>The best MNQ setups occur when: <br />1. Flow direction matches structure. <br />2. Price confirms (reclaims VWAP, holds OR, etc). <br />3. Leadership is aligned.</p>
      </div>
    </div>
  )
}
