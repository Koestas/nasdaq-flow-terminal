import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { ChartSkeleton, CardSkeleton } from '../components/LoadingSkeleton'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

export default function Wave() {
  const { data, isLoading } = useQuery({
    queryKey: ['wave'],
    queryFn: () => apiFetch('/api/flow/wave'),
    refetchInterval: 20_000,
  })

  const history = data?.history || []

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-terminal-text">WAVE — Options Premium Flow</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Call WAVE', value: fmt.premium(data?.call_wave), color: 'text-terminal-green' },
          { label: 'Put WAVE', value: fmt.premium(data?.put_wave), color: 'text-terminal-red' },
          { label: 'Net WAVE', value: fmt.premium(data?.net_wave), color: (data?.net_wave || 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red' },
          { label: 'Call Dominance', value: data?.call_dominance_pct ? `${data.call_dominance_pct.toFixed(1)}%` : '--', color: 'text-terminal-text' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card">
            <div className="stat-label">{label}</div>
            <div className={`stat-value mt-1 ${color}`}>{isLoading ? '...' : value}</div>
          </div>
        ))}
      </div>

      <ErrorBoundary>
        <div className="card">
          <div className="stat-label mb-4">Call vs Put Premium Over Time</div>
          {isLoading || history.length === 0 ? (
            <ChartSkeleton height={280} />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={history} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id="wCallGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00ff88" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#00ff88" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="wPutGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff4466" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#ff4466" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="timestamp" tick={{ fontSize: 10, fill: '#4a6080' }} tickFormatter={v => v ? new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''} />
                <YAxis tick={{ fontSize: 10, fill: '#4a6080' }} tickFormatter={v => fmt.premium(v)} />
                <Tooltip
                  contentStyle={{ background: '#0f1623', border: '1px solid #1e2d40', fontSize: 11 }}
                  formatter={(v, name) => [fmt.premium(v), name]}
                  labelFormatter={l => l ? new Date(l).toLocaleTimeString() : ''}
                />
                <Area type="monotone" dataKey="call_wave" stroke="#00ff88" strokeWidth={1.5} fill="url(#wCallGrad)" name="Call WAVE" dot={false} />
                <Area type="monotone" dataKey="put_wave" stroke="#ff4466" strokeWidth={1.5} fill="url(#wPutGrad)" name="Put WAVE" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </ErrorBoundary>

      <ErrorBoundary>
        <div className="card">
          <div className="stat-label mb-4">Net WAVE (Call minus Put Premium)</div>
          {isLoading || history.length === 0 ? (
            <ChartSkeleton height={160} />
          ) : (
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={history} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id="netGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00aaff" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00aaff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="timestamp" hide />
                <YAxis tick={{ fontSize: 10, fill: '#4a6080' }} tickFormatter={v => fmt.premium(v)} />
                <Tooltip
                  contentStyle={{ background: '#0f1623', border: '1px solid #1e2d40', fontSize: 11 }}
                  formatter={(v) => [fmt.premium(v), 'Net WAVE']}
                />
                <ReferenceLine y={0} stroke="#4a6080" strokeDasharray="3 3" />
                <Area type="monotone" dataKey="net_wave" stroke="#00aaff" strokeWidth={1.5} fill="url(#netGrad)" name="Net WAVE" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </ErrorBoundary>

      <div className="card bg-terminal-card2 text-xs text-terminal-muted space-y-2">
        <div className="text-terminal-text font-semibold text-sm">About WAVE</div>
        <p>WAVE measures <span className="text-terminal-green">call premium</span> vs <span className="text-terminal-red">put premium</span> flowing through QQQ options in real time.</p>
        <p><strong className="text-terminal-green">Bullish signal:</strong> Call WAVE rising while QQQ holds VWAP. Put WAVE flat or falling. Leadership green.</p>
        <p><strong className="text-terminal-red">Bearish signal:</strong> Put WAVE rising while QQQ loses VWAP. Call WAVE fading. Leadership red.</p>
        <p><strong className="text-terminal-yellow">Warning:</strong> WAVE alone is not a trade signal. Confirm with price structure and VWAP. WAVE can be hedging activity — never use it in isolation.</p>
        <p>For MNQ: A rising Net WAVE while QQQ reclaims VWAP is a high-quality long setup. A falling Net WAVE while QQQ fails VWAP supports shorts.</p>
      </div>
    </div>
  )
}
