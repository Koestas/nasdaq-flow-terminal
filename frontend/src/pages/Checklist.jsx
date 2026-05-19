import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { CheckCircle2, Circle, RefreshCw, Crosshair, AlertCircle } from 'lucide-react'

function CheckItem({ label, met, detail, critical }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-terminal-border/30 last:border-0">
      <span className={`shrink-0 mt-0.5 ${met ? 'text-terminal-green' : 'text-terminal-muted'}`}>
        {met ? <CheckCircle2 size={15} /> : <Circle size={15} />}
      </span>
      <div className="flex-1 min-w-0">
        <div className={`text-xs font-medium ${met ? 'text-terminal-text' : 'text-terminal-muted'}`}>{label}</div>
        {detail && <div className={`text-[10px] mt-0.5 ${met ? 'text-terminal-muted' : 'text-terminal-muted/60'}`}>{detail}</div>}
      </div>
      {critical && !met && (
        <span className="text-[9px] text-terminal-red border border-terminal-red/30 px-1.5 py-0.5 rounded shrink-0">REQUIRED</span>
      )}
    </div>
  )
}

function Verdict({ score, total, direction }) {
  const pct = total > 0 ? score / total : 0
  if (pct >= 0.85) return (
    <div className="bg-terminal-green/10 border border-terminal-green/30 rounded-lg p-4 text-center">
      <div className="text-terminal-green font-bold text-base">STRONG SETUP — Consider Entry</div>
      <div className="text-xs text-terminal-muted mt-1">{score}/{total} criteria met</div>
      {direction !== 'neutral' && (
        <div className={`text-sm font-bold mt-2 ${direction === 'bullish' ? 'text-terminal-green' : 'text-terminal-red'}`}>
          {direction === 'bullish' ? '▲ LONG' : '▼ SHORT'}
        </div>
      )}
    </div>
  )
  if (pct >= 0.65) return (
    <div className="bg-terminal-yellow/10 border border-terminal-yellow/30 rounded-lg p-4 text-center">
      <div className="text-terminal-yellow font-bold text-base">MODERATE — Wait for Confirmation</div>
      <div className="text-xs text-terminal-muted mt-1">{score}/{total} criteria met — patience is a position</div>
    </div>
  )
  return (
    <div className="bg-terminal-red/10 border border-terminal-red/30 rounded-lg p-4 text-center">
      <div className="text-terminal-red font-bold text-base">NO TRADE — Conditions Not Met</div>
      <div className="text-xs text-terminal-muted mt-1">{score}/{total} criteria met — wait for a clean setup</div>
    </div>
  )
}

function inKillzone() {
  const et = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }))
  const day = et.getDay()
  if (day === 0 || day === 6) return false
  const mins = et.getHours() * 60 + et.getMinutes()
  return mins >= 9 * 60 + 30 && mins <= 11 * 60 + 30
}

