import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import { clsx } from 'clsx'
import {
  Clock, Target, TrendingUp, TrendingDown, Minus,
  AlertTriangle, CheckCircle, XCircle, Zap, BarChart2,
  RefreshCw, ChevronDown, ChevronUp
} from 'lucide-react'
import { useState } from 'react'

function SessionBadge({ session, inKillzone, timeEt }) {
  return (
    <div className={clsx(
      'flex items-center gap-2 px-3 py-2 rounded border text-sm font-mono',
      inKillzone ? 'border-terminal-green/40 bg-terminal-green/10 text-terminal-green'
                 : 'border-terminal-border bg-terminal-card text-terminal-muted'
    )}>
      <Clock size={14} />
      <span className="font-semibold">{timeEt}</span>
      <span className="text-terminal-muted">·</span>
      <span>{session}</span>
      {inKillzone && <span className="ml-auto badge badge-green animate-pulse text-xs">KILLZONE</span>}
    </div>
  )
}

function ZonePill({ zone, pct }) {
  const isPremium = zone === 'premium', isDiscount = zone === 'discount'
  return (
    <div className={clsx('inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold',
      isPremium ? 'bg-terminal-red/20 text-terminal-red border border-terminal-red/30' :
      isDiscount ? 'bg-terminal-green/20 text-terminal-green border border-terminal-green/30' :
      'bg-terminal-border text-terminal-muted')}>
      {isPremium ? <TrendingDown size={11}/> : isDiscount ? <TrendingUp size={11}/> : <Minus size={11}/>}
      {zone === 'premium' ? 'PREMIUM' : zone === 'discount' ? 'DISCOUNT' : 'UNKNOWN'}
      {pct != null && <span className="opacity-70">({pct}%)</span>}
    </div>
  )
}

function DrawArrow({ direction, target, reason }) {
  if (!direction || direction === 'neutral')
    return <div className="text-terminal-muted text-xs italic">No clear draw — neutral</div>
  const up = direction === 'up'
  return (
    <div className={clsx('flex items-center gap-2 text-sm', up ? 'text-terminal-green' : 'text-terminal-red')}>
      {up ? <TrendingUp size={16}/> : <TrendingDown size={16}/>}
      <span className="font-mono font-semibold">{target ? fmt.price(target) : '—'}</span>
      <span className="text-terminal-muted text-xs truncate">{reason}</span>
    </div>
  )
}

