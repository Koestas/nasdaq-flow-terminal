import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { TableSkeleton } from '../components/LoadingSkeleton'
import { useState } from 'react'
import { clsx } from 'clsx'
import { ExternalLink } from 'lucide-react'

export default function News() {
  const [filter, setFilter] = useState('all')
  const { data, isLoading } = useQuery({
    queryKey: ['news'],
    queryFn: () => apiFetch('/api/market/news'),
    refetchInterval: 60_000,
  })

  const news = (data?.news || []).filter(n => filter === 'all' || n.sentiment === filter)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-terminal-text">Market News</h1>
        <div className="flex gap-1">
          {['all', 'bullish', 'bearish', 'neutral'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx('px-3 py-1 rounded text-xs capitalize transition-colors',
                filter === f ? 'bg-terminal-blue text-white' : 'bg-terminal-border text-terminal-muted hover:text-terminal-text'
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <ErrorBoundary>
        {isLoading ? (
          <TableSkeleton rows={6} />
        ) : (
          <div className="space-y-2">
            {news.map((item, i) => (
              <div key={i} className={clsx(
                'card flex items-start gap-3',
                item.sentiment === 'bullish' ? 'border-l-2 border-l-terminal-green' :
                item.sentiment === 'bearish' ? 'border-l-2 border-l-terminal-red' :
                'border-l-2 border-l-terminal-muted'
              )}>
                <span className={clsx('badge mt-0.5 shrink-0',
                  item.sentiment === 'bullish' ? 'badge-green' :
                  item.sentiment === 'bearish' ? 'badge-red' : 'badge-muted'
                )}>
                  {item.sentiment}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-terminal-text leading-snug">{item.title}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-terminal-muted">{item.publisher}</span>
                    <span className="text-xs text-terminal-muted">·</span>
                    <span className="text-xs text-terminal-muted">{fmt.timeAgo(item.timestamp)}</span>
                    {item.link && (
                      <a href={item.link} target="_blank" rel="noopener noreferrer" className="text-terminal-blue hover:underline">
                        <ExternalLink size={10} />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {news.length === 0 && (
              <div className="card text-center py-8 text-terminal-muted">No news found</div>
            )}
          </div>
        )}
      </ErrorBoundary>

      <div className="card bg-terminal-card2 text-xs text-terminal-muted">
        <div className="text-terminal-text font-semibold text-sm mb-1">About News Sentiment</div>
        <p>Sentiment is estimated by keyword scoring. <strong className="text-terminal-yellow">Not reliable on its own</strong> — use it to understand if price moves have a catalyst.</p>
        <p className="mt-1">Major catalysts to watch: Fed speakers, CPI/PPI, NVDA earnings, chip export news, macro surprises. These can override technical setups entirely.</p>
      </div>
    </div>
  )
}
