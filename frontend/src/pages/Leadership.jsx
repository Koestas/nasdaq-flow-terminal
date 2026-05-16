import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { clsx } from 'clsx'

function StockCard({ stock }) {
  const isUp = stock.bullish
  const wt = Math.round((stock.nasdaq_weight || 0) * 100)
  return (
    <div className={clsx(
      'card border transition-all',
      isUp ? 'border-terminal-green/30 glow-green' : isUp === false ? 'border-terminal-red/30 glow-red' : 'border-terminal-border'
    )}>
      <div className="flex justify-between items-start">
        <div>
          <div className="font-bold text-terminal-text">{stock.symbol}</div>
          <div className="text-xs text-terminal-muted">NQ weight: ~{wt}%</div>
        </div>
        <div className="text-right">
          <div className="font-semibold text-terminal-text">{fmt.price(stock.price)}</div>
          <div className={clsx('font-bold text-sm', isUp ? 'text-terminal-green' : isUp === false ? 'text-terminal-red' : 'text-terminal-muted')}>
            {fmt.pct(stock.change_pct)}
          </div>
        </div>
      </div>
      <div className="mt-2">
        <div className={clsx('h-1 rounded-full', isUp ? 'bg-terminal-green' : isUp === false ? 'bg-terminal-red' : 'bg-terminal-muted')} style={{ width: `${Math.min(100, Math.abs(stock.change_pct || 0) * 10)}%` }} />
      </div>
    </div>
  )
}

export default function Leadership() {
  const { data, isLoading } = useQuery({
    queryKey: ['leadership'],
    queryFn: () => apiFetch('/api/market/leadership'),
    refetchInterval: 30_000,
  })

  const stocks = data?.stocks || []
  const green = stocks.filter(s => s.bullish).length
  const red = stocks.filter(s => s.bullish === false).length
  const breadth = stocks.length ? Math.round(green / stocks.length * 100) : 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-terminal-text">Leadership Basket</h1>
        {!isLoading && stocks.length > 0 && (
          <div className="flex items-center gap-3 text-sm">
            <span className="text-terminal-green font-bold">{green} Green</span>
            <span className="text-terminal-red font-bold">{red} Red</span>
            <span className={clsx('badge', breadth >= 60 ? 'badge-green' : breadth <= 40 ? 'badge-red' : 'badge-yellow')}>
              {breadth}% bullish
            </span>
          </div>
        )}
      </div>

      {/* Breadth bar */}
      {!isLoading && stocks.length > 0 && (
        <div className="card">
          <div className="text-xs text-terminal-muted mb-2">Breadth: {green}/{stocks.length} green</div>
          <div className="h-2 bg-terminal-border rounded-full overflow-hidden">
            <div className="h-full bg-terminal-green rounded-full transition-all" style={{ width: `${breadth}%` }} />
          </div>
        </div>
      )}

      <ErrorBoundary>
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {isLoading
            ? Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="card h-24 animate-pulse bg-terminal-border/20" />
              ))
            : stocks.map(stock => <StockCard key={stock.symbol} stock={stock} />)
          }
        </div>
      </ErrorBoundary>

      <div className="card bg-terminal-card2 text-xs text-terminal-muted space-y-1">
        <div className="text-terminal-text font-semibold text-sm">About Leadership</div>
        <p>NVDA, MSFT, AAPL, META, and AMZN are the highest-weight Nasdaq-100 names and most influence MNQ direction.</p>
        <p><strong className="text-terminal-green">7+/10 green</strong> with QQQ above VWAP = strong bullish environment for MNQ longs.</p>
        <p><strong className="text-terminal-red">3 or fewer green</strong> = weak breadth even if QQQ looks okay on the surface.</p>
        <p>Always check if the heavyweights (NVDA, MSFT, AAPL) are participating before entering trend trades.</p>
      </div>
    </div>
  )
}