export default function Checklist() {
  const { data: analysis, isLoading: aLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ['checklist-analysis'],
    queryFn: () => apiFetch('/api/ict/analysis?symbol=QQQ'),
    refetchInterval: 60_000,
  })
  const { data: advanced, isLoading: advLoading } = useQuery({
    queryKey: ['checklist-advanced'],
    queryFn: () => apiFetch('/api/ict/advanced?symbol=QQQ'),
    refetchInterval: 60_000,
  })
  const { data: calendar } = useQuery({
    queryKey: ['calendar'],
    queryFn: () => apiFetch('/api/market/calendar'),
    refetchInterval: 300_000,
  })

  const loading = aLoading || advLoading
  const kz = inKillzone()

  const htf      = analysis?.htf_bias || {}
  const htfBias  = htf.bias || ''
  const htfOk    = htfBias && !htfBias.includes('neutral')

  const longSc   = analysis?.long_setup?.score  || 0
  const shortSc  = analysis?.short_setup?.score || 0
  const direction = longSc > shortSc ? 'bullish' : shortSc > longSc ? 'bearish' : 'neutral'
  const activeSetup = direction === 'bullish' ? analysis?.long_setup : analysis?.short_setup
  const grade    = activeSetup?.grade || ''
  const gradeOk  = grade === 'A+' || grade === 'A'
  const score    = Math.max(longSc, shortSc)

  const ifvgs        = analysis?.ifvgs || []
  const alignedIfvgs = ifvgs.filter(f => direction !== 'neutral' && (f.base_type || '').includes(direction))
  const ifvgOk       = alignedIfvgs.length > 0

  const sweeps      = advanced?.liquidity_sweeps || []
  const freshSweeps = sweeps.filter(s => s.is_fresh && (s.direction === direction || direction === 'neutral'))
  const sweepOk     = freshSweeps.length > 0
  const topSweep    = freshSweeps[0]
  const sweepDetail = topSweep
    ? `${topSweep.label} — ${topSweep.minutes_ago}min ago`
    : 'No fresh sweep in setup direction'

  const displacement  = sweeps.some(s => s.displacement_confirmed && (s.direction === direction || direction === 'neutral'))
  const dispDetail    = displacement ? 'Displacement candle confirmed after sweep' : 'No displacement candle detected yet'

  const dol     = analysis?.draw_on_liquidity || {}
  const dolOk   = dol.target != null && dol.direction !== 'neutral'
  const dolDetail = dolOk ? `${dol.direction?.toUpperCase()} to ${Number(dol.target).toFixed(2)} — ${dol.reason || ''}` : 'No clear liquidity target'

  const mss       = advanced?.mss_choch || {}
  const struct    = mss.last_structure || ''
  const structOk  = direction !== 'neutral' && (
    (direction === 'bullish' && struct.toLowerCase().includes('bullish')) ||
    (direction === 'bearish' && struct.toLowerCase().includes('bearish'))
  )
  const structDetail = struct || 'No market structure break detected'

  const highImpact  = calendar?.high_impact_count ?? (calendar?.events?.filter(e => e.impact === 'high')?.length ?? 0)
  const calOk       = highImpact === 0
  const calDetail   = highImpact > 0
    ? `${highImpact} high-impact USD event(s) today — exercise caution`
    : 'No high-impact events scheduled today'

  const criteria = [
    { label: 'NY Killzone Active (9:30–11:30 AM ET)',  met: kz,         detail: kz ? 'Window open — best setups occur here' : 'Outside killzone — setups less reliable',        critical: true  },
    { label: 'HTF Daily Bias Defined (not neutral)',   met: htfOk,      detail: htfBias ? `Daily bias: ${htfBias}` : 'No clear daily trend',                                  critical: true  },
    { label: 'Setup Grade A or A+ (score ≥55)',        met: gradeOk,    detail: grade ? `Grade: ${grade} · Score: ${score}/100` : 'No qualifying setup detected',             critical: true  },
    { label: 'Fresh Liquidity Sweep Detected',         met: sweepOk,    detail: sweepDetail,                                                                                   critical: true  },
    { label: 'Displacement Candle Confirmed',          met: displacement, detail: dispDetail,                                                                                   critical: false },
    { label: 'Inverted FVG (Entry Zone) Aligned',      met: ifvgOk,     detail: ifvgOk ? `${alignedIfvgs.length} iFVG(s) in ${direction} direction` : 'No aligned iFVGs',     critical: true  },
    { label: 'Draw on Liquidity (DOL) Target Clear',   met: dolOk,      detail: dolDetail,                                                                                     critical: false },
    { label: 'Market Structure Supports Direction',    met: structOk,   detail: structDetail,                                                                                  critical: false },
    { label: 'No High-Impact Economic Events Today',   met: calOk,      detail: calDetail,                                                                                     critical: false },
  ]

  const metCount = criteria.filter(c => c.met).length

  return (
    <div className="flex flex-col gap-4">

      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Crosshair size={16} className="text-terminal-blue" />
          <span className="text-terminal-blue font-bold text-sm">PRE-TRADE CHECKLIST</span>
          <span className="text-terminal-muted text-xs">— ICT / SMC setup verification</span>
        </div>
        <div className="ml-auto flex items-center gap-2 text-[10px] text-terminal-muted">
          {dataUpdatedAt && <span>Updated {new Date(dataUpdatedAt).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit' })} ET</span>}
          <button onClick={() => refetch()} className="text-terminal-muted hover:text-terminal-blue transition-colors">
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {/* Active direction banner */}
      {!loading && direction !== 'neutral' && (
        <div className={`flex items-center gap-2 px-3 py-2 rounded border text-xs font-medium
          ${direction === 'bullish'
            ? 'bg-terminal-green/10 border-terminal-green/30 text-terminal-green'
            : 'bg-terminal-red/10 border-terminal-red/30 text-terminal-red'}`}>
          <span>{direction === 'bullish' ? '▲' : '▼'} Bias: <strong>{direction.toUpperCase()}</strong></span>
          {grade && <span className="ml-2 opacity-70">· Grade {grade} · {score}/100</span>}
          {kz && <span className="ml-auto text-[10px] animate-pulse font-bold">● NY KILLZONE ACTIVE</span>}
        </div>
      )}

      {!loading && !highImpact === false && highImpact > 0 && (
        <div className="flex items-start gap-2 px-3 py-2 bg-terminal-red/5 border border-terminal-red/20 rounded text-xs text-terminal-red/90">
          <AlertCircle size={12} className="shrink-0 mt-0.5" />
          High-impact USD events today — widen stops or sit out
        </div>
      )}

      {/* Checklist */}
      <div className="bg-terminal-card border border-terminal-border rounded-lg overflow-hidden">
        <div className="px-4 py-2 border-b border-terminal-border bg-terminal-bg text-[10px] text-terminal-muted uppercase tracking-wider flex items-center justify-between">
          <span>ICT Setup Criteria</span>
          <span className={`font-bold ${metCount >= 7 ? 'text-terminal-green' : metCount >= 5 ? 'text-terminal-yellow' : 'text-terminal-red'}`}>
            {metCount}/{criteria.length} met
          </span>
        </div>
        <div className="px-4">
          {loading ? (
            <div className="flex items-center justify-center h-40 text-terminal-muted text-xs animate-pulse">
              Fetching market data…
            </div>
          ) : (
            criteria.map((c, i) => <CheckItem key={i} {...c} />)
          )}
        </div>
      </div>

      {!loading && <Verdict score={metCount} total={criteria.length} direction={direction} />}

      {/* Entry sequence quick-ref */}
      <div className="bg-terminal-card border border-terminal-border rounded-lg p-4">
        <div className="text-[10px] text-terminal-muted uppercase tracking-wider font-semibold mb-3">ICT Entry Sequence (Order Matters)</div>
        <div className="space-y-1.5 text-xs text-terminal-muted">
          <div><span className="text-terminal-blue font-mono mr-2">1.</span> HTF daily bias → defines which direction to trade today</div>
          <div><span className="text-terminal-blue font-mono mr-2">2.</span> Wait for NY Killzone window (9:30–11:30 AM ET)</div>
          <div><span className="text-terminal-blue font-mono mr-2">3.</span> Sweep of Asia or London session H/L → liquidity taken</div>
          <div><span className="text-terminal-blue font-mono mr-2">4.</span> Displacement candle → confirms smart money involvement</div>
          <div><span className="text-terminal-blue font-mono mr-2">5.</span> Retest of iFVG zone → enter at midpoint of the gap</div>
          <div><span className="text-terminal-blue font-mono mr-2">6.</span> DOL (Equal Highs/Lows, PDH/PDL) → target for take-profit</div>
          <div><span className="text-terminal-muted font-mono mr-2">★</span> <span className="text-terminal-yellow">Min R:R 2:1 · Stop beyond sweep wick · Max 2 attempts/day</span></div>
        </div>
      </div>

    </div>
  )
}
