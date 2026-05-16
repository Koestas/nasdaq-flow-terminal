import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { ChartSkeleton } from '../components/LoadingSkeleton'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from 'recharts'

export default function Gex() {
  const { data, isLoading } = useQuery({
    queryKey: ['gex'],
    queryFn: () => apiFetch('/api/flow/gex'),
    refetchInterval: 30_000,
  })

  const strikes = (data?.by_strike || []).filter(s => s.net_gex != null)
  const spot = data?.spot

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-terminal-text">GEX — Gamma Exposure</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Net GEX', value: fmt.premium(data?.net_gex), color: (data?.net_gex || 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red' },
          { label: 'Call Wall', value: fmt.price(data?.call_wall), color: 'text-terminal-text' },
          { label: 'Put Wall', value: fmt.price(data?.put_wall), color: 'text-terminal-text' },
          { label: 'QQQ Spot', value: fmt.price(spot), color: 'text-terminal-blue' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card">
            <div className="stat-label">{label}</div>
            <div className={`stat-value mt-1 ${color}`}>{isLoading ? '...' : value}</div>
          </div>
        ))}
      </div>

      <ErrorBoundary>
        <div className="card">
          <div className="stat-label mb-4">Net Gamma Exposure by Strike</div>
          {isLoading || strikes.length === 0 ? (
            <ChartSkeleton height={320} />
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={strikes} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                <XAxis dataKey="strike" tick={{ fontSize: 10, fill: '#4a6080' }} />
                <YAxis tick={{ fontSize: 10, fill: '#4a6080' }} tickFormatter={v => fmt.premium(v)} />
                <Tooltip
                  contentStyle={{ background: '#0f1623', border: '1px solid #1e2d40', fontSize: 11 }}
                  formatter={(v) => [fmt.premium(v), 'Net GEX']}
                  labelFormatter={l => `Strike: ${l}`}
                />
                <ReferenceLine y={0} stroke="#4a6080" />
                {spot && <ReferenceLine x={strikes.reduce((prev, curr) => Math.abs(curr.strike - spot) < Math.abs(prev.strike - spot) ? curr : prev, strikes[0])?.strike} stroke="#00aaff" strokeDasharray="4 2" label={{ value: 'Spot', fill: '#00aaff', fontSize: 10 }} />}
                <Bar dataKey="net_gex" radius={[2, 2, 0, 0]}>
                  {strikes.map((entry, i) => (
                    <Cell key={i} fill={(entry.net_gex || 0) >= 0 ? '#00ff8866' : '#ff446666'} stroke={(entry.net_gex || 0) >= 0 ? '#00ff88' : '#ff4466'} strokeWidth={1} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </ErrorBoundary>

      <div className="card bg-terminal-card2 text-xs text-terminal-muted space-y-2">
        <div className="text-terminal-text font-semibold text-sm">About GEX / Gamma</div>
        <p><strong className="text-terminal-text">Positive GEX</strong> (green bars): Market makers are long gamma — they buy dips and sell rips, damping volatility and acting as a magnet.</p>
        <p><strong className="text-terminal-text">Negative GEX</strong> (red bars): Market makers are short gamma — they chase price in both directions, amplifying moves.</p>
        <p><strong className="text-terminal-green">Call Wall</strong>: Strike with highest call OI above spot. Acts as resistance — price tends to slow or reverse here.</p>
        <p><strong className="text-terminal-red">Put Wall</strong>: Strike with highest put OI below spot. Acts as support — price may bounce or accelerate if broken.</p>
        <p><strong className="text-terminal-yellow">For MNQ:</strong> Breaking through the call wall can trigger rapid short covering. Losing the put wall can trigger accelerated selling.</p>
      </div>
    </div>
  )
}
