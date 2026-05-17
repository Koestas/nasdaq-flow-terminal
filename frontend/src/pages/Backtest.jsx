import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import { BarChart2, TrendingUp, TrendingDown, AlertCircle, CheckCircle, Clock } from 'lucide-react'

const SYMBOLS = [
  { value: 'NQ=F', label: 'MNQ', instrument: 'MNQ' },
  { value: 'ES=F', label: 'MES', instrument: 'MES' },
  { value: 'GC=F', label: 'MGC', instrument: 'MGC' },
]
const PERIODS = [
  { value: 15, label: '15 days' },
  { value: 30, label: '30 days' },
  { value: 45, label: '45 days' },
  { value: 60, label: '60 days' },
]

function StatCard({ label, value, sub, color = 'text-terminal-text', icon }) {
  return (
    <div className="bg-terminal-card border border-terminal-border rounded-lg p-4 flex flex-col gap-1">
      <div className="flex items-center gap-2 text-[10px] text-terminal-muted uppercase tracking-wider">
        {icon && <span>{icon}</span>}
        {label}
      </div>
      <div className={`font-mono font-bold text-2xl ${color}`}>{value}</div>
      {sub && <div className="text-xs text-terminal-muted">{sub}</div>}
    </div>
  )
}

function MiniEquityCurve({ curve }) {
  if (!curve || curve.length < 2) return null
  const trades = curve.filter(p => p.trade)
  if (!trades.length) return null

  const pnls = curve.map(p => p.pnl)
  const min = Math.min(...pnls, 0)
  const max = Math.max(...pnls, 0)
  const range = max - min || 1
  const W = 100, H = 60

  const pts = curve.map((p, i) => {
    const x = (i / (curve.length - 1)) * W
    const y = H - ((p.pnl - min) / range) * H
    return `${x},${y}`
  }).join(' ')

  const zeroY = H - ((0 - min) / range) * H

  return (
    <div className="bg-terminal-bg border border-terminal-border rounded p-3">
      <div className="text-[10px] text-terminal-muted uppercase tracking-wider mb-2">Equity Curve</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-20 overflow-visible">
        <line x1="0" y1={zeroY} x2={W} y2={zeroY} stroke="#334155" strokeWidth="0.5" strokeDasharray="2,2" />
        <polyline points={pts} fill="none"
          stroke={pnls[pnls.length - 1] >= 0 ? '#10B981' : '#EF4444'}
          strokeWidth="1.5" />
        {curve.filter(p => p.trade).map((p, i) => {
          const idx = curve.indexOf(p)
          const x = (idx / (curve.length - 1)) * W
          const y = H - ((p.pnl - min) / range) * H
          return (
            <circle key={i} cx={x} cy={y} r="1.5"
              fill={p.pnl > (curve[idx - 1]?.pnl ?? 0) ? '#10B981' : '#EF4444'} />
          )
        })}
      </svg>
    </div>
  )
}

function ResultBadge({ result }) {
  if (result === 'win')     return <span className="text-[10px] font-bold text-terminal-green px-1.5 py-0.5 rounded bg-terminal-green/10 border border-terminal-green/30">WIN</span>
  if (result === 'loss')    return <span className="text-[10px] font-bold text-terminal-red px-1.5 py-0.5 rounded bg-terminal-red/10 border border-terminal-red/30">LOSS</span>
  return <span className="text-[10px] font-bold text-terminal-muted px-1.5 py-0.5 rounded bg-terminal-card border border-terminal-border">EXP</span>
}

