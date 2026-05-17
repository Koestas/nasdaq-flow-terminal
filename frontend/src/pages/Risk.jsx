import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import { clsx } from 'clsx'
import {
  ShieldAlert, DollarSign, TrendingUp, Target,
  AlertTriangle, CheckCircle, RefreshCw, Calculator
} from 'lucide-react'

const INSTRUMENTS = {
  MNQ: { name: 'Micro NQ', color: 'blue', session: 'NY Killzone', usd_per_pt: 2 },
  MES: { name: 'Micro ES', color: 'purple', session: 'NY Killzone', usd_per_pt: 5 },
  MGC: { name: 'Micro Gold', color: 'yellow', session: 'Asia Session', usd_per_pt: 10 },
}

function StatusBadge({ status, color }) {
  const colors = {
    green: 'bg-terminal-green/20 text-terminal-green border-terminal-green/30',
    red: 'bg-terminal-red/20 text-terminal-red border-terminal-red/30',
    yellow: 'bg-terminal-yellow/20 text-terminal-yellow border-terminal-yellow/30',
    blue: 'bg-terminal-blue/20 text-terminal-blue border-terminal-blue/30',
  }
  return (
    <span className={clsx('inline-flex items-center px-2.5 py-0.5 rounded text-xs font-bold border', colors[color] || colors.blue)}>
      {status}
    </span>
  )
}

function ProgressBar({ value, max, color = 'green', label }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div>
      {label && <div className="flex justify-between text-xs text-terminal-muted mb-1">
        <span>{label}</span><span>{pct.toFixed(0)}%</span>
      </div>}
      <div className="h-2 bg-terminal-border rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-all', {
            'bg-terminal-green': color === 'green',
            'bg-terminal-red': color === 'red',
            'bg-terminal-yellow': color === 'yellow',
            'bg-terminal-blue': color === 'blue',
          })}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function StatRow({ label, value, sub, highlight }) {
  return (
    <div className={clsx('flex items-center justify-between py-2 border-b border-terminal-border/50 last:border-0', highlight && 'bg-terminal-border/20 -mx-3 px-3 rounded')}>
      <span className="text-terminal-muted text-sm">{label}</span>
      <div className="text-right">
        <span className={clsx('font-mono font-semibold text-sm', highlight ? 'text-terminal-text' : 'text-terminal-text')}>{value}</span>
        {sub && <div className="text-xs text-terminal-muted">{sub}</div>}
      </div>
    </div>
  )
}

