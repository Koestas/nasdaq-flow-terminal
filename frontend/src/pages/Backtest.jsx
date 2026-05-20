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
  { value: 90, label: '90 days' },
]
const TEST_PERIODS = [
  { value: 90,  label: '90d' },
  { value: 180, label: '180d' },
  { value: 365, label: '365d' },
  { value: 540, label: '540d' },
  { value: 720, label: '720d' },
]
const CONTRACTS = [1, 2, 3, 4, 5]

const KORABI_FLAGS = [
  { key: 'exp_tight_stop',   label: 'Tight Stop ≤50pt',  color: 'text-purple-400 border-purple-500/40 bg-purple-500/10', desc: 'Korabi precision: only setups with natural stop ≤50pts MNQ' },
  { key: 'exp_ext_liq',      label: 'External Sweep',    color: 'text-blue-400 border-blue-500/40 bg-blue-500/10',       desc: 'IRL→ERL: require sweep of EQH/EQL/session level, not intraday micro-level' },
  { key: 'exp_smt_confirm',  label: 'SMT Diverge',       color: 'text-yellow-400 border-yellow-500/40 bg-yellow-500/10', desc: 'Require NQ+ES divergence at sweep level (5m only)' },
  { key: 'exp_bpr_entry',    label: 'BPR Zone',          color: 'text-cyan-400 border-cyan-500/40 bg-cyan-500/10',       desc: 'Balanced Price Range: entry must fall inside overlapping bull+bear FVG zone' },
  { key: 'exp_vwap_slope',   label: 'VWAP Slope',        color: 'text-green-400 border-green-500/40 bg-green-500/10',    desc: 'Require rising VWAP for longs, falling for shorts' },
  { key: 'exp_entry_volume', label: 'Entry Volume',      color: 'text-orange-400 border-orange-500/40 bg-orange-500/10', desc: 'Entry bar must have volume > 0.8× session average' },
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

function ResultBadge({ result, eod }) {
  if (result === 'win'          && eod)  return <span className="text-[10px] font-bold text-terminal-green px-1.5 py-0.5 rounded bg-terminal-green/10 border border-terminal-green/20 opacity-70">EOD+</span>
  if (result === 'loss'         && eod)  return <span className="text-[10px] font-bold text-terminal-red px-1.5 py-0.5 rounded bg-terminal-red/10 border border-terminal-red/20 opacity-70">EOD−</span>
  if (result === 'win')                  return <span className="text-[10px] font-bold text-terminal-green px-1.5 py-0.5 rounded bg-terminal-green/10 border border-terminal-green/30">WIN</span>
  if (result === 'partial_win'  && eod)  return <span className="text-[10px] font-bold text-terminal-yellow px-1.5 py-0.5 rounded bg-terminal-yellow/10 border border-terminal-yellow/20 opacity-70">P-EOD</span>
  if (result === 'partial_win')          return <span className="text-[10px] font-bold text-terminal-yellow px-1.5 py-0.5 rounded bg-terminal-yellow/10 border border-terminal-yellow/30">+½R</span>
  if (result === 'loss')                 return <span className="text-[10px] font-bold text-terminal-red px-1.5 py-0.5 rounded bg-terminal-red/10 border border-terminal-red/30">LOSS</span>
  return <span className="text-[10px] font-bold text-terminal-muted px-1.5 py-0.5 rounded bg-terminal-card border border-terminal-border">EXP</span>
}

function GradeBadge({ grade }) {
  const color = grade === 'A+' ? 'text-green-400 border-green-500/40 bg-green-500/10'
              : grade === 'A'  ? 'text-blue-400 border-blue-500/40 bg-blue-500/10'
              : grade === 'B+' ? 'text-orange-400 border-orange-500/40 bg-orange-500/10'
              : 'text-terminal-muted border-terminal-border bg-terminal-card'
  return <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${color}`}>{grade}</span>
}

function SessionBadge({ session }) {
  if (session === 'OR30')
    return <span className="text-[10px] font-bold text-orange-400 px-1.5 py-0.5 rounded bg-orange-500/10 border border-orange-500/30">OR30</span>
  if (session === 'AM2')
    return <span className="text-[10px] font-bold text-terminal-blue px-1.5 py-0.5 rounded bg-terminal-blue/10 border border-terminal-blue/30">AM2</span>
  return <span className="text-[10px] font-bold text-terminal-muted px-1.5 py-0.5 rounded bg-terminal-card border border-terminal-border">AM</span>
}

export default function Backtest() {
  const [activeTab,  setActiveTab]  = useState('arlennys')
  const [symIdx,     setSymIdx]     = useState(0)
  const [period,     setPeriod]     = useState(30)
  const [contracts,  setContracts]  = useState(1)
  const [runKey,     setRunKey]     = useState(null)
  // Test Lab state
  const [testPeriod,    setTestPeriod]    = useState(365)
  const [testInterval,  setTestInterval]  = useState('1h')
  const [testContracts, setTestContracts] = useState(1)
  const [activeFlags,   setActiveFlags]   = useState({})
  const [testRunKey,    setTestRunKey]     = useState(null)

  const sym = SYMBOLS[symIdx]

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['backtest', sym.value, sym.instrument, period, contracts, runKey],
    queryFn: () => apiFetch(`/api/backtest/run?symbol=${encodeURIComponent(sym.value)}&instrument=${sym.instrument}&lookback_days=${period}&contracts=${contracts}&daily_loss_limit=1000`),
    enabled: runKey !== null,
    staleTime: Infinity,
    retry: false,
  })

  const testFlagParams = Object.entries(activeFlags).filter(([,v]) => v).map(([k]) => `${k}=1`).join('&')
  const { data: testData, isLoading: testLoading, isFetching: testFetching } = useQuery({
    queryKey: ['backtest-test', sym.value, sym.instrument, testPeriod, testInterval, testContracts, testFlagParams, testRunKey],
    queryFn: () => apiFetch(`/api/backtest/run-test?symbol=${encodeURIComponent(sym.value)}&instrument=${sym.instrument}&lookback_days=${testPeriod}&interval=${testInterval}&contracts=${testContracts}${testFlagParams ? '&' + testFlagParams : ''}`),
    enabled: testRunKey !== null,
    staleTime: Infinity,
    retry: false,
  })

  const stats  = data?.stats   || {}
  const trades = data?.trades  || []
  const curve  = data?.equity_curve || []

  const testStats   = testData?.stats            || {}
  const testTrades  = testData?.trades           || []
  const testCurve   = testData?.equity_curve     || []
  const testMonthly = testData?.monthly_breakdown || {}

  const running     = isLoading || isFetching
  const testRunning = testLoading || testFetching

  return (
    <div className="flex flex-col gap-4">
      {/* Header + Tabs */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <BarChart2 size={16} className="text-terminal-blue" />
          <span className="text-terminal-blue font-bold text-sm">SIGNAL BACKTEST</span>
        </div>
        <div className="ml-auto flex gap-1">
          <button onClick={() => setActiveTab('arlennys')}
            className={`px-3 py-1 rounded text-xs font-bold transition-colors ${activeTab === 'arlennys' ? 'bg-terminal-blue text-white' : 'bg-terminal-bg text-terminal-muted border border-terminal-border hover:text-terminal-text'}`}>
            Arlennys Model
          </button>
          <button onClick={() => setActiveTab('test')}
            className={`px-3 py-1 rounded text-xs font-bold transition-colors ${activeTab === 'test' ? 'bg-purple-600 text-white' : 'bg-terminal-bg text-terminal-muted border border-terminal-border hover:text-terminal-text'}`}>
            🧪 Test Lab
          </button>
        </div>
      </div>

      {/* ── TEST LAB ── */}
      {activeTab === 'test' && (
        <div className="flex flex-col gap-4">
          {/* Test controls */}
          <div className="flex flex-col gap-3 bg-terminal-card border border-purple-500/20 rounded p-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] text-purple-400 font-bold uppercase tracking-wider">Symbol</span>
              {SYMBOLS.map((s, i) => (
                <button key={s.value} onClick={() => setSymIdx(i)}
                  className={`px-2 py-0.5 rounded text-xs font-medium ${symIdx === i ? 'bg-terminal-blue text-white' : 'bg-terminal-bg text-terminal-muted border border-terminal-border'}`}>
                  {s.label}
                </button>
              ))}
              <span className="w-px h-4 bg-terminal-border mx-1" />
              <span className="text-[10px] text-purple-400 font-bold uppercase tracking-wider">Interval</span>
              {['1h', '5m'].map(iv => (
                <button key={iv} onClick={() => setTestInterval(iv)}
                  className={`px-2 py-0.5 rounded text-xs font-medium ${testInterval === iv ? 'bg-purple-600 text-white' : 'bg-terminal-bg text-terminal-muted border border-terminal-border'}`}>
                  {iv} {iv === '1h' ? '(720d max)' : '(90d max)'}
                </button>
              ))}
              <span className="w-px h-4 bg-terminal-border mx-1" />
              <span className="text-[10px] text-purple-400 font-bold uppercase tracking-wider">Lookback</span>
              {TEST_PERIODS.map(p => (
                <button key={p.value} onClick={() => setTestPeriod(p.value)}
                  className={`px-2 py-0.5 rounded text-xs font-medium ${testPeriod === p.value ? 'bg-terminal-yellow/20 text-terminal-yellow border border-terminal-yellow/40' : 'bg-terminal-bg text-terminal-muted border border-terminal-border'}`}
                  disabled={testInterval === '5m' && p.value > 90}>
                  {p.label}
                </button>
              ))}
              <span className="w-px h-4 bg-terminal-border mx-1" />
              <span className="text-[10px] text-purple-400 font-bold uppercase tracking-wider">Cts</span>
              {CONTRACTS.map(c => (
                <button key={c} onClick={() => setTestContracts(c)}
                  className={`px-2 py-0.5 rounded text-xs font-medium ${testContracts === c ? 'bg-terminal-blue/30 text-terminal-blue border border-terminal-blue/50' : 'bg-terminal-bg text-terminal-muted border border-terminal-border'}`}>
                  {c}
                </button>
              ))}
            </div>

            {/* Korabi flags */}
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] text-purple-400 font-bold uppercase tracking-wider">Korabi Trades Concepts</span>
              <div className="flex flex-wrap gap-2">
                {KORABI_FLAGS.map(f => {
                  const on = !!activeFlags[f.key]
                  return (
                    <button key={f.key}
                      onClick={() => setActiveFlags(prev => ({ ...prev, [f.key]: !prev[f.key] }))}
                      title={f.desc}
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${on ? f.color : 'text-terminal-muted border-terminal-border bg-terminal-bg'}`}>
                      {on ? '✓ ' : ''}{f.label}
                    </button>
                  )
                })}
              </div>
              <div className="text-[10px] text-terminal-muted">
                Hover a flag for description · SMT/BPR require 5m interval
              </div>
            </div>

            <div className="flex items-center gap-2 mt-1">
              {testRunning && <span className="text-xs text-purple-400 animate-pulse">Running simulation… {testInterval === '1h' && testPeriod >= 365 ? '(720d may take 30–60s)' : ''}</span>}
              <button onClick={() => setTestRunKey(Date.now())} disabled={testRunning}
                className="ml-auto px-4 py-1.5 rounded text-xs font-bold bg-purple-600 text-white hover:bg-purple-500 disabled:opacity-50 transition-colors">
                {testRunning ? 'Running…' : '▶ Run Test'}
              </button>
            </div>
          </div>

          {/* Test results */}
          {testData && !testRunning && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2">
                <StatCard label="Trades" value={testStats.total_trades ?? 0} sub={`${testData.lookback_days}d · ${testData.interval}`} />
                <StatCard label="Win Rate" value={`${testStats.win_rate ?? 0}%`}
                  sub={`${testStats.wins}W · ${testStats.losses}L`}
                  color={testStats.win_rate >= 65 ? 'text-terminal-green' : testStats.win_rate >= 50 ? 'text-terminal-yellow' : 'text-terminal-red'} />
                <StatCard label="Profit Factor" value={testStats.profit_factor ?? '--'}
                  color={testStats.profit_factor >= 2 ? 'text-terminal-green' : testStats.profit_factor >= 1 ? 'text-terminal-yellow' : 'text-terminal-red'} />
                <StatCard label="Total P&L" value={`$${fmt.num(testStats.total_pnl ?? 0)}`}
                  color={(testStats.total_pnl ?? 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red'} />
                <StatCard label="Avg Win" value={`$${testStats.avg_win ?? 0}`} color="text-terminal-green" />
                <StatCard label="Avg Loss" value={`$${testStats.avg_loss ?? 0}`} color="text-terminal-red" />
              </div>

              {/* Active flags summary */}
              {Object.values(testData.flags || {}).some(Boolean) && (
                <div className="flex flex-wrap gap-1 text-[10px]">
                  <span className="text-terminal-muted">Active flags:</span>
                  {KORABI_FLAGS.filter(f => testData.flags?.[f.key]).map(f => (
                    <span key={f.key} className={`px-1.5 py-0.5 rounded border ${f.color}`}>{f.label}</span>
                  ))}
                </div>
              )}

              {/* Monthly breakdown */}
              {Object.keys(testMonthly).length > 0 && (
                <div className="bg-terminal-card border border-terminal-border rounded overflow-hidden">
                  <div className="px-3 py-2 border-b border-terminal-border">
                    <span className="text-xs font-bold text-terminal-text">Monthly Breakdown</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-terminal-border bg-terminal-bg">
                          {['Month', 'Trades', 'Wins', 'WR', 'P&L'].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-terminal-muted font-medium">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(testMonthly).sort().map(([m, v]) => (
                          <tr key={m} className="border-b border-terminal-border/30 hover:bg-terminal-bg/50">
                            <td className="px-3 py-1.5 text-terminal-muted">{m}</td>
                            <td className="px-3 py-1.5 font-mono text-terminal-text">{v.trades}</td>
                            <td className="px-3 py-1.5 font-mono text-terminal-green">{v.wins}</td>
                            <td className={`px-3 py-1.5 font-mono font-bold ${v.win_rate >= 65 ? 'text-terminal-green' : v.win_rate >= 50 ? 'text-terminal-yellow' : 'text-terminal-red'}`}>
                              {v.win_rate}%
                            </td>
                            <td className={`px-3 py-1.5 font-mono font-bold ${v.pnl >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                              {v.pnl >= 0 ? '+' : ''}${fmt.num(v.pnl)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {testCurve.length > 2 && <MiniEquityCurve curve={testCurve} />}

              {/* Test trade log */}
              {testTrades.length > 0 && (
                <div className="bg-terminal-card border border-purple-500/10 rounded overflow-hidden">
                  <div className="px-3 py-2 border-b border-terminal-border flex items-center gap-2">
                    <span className="text-xs font-bold text-terminal-text">Test Trade Log</span>
                    <span className="text-[10px] text-terminal-muted">({testTrades.length} simulated)</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-terminal-border bg-terminal-bg">
                          {['Date', 'Dir', 'HTF', 'Grade', 'Entry', 'Stop', 'Pts', 'P&L', 'RR', 'Result'].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-terminal-muted font-medium whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {testTrades.map((t, i) => (
                          <tr key={i} className="border-b border-terminal-border/30 hover:bg-terminal-bg/50">
                            <td className="px-3 py-1.5 text-terminal-muted whitespace-nowrap">{t.day}</td>
                            <td className="px-3 py-1.5">
                              <span className={t.direction === 'bullish' ? 'text-terminal-green font-bold' : 'text-terminal-red font-bold'}>
                                {t.direction === 'bullish' ? '▲ L' : '▼ S'}
                              </span>
                            </td>
                            <td className="px-3 py-1.5">
                              <span className={`text-[10px] font-bold ${t.htf_dir?.includes('bullish') ? 'text-terminal-green' : t.htf_dir?.includes('bearish') ? 'text-terminal-red' : 'text-terminal-muted'}`}>
                                {t.htf_dir?.includes('bullish') ? '▲' : t.htf_dir?.includes('bearish') ? '▼' : '—'}
                              </span>
                            </td>
                            <td className="px-3 py-1.5"><GradeBadge grade={t.grade} /></td>
                            <td className="px-3 py-1.5 font-mono text-terminal-text">{fmt.num(t.entry)}</td>
                            <td className="px-3 py-1.5 font-mono text-terminal-red">{t.stop_dist}pt</td>
                            <td className={`px-3 py-1.5 font-mono ${t.pts >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>{t.pts >= 0 ? '+' : ''}{t.pts}</td>
                            <td className={`px-3 py-1.5 font-mono font-bold ${t.pnl >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>{t.pnl >= 0 ? '+' : ''}${t.pnl}</td>
                            <td className="px-3 py-1.5 font-mono text-terminal-yellow">{t.rr_achieved}R</td>
                            <td className="px-3 py-1.5"><ResultBadge result={t.result} eod={t.eod} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {testTrades.length === 0 && (
                <div className="flex items-center justify-center h-16 text-terminal-muted text-xs">
                  No qualifying setups with current filters — try loosening thresholds or switching to 5m
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── ARLENNYS MODEL ── */}
      {activeTab === 'arlennys' && (
        <div className="flex flex-col gap-4">
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
        <div className="w-px h-5 bg-terminal-border" />
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-terminal-muted mr-1">Contracts:</span>
          {CONTRACTS.map(c => (
            <button key={c} onClick={() => setContracts(c)}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                contracts === c ? 'bg-terminal-blue/30 text-terminal-blue border border-terminal-blue/50' : 'bg-terminal-bg text-terminal-muted border border-terminal-border hover:text-terminal-text'
              }`}
            >{c}</button>
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
        Simulated results using Yahoo Finance 5m data. <strong>Arlennys Model</strong>: HTF-aligned ICT sweep+iFVG, grade A/A+, 3-day vol regime filter, partial TP at 1R→breakeven (sessions: AM). <strong>OR30 track</strong>: Coach Dakota urgency trade, OR breakout with 1.2× volume (sessions: OR30). 1 trade/day max each track. Past performance ≠ future results.
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
            <StatCard label="Trades" value={stats.total_trades ?? 0} sub={`${data.lookback_days}d · ${data.contracts}×`} />
            <StatCard
              label="Win Rate"
              value={`${stats.win_rate ?? 0}%`}
              sub={`${stats.wins}W · ${stats.losses}L · ${stats.eod_closes ?? 0} EOD`}
              color={stats.win_rate >= 60 ? 'text-terminal-green' : stats.win_rate >= 45 ? 'text-terminal-yellow' : 'text-terminal-red'}
            />
            <StatCard
              label="Monthly Est."
              value={`$${fmt.num(stats.monthly_projection ?? 0)}`}
              sub={`${data.contracts}× ${sym.instrument} · 21 days`}
              color={(stats.monthly_projection ?? 0) >= 3000 ? 'text-terminal-green' : (stats.monthly_projection ?? 0) >= 1500 ? 'text-terminal-yellow' : 'text-terminal-red'}
            />
            <StatCard
              label="Total P&L"
              value={`$${fmt.num(stats.total_pnl ?? 0)}`}
              sub={`${data.lookback_days}d actual`}
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

          {/* Session breakdown */}
          {(() => {
            const ict  = trades.filter(t => t.session === 'AM' || t.session === 'AM2')
            const or30 = trades.filter(t => t.session === 'OR30')
            const ictWR  = ict.length  ? Math.round(ict.filter(t => t.result !== 'loss').length  / ict.length  * 100) : null
            const or30WR = or30.length ? Math.round(or30.filter(t => t.result !== 'loss').length / or30.length * 100) : null
            return (
              <div className="flex gap-2 text-[10px] flex-wrap">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-terminal-card border border-terminal-border rounded">
                  <span className="text-terminal-muted">Arlennys ICT:</span>
                  <span className="font-bold text-terminal-text">{ict.length} trades</span>
                  {ictWR !== null && <span className={ictWR >= 60 ? 'text-terminal-green' : 'text-terminal-red'}>{ictWR}% WR</span>}
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 bg-terminal-card border border-orange-500/20 rounded">
                  <span className="text-terminal-muted">OR30 Urgency:</span>
                  <span className="font-bold text-terminal-text">{or30.length} trades</span>
                  {or30WR !== null && <span className={or30WR >= 60 ? 'text-terminal-green' : 'text-terminal-red'}>{or30WR}% WR</span>}
                  {or30.length === 0 && <span className="text-terminal-muted italic">(fires in normal market — blocked by same vol filter)</span>}
                </div>
              </div>
            )
          })()}

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
                      {['Date', 'Sess', 'Dir', 'HTF', 'Grade', 'Entry', 'Stop', 'Target', 'Exit', 'Pts', 'P&L', 'RR', 'Result', 'Equity'].map(h => (
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
                          <td className="px-3 py-1.5"><SessionBadge session={t.session} /></td>
                          <td className="px-3 py-1.5">
                            <span className={t.direction === 'bullish' ? 'text-terminal-green font-bold' : 'text-terminal-red font-bold'}>
                              {t.direction === 'bullish' ? '▲ L' : '▼ S'}
                            </span>
                          </td>
                          <td className="px-3 py-1.5">
                            <span className={`text-[10px] font-bold ${
                              t.htf_dir?.includes('bullish') ? 'text-terminal-green' :
                              t.htf_dir?.includes('bearish') ? 'text-terminal-red' : 'text-terminal-muted'
                            }`}>
                              {t.htf_dir?.includes('bullish') ? '▲' : t.htf_dir?.includes('bearish') ? '▼' : '—'}
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
                          <td className="px-3 py-1.5"><ResultBadge result={t.result} eod={t.eod} /></td>
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
      )}
    </div>
  )
}