function GradeBadge({ grade }) {
  const color = grade === 'A+' ? 'text-green-400 border-green-500/40 bg-green-500/10'
              : grade === 'A'  ? 'text-blue-400 border-blue-500/40 bg-blue-500/10'
              : 'text-terminal-muted border-terminal-border bg-terminal-card'
  return <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${color}`}>{grade}</span>
}

export default function Backtest() {
  const [symIdx,   setSymIdx]   = useState(0)
  const [period,   setPeriod]   = useState(30)
  const [runKey,   setRunKey]   = useState(null)

  const sym = SYMBOLS[symIdx]

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['backtest', sym.value, sym.instrument, period, runKey],
    queryFn: () => apiFetch(`/api/backtest/run?symbol=${encodeURIComponent(sym.value)}&instrument=${sym.instrument}&lookback_days=${period}`),
    enabled: runKey !== null,
    staleTime: Infinity,
    retry: false,
  })

  const stats  = data?.stats   || {}
  const trades = data?.trades  || []
  const curve  = data?.equity_curve || []

  const running = isLoading || isFetching

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <BarChart2 size={16} className="text-terminal-blue" />
          <span className="text-terminal-blue font-bold text-sm">SIGNAL BACKTEST</span>
          <span className="text-terminal-muted text-xs">— ICT strategy over historical data</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap bg-terminal-card border border-terminal-border rounded p-3">
        <div className="flex gap-1">
          {SYMBOLS.map((s, i) => (
            <button key={s.value} onClick={() => setSymIdx(i)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                symIdx === i ? 'bg-terminal-blue text-white' : 'bg-terminal-bg text-terminal-muted border border-terminal-border hover:text-terminal-text'
              }`}
            >{s.label}</button>
          ))}
        </div>
        <div className="w-px h-5 bg-terminal-border" />
        <div className="flex gap-1">
          {PERIODS.map(p => (
            <button key={p.value} onClick={() => setPeriod(p.value)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                period === p.value ? 'bg-terminal-yellow/20 text-terminal-yellow border border-terminal-yellow/40' : 'bg-terminal-bg text-terminal-muted border border-terminal-border hover:text-terminal-text'
              }`}
            >{p.label}</button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {running && <span className="text-xs text-terminal-yellow animate-pulse">Running simulation...</span>}
          <button
            onClick={() => setRunKey(Date.now())}
            disabled={running}
            className="px-4 py-1.5 rounded text-xs font-bold bg-terminal-blue text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {running ? 'Running…' : '▶ Run Backtest'}
          </button>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="flex items-start gap-2 px-3 py-2 bg-terminal-yellow/5 border border-terminal-yellow/20 rounded text-xs text-terminal-yellow/80">
        <AlertCircle size={12} className="shrink-0 mt-0.5" />
        Simulated results using Yahoo Finance 5m data (15-20 min delayed). Up to 2 trades per day — first A/A+ setup in the 9:30–11:30 AM ET killzone. Win = done for the day. Lose once = try again. Lose twice = done. Past performance ≠ future results.
      </div>

      {!data && !running && (
        <div className="flex flex-col items-center justify-center h-48 text-terminal-muted gap-2">
          <BarChart2 size={32} className="opacity-30" />
          <div className="text-sm">Select a symbol and period, then click Run Backtest</div>
        </div>
      )}

      {data && !running && (
        <>
          {/* Stats grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
            <StatCard label="Trades" value={stats.total_trades ?? 0} sub={`${data.lookback_days}d window`} />
            <StatCard
              label="Win Rate"
              value={`${stats.win_rate ?? 0}%`}
              sub={`${stats.wins}W · ${stats.losses}L · ${stats.expired}X`}
              color={stats.win_rate >= 55 ? 'text-terminal-green' : stats.win_rate >= 40 ? 'text-terminal-yellow' : 'text-terminal-red'}
            />
            <StatCard
              label="Total P&L"
              value={`$${fmt.num(stats.total_pnl ?? 0)}`}
              sub={sym.instrument}
              color={(stats.total_pnl ?? 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red'}
            />
            <StatCard
              label="Profit Factor"
              value={stats.profit_factor ?? '--'}
              sub="gross win / gross loss"
              color={stats.profit_factor >= 1.5 ? 'text-terminal-green' : stats.profit_factor >= 1 ? 'text-terminal-yellow' : 'text-terminal-red'}
            />
            <StatCard label="Avg Win" value={`$${stats.avg_win ?? 0}`} color="text-terminal-green" />
            <StatCard label="Avg Loss" value={`$${stats.avg_loss ?? 0}`} color="text-terminal-red" />
            <StatCard label="Avg R:R" value={`${stats.avg_rr ?? 0}R`} sub="actual achieved" />
            <StatCard label="Max DD" value={`$${stats.max_drawdown ?? 0}`} sub="peak-to-trough" color="text-terminal-red" />
          </div>

          {/* Equity curve */}
          {curve.length > 2 && <MiniEquityCurve curve={curve} />}

          {/* Best / Worst */}
          {(stats.best_trade || stats.worst_trade) && (
            <div className="grid grid-cols-2 gap-2">
              {stats.best_trade && (
                <div className="bg-terminal-card border border-terminal-green/20 rounded p-3 text-xs">
                  <div className="flex items-center gap-1 text-terminal-green font-bold mb-1">
                    <TrendingUp size={11}/> Best Trade
                  </div>
                  <span className="text-terminal-muted">{stats.best_trade.day}</span>
                  <span className="mx-1 text-terminal-border">·</span>
                  <span className="text-terminal-green font-mono">${stats.best_trade.pnl}</span>
                  <span className="mx-1 text-terminal-border">·</span>
                  <span className="text-terminal-muted">{stats.best_trade.rr_achieved}R · {stats.best_trade.direction.toUpperCase()}</span>
                </div>
              )}
              {stats.worst_trade && (
                <div className="bg-terminal-card border border-terminal-red/20 rounded p-3 text-xs">
                  <div className="flex items-center gap-1 text-terminal-red font-bold mb-1">
                    <TrendingDown size={11}/> Worst Trade
                  </div>
                  <span className="text-terminal-muted">{stats.worst_trade.day}</span>
                  <span className="mx-1 text-terminal-border">·</span>
                  <span className="text-terminal-red font-mono">${stats.worst_trade.pnl}</span>
                  <span className="mx-1 text-terminal-border">·</span>
                  <span className="text-terminal-muted">{stats.worst_trade.rr_achieved}R · {stats.worst_trade.direction.toUpperCase()}</span>
                </div>
              )}
            </div>
          )}

          {/* Trade log */}
          {trades.length > 0 && (
            <div className="bg-terminal-card border border-terminal-border rounded overflow-hidden">
              <div className="px-3 py-2 border-b border-terminal-border flex items-center gap-2">
                <span className="text-xs font-bold text-terminal-text">Trade Log</span>
                <span className="text-[10px] text-terminal-muted">({trades.length} simulated entries)</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-terminal-border bg-terminal-bg">
                      {['Date', 'Dir', 'Grade', 'Entry', 'Stop', 'Target', 'Exit', 'Pts', 'P&L', 'RR', 'Result', 'Equity'].map(h => (
                        <th key={h} className="px-3 py-2 text-left text-terminal-muted font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((t, i) => {
                      const isWin = t.result === 'win'
                      const rowColor = isWin ? 'border-terminal-green/10' : t.result === 'loss' ? 'border-terminal-red/10' : ''
                      return (
                        <tr key={i} className={`border-b border-terminal-border/30 hover:bg-terminal-bg/50 ${rowColor}`}>
                          <td className="px-3 py-1.5 text-terminal-muted whitespace-nowrap">{t.day}</td>
                          <td className="px-3 py-1.5">
                            <span className={t.direction === 'bullish' ? 'text-terminal-green font-bold' : 'text-terminal-red font-bold'}>
                              {t.direction === 'bullish' ? '▲ L' : '▼ S'}
                            </span>
                          </td>
                          <td className="px-3 py-1.5"><GradeBadge grade={t.grade} /></td>
                          <td className="px-3 py-1.5 font-mono text-terminal-text">{fmt.num(t.entry)}</td>
                          <td className="px-3 py-1.5 font-mono text-terminal-red">{fmt.num(t.stop)}</td>
                          <td className="px-3 py-1.5 font-mono text-terminal-green">{fmt.num(t.target)}</td>
                          <td className="px-3 py-1.5 font-mono text-terminal-text">{fmt.num(t.exit_price)}</td>
                          <td className={`px-3 py-1.5 font-mono ${t.pts >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                            {t.pts >= 0 ? '+' : ''}{t.pts}
                          </td>
                          <td className={`px-3 py-1.5 font-mono font-bold ${t.pnl >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                            {t.pnl >= 0 ? '+' : ''}${t.pnl}
                          </td>
                          <td className="px-3 py-1.5 font-mono text-terminal-yellow">{t.rr_achieved}R</td>
                          <td className="px-3 py-1.5"><ResultBadge result={t.result} /></td>
                          <td className={`px-3 py-1.5 font-mono ${t.running_pnl >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                            ${fmt.num(t.running_pnl)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {trades.length === 0 && (
            <div className="flex items-center justify-center h-24 text-terminal-muted text-sm">
              No qualifying A/A+ setups found in this window — try a longer period or different symbol
            </div>
          )}
        </>
      )}
    </div>
  )
}