function SetupGrade({ grade, score, checklist, title }) {
  const color = grade === 'A+' ? 'text-terminal-green' : grade === 'A' ? 'text-terminal-yellow'
    : grade === 'B' ? 'text-terminal-blue' : 'text-terminal-muted'
  const [open, setOpen] = useState(false)
  return (
    <div className="card border border-terminal-border/50">
      <div className="flex items-center justify-between cursor-pointer" onClick={() => setOpen(o => !o)}>
        <div className="flex items-center gap-2">
          <span className={clsx('text-2xl font-bold font-mono', color)}>{grade}</span>
          <div>
            <div className="text-terminal-text text-sm font-semibold">{title}</div>
            <div className="text-terminal-muted text-xs">{score}/100</div>
          </div>
        </div>
        {open ? <ChevronUp size={14} className="text-terminal-muted"/> : <ChevronDown size={14} className="text-terminal-muted"/>}
      </div>
      {open && (
        <div className="mt-3 space-y-1 border-t border-terminal-border pt-3">
          {checklist?.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              {c.met ? <CheckCircle size={12} className="text-terminal-green shrink-0"/>
                     : <XCircle size={12} className="text-terminal-muted shrink-0"/>}
              <span className={c.met ? 'text-terminal-text' : 'text-terminal-muted'}>{c.item}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function FVGRow({ fvg }) {
  const isBull = fvg.base_type === 'bullish_fvg', isInverted = fvg.inverted
  return (
    <div className={clsx('flex items-center gap-2 text-xs py-1.5 px-2 rounded border',
      isInverted ? (isBull ? 'border-terminal-green/30 bg-terminal-green/5' : 'border-terminal-red/30 bg-terminal-red/5')
                 : 'border-terminal-border/30')}>
      <span className={clsx('font-semibold shrink-0',
        isInverted ? (isBull ? 'text-terminal-green' : 'text-terminal-red') : 'text-terminal-muted')}>
        {isInverted ? 'iFVG' : isBull ? 'FVG↑' : 'FVG↓'}
      </span>
      <span className="font-mono text-terminal-text">{fmt.price(fvg.bottom)} – {fmt.price(fvg.top)}</span>
      <span className="text-terminal-muted ml-auto shrink-0">Δ{fvg.size?.toFixed(2)}</span>
      {fvg.filled && <span className="text-terminal-muted shrink-0">[filled]</span>}
    </div>
  )
}

function LevelRow({ label, value, variant = 'default' }) {
  if (!value) return null
  const c = {default:'text-terminal-text',green:'text-terminal-green',red:'text-terminal-red',
              yellow:'text-terminal-yellow',blue:'text-terminal-blue',muted:'text-terminal-muted'}
  return (
    <div className="flex items-center justify-between text-xs py-1 border-b border-terminal-border/20">
      <span className="text-terminal-muted">{label}</span>
      <span className={clsx('font-mono font-semibold', c[variant])}>{fmt.price(value)}</span>
    </div>
  )
}

function EqualHL({ data }) {
  const all = [
    ...data.equal_highs.map(e => ({ ...e, is_high: true })),
    ...data.equal_lows.map(e => ({ ...e, is_high: false })),
  ].sort((a, b) => b.level - a.level)
  if (!all.length) return <div className="text-terminal-muted text-xs italic">None detected</div>
  return (
    <div className="space-y-1">
      {all.map((e, i) => (
        <div key={i} className={clsx('flex items-center gap-2 text-xs px-2 py-1.5 rounded border',
          e.is_high ? 'border-terminal-red/30 bg-terminal-red/5' : 'border-terminal-green/30 bg-terminal-green/5')}>
          <AlertTriangle size={11} className={e.is_high ? 'text-terminal-red' : 'text-terminal-green'}/>
          <span className={clsx('font-semibold shrink-0', e.is_high ? 'text-terminal-red' : 'text-terminal-green')}>
            {e.is_high ? 'EQH' : 'EQL'}
          </span>
          <span className="font-mono text-terminal-text">{fmt.price(e.level)}</span>
          <span className="text-terminal-muted ml-auto">×{e.count} touches</span>
        </div>
      ))}
    </div>
  )
}

export default function ICT() {
  const [symbol, setSymbol] = useState('QQQ')
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ['ict-analysis', symbol],
    queryFn: () => apiFetch(`/api/ict/analysis?symbol=${symbol}`),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const session = data?.session
  const levels = data?.session_levels || {}
  const dp = data?.discount_premium || {}
  const draw = data?.draw_on_liquidity || {}
  const fvgs = data?.fair_value_gaps || []
  const ifvgs = data?.ifvgs || []
  const obs = data?.order_blocks || []
  const ehl = data?.equal_highs_lows || { equal_highs: [], equal_lows: [] }
  const summary = data?.summary || {}
  const sortedFvgs = [...fvgs].sort((a, b) => (b.inverted ? 1 : 0) - (a.inverted ? 1 : 0))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-terminal-text">ICT / Smart Money</h1>
          <select value={symbol} onChange={e => setSymbol(e.target.value)}
            className="bg-terminal-card border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text">
            {['QQQ','SPY','NVDA','MSFT','AAPL','TSLA','AMD'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          {dataUpdatedAt && <span className="text-xs text-terminal-muted">{fmt.timeAgo(new Date(dataUpdatedAt).toISOString())}</span>}
          <button onClick={() => refetch()} className="flex items-center gap-1 text-xs text-terminal-blue hover:underline">
            <RefreshCw size={11}/> Refresh
          </button>
        </div>
      </div>

      {isLoading ? <div className="h-10 rounded animate-pulse bg-terminal-border/20"/> : session && (
        <div className="flex items-center gap-3 flex-wrap">
          <SessionBadge session={session.session} inKillzone={session.in_killzone} timeEt={session.time_et}/>
          {dp.zone && <ZonePill zone={dp.zone} pct={dp.position_pct}/>}
          {dp.zone_note && <span className="text-xs text-terminal-muted italic hidden sm:block">{dp.zone_note}</span>}
        </div>
      )}
      {session?.session_note && (
        <div className="text-xs text-terminal-muted bg-terminal-card border border-terminal-border/50 rounded px-3 py-2">
          {session.session_note}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Session Levels + DOL + EHL */}
        <div className="space-y-4">
          <div className="card">
            <div className="text-xs font-semibold text-terminal-muted uppercase mb-3">Session Levels</div>
            {isLoading ? <div className="space-y-2">{Array.from({length:6}).map((_,i)=><div key={i} className="h-5 bg-terminal-border/20 rounded animate-pulse"/>)}</div>
            : <div className="space-y-0.5">
                <LevelRow label="Today High" value={levels.today_high} variant="green"/>
                <LevelRow label="Today Low" value={levels.today_low} variant="red"/>
                <LevelRow label="London High" value={levels.london_high} variant="yellow"/>
                <LevelRow label="London Low" value={levels.london_low} variant="yellow"/>
                <LevelRow label="Asia High" value={levels.asia_high} variant="blue"/>
                <LevelRow label="Asia Low" value={levels.asia_low} variant="blue"/>
                <LevelRow label="Pre-mkt High" value={levels.premarket_high} variant="muted"/>
                <LevelRow label="Pre-mkt Low" value={levels.premarket_low} variant="muted"/>
                <LevelRow label="Prev Day High" value={levels.prev_day_high} variant="muted"/>
                <LevelRow label="Prev Day Low" value={levels.prev_day_low} variant="muted"/>
                <LevelRow label="Prev Day Mid" value={levels.prev_day_mid} variant="muted"/>
                <LevelRow label="Equilibrium" value={dp.equilibrium} variant="default"/>
              </div>}
          </div>
          <div className="card">
            <div className="text-xs font-semibold text-terminal-muted uppercase mb-3 flex items-center gap-2">
              <Target size={12}/> Draw on Liquidity
            </div>
            {isLoading ? <div className="h-8 bg-terminal-border/20 rounded animate-pulse"/>
            : <DrawArrow direction={draw.direction} target={draw.target} reason={draw.reason}/>}
          </div>
          <div className="card">
            <div className="text-xs font-semibold text-terminal-muted uppercase mb-3 flex items-center gap-2">
              <AlertTriangle size={12}/> Equal Highs / Lows
            </div>
            {isLoading ? <div className="h-16 bg-terminal-border/20 rounded animate-pulse"/> : <EqualHL data={ehl}/>}
          </div>
        </div>

        {/* Middle: Setup grades + FVGs */}
        <div className="space-y-4">
          {!isLoading && data?.long_setup && data?.short_setup && (
            <div className="grid grid-cols-2 gap-2">
              <SetupGrade grade={data.long_setup.grade} score={data.long_setup.score} checklist={data.long_setup.checklist} title="Long Setup"/>
              <SetupGrade grade={data.short_setup.grade} score={data.short_setup.score} checklist={data.short_setup.checklist} title="Short Setup"/>
            </div>
          )}
          {ifvgs.length > 0 && (
            <div className="card border border-terminal-purple/30">
              <div className="text-xs font-semibold text-terminal-purple uppercase mb-2 flex items-center gap-2">
                <Zap size={12}/> iFVGs — Active Entry Zones ({ifvgs.length})
              </div>
              <div className="space-y-1">{ifvgs.map((f,i) => <FVGRow key={i} fvg={f}/>)}</div>
            </div>
          )}
          <div className="card">
            <div className="text-xs font-semibold text-terminal-muted uppercase mb-3 flex items-center justify-between">
              <span>Fair Value Gaps</span>
              <span className="font-normal text-terminal-muted">↑{summary.unfilled_bullish_fvgs||0} ↓{summary.unfilled_bearish_fvgs||0} total:{summary.total_fvgs||0}</span>
            </div>
            {isLoading ? <div className="space-y-2">{Array.from({length:5}).map((_,i)=><div key={i} className="h-7 bg-terminal-border/20 rounded animate-pulse"/>)}</div>
            : sortedFvgs.length === 0 ? <div className="text-terminal-muted text-xs italic">No FVGs detected</div>
            : <div className="space-y-1 max-h-64 overflow-y-auto">{sortedFvgs.slice(-15).reverse().map((f,i) => <FVGRow key={i} fvg={f}/>)}</div>}
          </div>
        </div>

        {/* Right: Order Blocks + Reference */}
        <div className="space-y-4">
          <div className="card">
            <div className="text-xs font-semibold text-terminal-muted uppercase mb-3 flex items-center gap-2">
              <BarChart2 size={12}/> Order Blocks ({obs.length})
            </div>
            {isLoading ? <div className="space-y-2">{Array.from({length:4}).map((_,i)=><div key={i} className="h-7 bg-terminal-border/20 rounded animate-pulse"/>)}</div>
            : obs.length === 0 ? <div className="text-terminal-muted text-xs italic">No order blocks detected</div>
            : <div className="space-y-1">{[...obs].reverse().map((ob,i) => {
                const isBull = ob.type === 'bullish_ob'
                return (
                  <div key={i} className={clsx('flex items-center gap-2 text-xs px-2 py-1.5 rounded border',
                    isBull ? 'border-terminal-green/30 bg-terminal-green/5' : 'border-terminal-red/30 bg-terminal-red/5')}>
                    <span className={clsx('font-semibold shrink-0', isBull ? 'text-terminal-green' : 'text-terminal-red')}>
                      {isBull ? 'BOB' : 'SOB'}
                    </span>
                    <span className="font-mono text-terminal-text">{fmt.price(ob.low)} – {fmt.price(ob.high)}</span>
                    <span className="text-terminal-muted ml-auto">{isBull ? 'demand' : 'supply'}</span>
                  </div>
                )
              })}</div>}
          </div>
          <div className="card bg-terminal-card2 text-xs space-y-3">
            <div className="text-terminal-text font-semibold text-sm">ICT Sweep & Inverse Model</div>
            <div>
              <div className="text-terminal-green font-semibold mb-1">A+ Long Setup</div>
              <div className="text-terminal-muted space-y-0.5">
                <div>1. Price sweeps EQL or Asia/London Low</div>
                <div>2. Strong bullish displacement candle</div>
                <div>3. iFVG forms in displacement</div>
                <div>4. Price returns to iFVG in NY Killzone</div>
                <div>5. Target: EQH / session high / DOL</div>
              </div>
            </div>
            <div>
              <div className="text-terminal-red font-semibold mb-1">A+ Short Setup</div>
              <div className="text-terminal-muted space-y-0.5">
                <div>1. Price sweeps EQH or Asia/London High</div>
                <div>2. Strong bearish displacement candle</div>
                <div>3. iFVG forms in displacement</div>
                <div>4. Price returns to iFVG in NY Killzone</div>
                <div>5. Target: EQL / session low / DOL</div>
              </div>
            </div>
            <div className="border-t border-terminal-border pt-2">
              <div className="text-terminal-yellow font-semibold mb-1">No Trade Conditions</div>
              <div className="text-terminal-muted space-y-0.5">
                <div>• Outside NY Killzone (9:30–11:30 AM ET)</div>
                <div>• Friday after 11:30 AM / Monday pre-market</div>
                <div>• Price at equilibrium (50% range) — no edge</div>
                <div>• No clear draw on liquidity identified</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