export default function Risk() {
  const [balance, setBalance] = useState('25000')
  const [prevClose, setPrevClose] = useState('')
  const [instrument, setInstrument] = useState('MNQ')
  const [stopPts, setStopPts] = useState('')
  const [submitted, setSubmitted] = useState({ balance: 25000, prevClose: null })

  const { data: account, isLoading, refetch } = useQuery({
    queryKey: ['risk-account', submitted],
    queryFn: () => {
      const params = new URLSearchParams({ balance: submitted.balance })
      if (submitted.prevClose) params.set('prev_close', submitted.prevClose)
      return apiFetch(`/api/risk/account?${params}`)
    },
    refetchInterval: 30000,
  })

  const { data: sizing } = useQuery({
    queryKey: ['risk-size', submitted, instrument, stopPts],
    queryFn: () => {
      if (!stopPts || isNaN(parseFloat(stopPts))) return null
      const params = new URLSearchParams({
        balance: submitted.balance,
        instrument,
        stop_points: stopPts,
      })
      if (submitted.prevClose) params.set('prev_close', submitted.prevClose)
      return apiFetch(`/api/risk/size?${params}`)
    },
    enabled: !!stopPts && !isNaN(parseFloat(stopPts)),
  })

  const handleSubmit = useCallback(() => {
    const b = parseFloat(balance)
    const pc = prevClose ? parseFloat(prevClose) : null
    if (!isNaN(b)) setSubmitted({ balance: b, prevClose: pc })
  }, [balance, prevClose])

  const status = account?.status_color || 'green'
  const plan = account?.trade_plan

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-terminal-text">Risk Manager</h1>
          <p className="text-sm text-terminal-muted">Lucid 25k Pro · Trailing drawdown · Position sizing</p>
        </div>
        <button onClick={() => refetch()} className="btn btn-ghost gap-1.5 text-xs">
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* Balance input */}
      <div className="card border border-terminal-border">
        <div className="text-xs font-semibold text-terminal-muted uppercase tracking-wider mb-3">Account Balance</div>
        <div className="flex gap-3 flex-wrap">
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs text-terminal-muted mb-1 block">Current Balance ($)</label>
            <input
              type="number"
              value={balance}
              onChange={e => setBalance(e.target.value)}
              className="w-full bg-terminal-bg border border-terminal-border rounded px-3 py-2 text-terminal-text text-sm font-mono focus:outline-none focus:border-terminal-blue"
              placeholder="25000"
            />
          </div>
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs text-terminal-muted mb-1 block">Yesterday's Close ($) — optional</label>
            <input
              type="number"
              value={prevClose}
              onChange={e => setPrevClose(e.target.value)}
              className="w-full bg-terminal-bg border border-terminal-border rounded px-3 py-2 text-terminal-text text-sm font-mono focus:outline-none focus:border-terminal-blue"
              placeholder="same as balance"
            />
          </div>
          <div className="flex items-end">
            <button onClick={handleSubmit} className="btn btn-primary px-5 py-2 text-sm">
              Calculate
            </button>
          </div>
        </div>
      </div>

      {isLoading && <div className="text-terminal-muted text-sm animate-pulse">Loading...</div>}

      {account && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Account Status */}
          <div className="card border border-terminal-border space-y-1">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-semibold text-terminal-muted uppercase tracking-wider">Account Status</div>
              <StatusBadge status={account.status} color={status} />
            </div>

            <StatRow label="Current Balance" value={fmt.currency(account.current_balance)} highlight />
            <StatRow label="Trailing Floor" value={fmt.currency(account.trailing_floor)}
              sub={account.floor_locked ? 'Floor locked — max protection' : 'Floor trailing with profit'} />
            <StatRow label="Daily Risk Remaining" value={fmt.currency(account.daily_risk_remaining)}
              sub={`${account.daily_risk_pct_used}% of $1,000 limit used`} />
            <StatRow label="Daily P&L" value={fmt.currency(account.daily_pnl)}
              highlight={account.daily_pnl !== 0} />

            <div className="pt-2">
              <ProgressBar
                value={(account.rules?.daily_loss_limit || 1000) - account.daily_risk_remaining || 0}
                max={account.rules?.daily_loss_limit || 1000}
                color={account.daily_risk_remaining < 300 ? 'red' : account.daily_risk_remaining < 600 ? 'yellow' : 'green'}
                label="Daily loss limit used"
              />
            </div>
          </div>

          {/* Payout Status */}
          <div className="card border border-terminal-border space-y-1">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-semibold text-terminal-muted uppercase tracking-wider">Payout Progress</div>
              {account.payout_ready
                ? <StatusBadge status="READY" color="green" />
                : <StatusBadge status="BUILDING" color="blue" />}
            </div>

            <StatRow label="Payout Threshold" value={fmt.currency(account.payout_threshold)} />
            <StatRow label="Safe Trigger (buffer)" value={fmt.currency(account.safe_payout_trigger)}
              sub="Ensures $26,500 remains after $1,500 payout" />
            <StatRow label="To Safe Trigger" value={fmt.currency(account.to_safe_trigger)} highlight />
            <StatRow label="Max Payout" value={fmt.currency(account.max_payout)} />

            <div className="pt-2">
              <ProgressBar
                value={account.current_balance - 25000}
                max={account.safe_payout_trigger - 25000}
                color="blue"
                label="Progress to safe payout trigger"
              />
            </div>

            <div className="pt-2 grid grid-cols-3 gap-2 text-center">
              {[['$300/day', account.days_at_300], ['$400/day', account.days_at_400], ['$500/day', account.days_at_500]].map(([label, days]) => (
                <div key={label} className="bg-terminal-bg rounded p-2 border border-terminal-border/50">
                  <div className="text-xs text-terminal-muted">{label}</div>
                  <div className="font-mono font-bold text-terminal-text text-sm">{days === 0 ? '✓' : `${days}d`}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Trade Plan */}
      {plan && (
        <div className={clsx('card border', status === 'red' ? 'border-terminal-red/40 bg-terminal-red/5' : 'border-terminal-border')}>
          <div className="flex items-center gap-2 mb-2">
            {status === 'red'
              ? <AlertTriangle size={15} className="text-terminal-red" />
              : <CheckCircle size={15} className="text-terminal-green" />}
            <span className="text-sm font-semibold text-terminal-text">{plan.recommendation}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="bg-terminal-bg rounded p-2 border border-terminal-border/50">
              <div className="text-terminal-muted">Max Trades</div>
              <div className="font-mono font-bold text-terminal-text text-lg">{plan.max_trades}</div>
            </div>
            <div className="bg-terminal-bg rounded p-2 border border-terminal-border/50">
              <div className="text-terminal-muted">Risk / Trade</div>
              <div className="font-mono font-bold text-terminal-text text-lg">${plan.risk_per_trade?.toFixed(0)}</div>
            </div>
            <div className="bg-terminal-bg rounded p-2 border border-terminal-border/50">
              <div className="text-terminal-muted">Daily Goal</div>
              <div className="font-mono font-bold text-terminal-text text-lg">${plan.daily_goal}</div>
            </div>
            <div className="bg-terminal-bg rounded p-2 border border-terminal-border/50">
              <div className="text-terminal-muted">Instrument</div>
              <div className="font-mono font-bold text-terminal-blue text-lg">{plan.primary_instrument}</div>
            </div>
          </div>
          <p className="text-xs text-terminal-muted mt-2 italic">{plan.note}</p>
        </div>
      )}

      {/* Position Sizer */}
      <div className="card border border-terminal-border">
        <div className="flex items-center gap-2 mb-3">
          <Calculator size={15} className="text-terminal-blue" />
          <span className="text-xs font-semibold text-terminal-muted uppercase tracking-wider">Position Sizer</span>
        </div>

        <div className="flex gap-3 flex-wrap mb-4">
          <div>
            <label className="text-xs text-terminal-muted mb-1 block">Instrument</label>
            <div className="flex gap-1">
              {Object.entries(INSTRUMENTS).map(([key, spec]) => (
                <button
                  key={key}
                  onClick={() => setInstrument(key)}
                  className={clsx('px-3 py-1.5 rounded text-xs font-semibold border transition-colors', instrument === key
                    ? 'bg-terminal-blue/20 text-terminal-blue border-terminal-blue/40'
                    : 'bg-terminal-bg text-terminal-muted border-terminal-border hover:border-terminal-blue/30'
                  )}
                >
                  {key}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 min-w-[120px]">
            <label className="text-xs text-terminal-muted mb-1 block">Stop Distance (points)</label>
            <input
              type="number"
              value={stopPts}
              onChange={e => setStopPts(e.target.value)}
              className="w-full bg-terminal-bg border border-terminal-border rounded px-3 py-1.5 text-terminal-text text-sm font-mono focus:outline-none focus:border-terminal-blue"
              placeholder="e.g. 3.5"
              step="0.5"
            />
          </div>
        </div>

        {/* Instrument info */}
        {instrument && (
          <div className="text-xs text-terminal-muted mb-3 p-2 bg-terminal-bg rounded border border-terminal-border/50">
            <span className="text-terminal-blue font-semibold">{instrument}</span> · {INSTRUMENTS[instrument].name} ·
            <span className="font-mono"> ${INSTRUMENTS[instrument].usd_per_pt}/point</span> ·
            Best session: <span className="text-terminal-yellow">{INSTRUMENTS[instrument].session}</span>
          </div>
        )}

        {sizing?.sizing && !sizing.sizing.error && (
          <div className="space-y-3">
            <div className="p-3 bg-terminal-green/10 border border-terminal-green/30 rounded text-terminal-green font-mono text-sm font-semibold">
              {sizing.sizing.note}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.entries(sizing.sizing.tp_levels || {}).map(([label, tp]) => (
                <div key={label} className="bg-terminal-bg rounded p-2 border border-terminal-border/50 text-center">
                  <div className="text-xs text-terminal-muted">{label}</div>
                  <div className="font-mono font-bold text-terminal-green text-sm">+{tp.points}pts</div>
                  <div className="font-mono text-xs text-terminal-text">+${tp.gain}</div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-2 text-xs text-center">
              <div className="bg-terminal-bg rounded p-2 border border-terminal-border/50">
                <div className="text-terminal-muted">Contracts</div>
                <div className="font-mono font-bold text-terminal-text text-xl">{sizing.sizing.contracts}</div>
              </div>
              <div className="bg-terminal-bg rounded p-2 border border-terminal-border/50">
                <div className="text-terminal-muted">Risk $</div>
                <div className="font-mono font-bold text-terminal-red text-xl">${sizing.sizing.risk_amount?.toFixed(0)}</div>
              </div>
              <div className="bg-terminal-bg rounded p-2 border border-terminal-border/50">
                <div className="text-terminal-muted">$/point</div>
                <div className="font-mono font-bold text-terminal-text text-xl">${sizing.sizing.dollars_per_point}</div>
              </div>
            </div>
          </div>
        )}

        {sizing?.sizing?.error && (
          <div className="text-terminal-red text-sm">{sizing.sizing.error}</div>
        )}
      </div>

      {/* Rules Reference */}
      <div className="card border border-terminal-border/50">
        <div className="text-xs font-semibold text-terminal-muted uppercase tracking-wider mb-3">Lucid 25k Pro Rules</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1 text-xs">
          {[
            ['Starting Balance', '$25,000'],
            ['Daily Loss Limit', '$1,000'],
            ['Floor Trailing', 'Follows profit up'],
            ['Floor Locks At', '$25,100 (max protection)'],
            ['Payout Threshold', '$26,100'],
            ['Max Payout', '$1,500'],
            ['Safe After Payout', '$26,500 remaining'],
            ['Safe Trigger', '$28,000 balance'],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between py-1 border-b border-terminal-border/30">
              <span className="text-terminal-muted">{k}</span>
              <span className="font-mono text-terminal-text">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
