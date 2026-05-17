import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'
import { apiFetch, fmt } from '../lib/api'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, GraduationCap } from 'lucide-react'

const SYMBOLS = ['QQQ', 'SPY', 'GC=F']
const INTERVALS = ['1m', '5m', '15m', '30m', '1h']

// Returns "YYYY-MM-DDTHH:mm" defaulting to last weekday at 10:00 AM
function defaultEndTime() {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() - 1)
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const dy = String(d.getDate()).padStart(2, '0')
  return `${y}-${mo}-${dy}T10:00`
}

function shiftTime(iso16, minutes) {
  const dt = new Date(`${iso16}:00`)
  dt.setMinutes(dt.getMinutes() + minutes)
  const y  = dt.getFullYear()
  const mo = String(dt.getMonth() + 1).padStart(2, '0')
  const dy = String(dt.getDate()).padStart(2, '0')
  const h  = String(dt.getHours()).padStart(2, '0')
  const m  = String(dt.getMinutes()).padStart(2, '0')
  return `${y}-${mo}-${dy}T${h}:${m}`
}

function toUnix(isoTime) {
  return Math.floor(new Date(isoTime).getTime() / 1000)
}

// ── Check badge ───────────────────────────────────────────────────────────────
function Check({ ok, label }) {
  return (
    <div className={`flex items-center gap-1.5 text-xs ${ok ? 'text-green-400' : 'text-slate-500'}`}>
      <span className="text-[10px]">{ok ? '✓' : '○'}</span>
      <span>{label}</span>
    </div>
  )
}

// ── Coach panel ───────────────────────────────────────────────────────────────
function CoachPanel({ data }) {
  if (!data) return (
    <div className="flex items-center justify-center h-full text-terminal-muted text-sm">
      Pick a date and load the chart to begin
    </div>
  )

  const long_s  = data.long_setup  || {}
  const short_s = data.short_setup || {}
  const long_cl  = long_s.checklist  || []
  const short_cl = short_s.checklist || []
  const sess = data.session || {}
  const po3  = data.po3_phase || {}
  const sweeps = (data.liquidity_sweeps || []).slice(-3)
  const dol  = data.draw_on_liquidity || {}
  const dp   = data.discount_premium  || {}
  const mss  = data.mss_choch || {}
  const ote  = data.ote_zone  || {}
  const smt  = data.smt_divergence || {}
  const in_ote = data.in_ote

  return (
    <div className="flex flex-col gap-3 h-full overflow-y-auto text-xs">
      {/* Price + time */}
      <div className="flex items-center justify-between">
        <span className="text-terminal-muted">{data.end_time_label}</span>
        <span className="font-bold text-terminal-text text-sm">{fmt.num(data.current_price)}</span>
      </div>

      {/* Session + PO3 */}
      <div className="bg-terminal-card border border-terminal-border rounded p-2 flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <span className="text-terminal-muted uppercase tracking-wider text-[10px]">Session</span>
          {sess.in_killzone
            ? <span className="text-green-400 animate-pulse text-[10px] font-bold">NY KILLZONE</span>
            : <span className="text-yellow-400 text-[10px]">Outside Killzone</span>}
        </div>
        <span className="text-terminal-text">{sess.session || '—'}</span>
        {po3.phase_label && (
          <span className="text-blue-400">PO3: {po3.phase_label}</span>
        )}
      </div>

      {/* Zone + DOL */}
      <div className="bg-terminal-card border border-terminal-border rounded p-2 flex flex-col gap-1">
        <span className="text-terminal-muted uppercase tracking-wider text-[10px]">Zone & DOL</span>
        {dp.zone && (
          <span className={dp.zone === 'discount' ? 'text-green-400' : 'text-red-400'}>
            {dp.zone.toUpperCase()} ({dp.position_pct?.toFixed(1)}% of range)
          </span>
        )}
        {dol.direction && dol.direction !== 'neutral' ? (
          <span className="text-cyan-400">
            DOL {dol.direction === 'up' ? '↑' : '↓'} {fmt.num(dol.target)} — {dol.reason}
          </span>
        ) : (
          <span className="text-terminal-muted">DOL: Neutral</span>
        )}
      </div>

      {/* Sweeps */}
      <div className="bg-terminal-card border border-terminal-border rounded p-2 flex flex-col gap-1">
        <span className="text-terminal-muted uppercase tracking-wider text-[10px]">Liquidity Sweeps</span>
        {sweeps.length > 0 ? sweeps.map((s, i) => (
          <div key={i} className="flex items-start gap-1">
            <span className={s.direction === 'bullish' ? 'text-green-400' : 'text-red-400'}>
              {s.direction === 'bullish' ? '↑' : '↓'}
            </span>
            <span className="text-terminal-text leading-snug">{s.description}</span>
          </div>
        )) : (
          <span className="text-slate-500">No sweeps yet — waiting for a key level to be swept</span>
        )}
      </div>

      {/* iFVGs */}
      <div className="bg-terminal-card border border-terminal-border rounded p-2 flex flex-col gap-1">
        <span className="text-terminal-muted uppercase tracking-wider text-[10px]">iFVG Entry Zones</span>
        {(data.ifvgs || []).length > 0 ? (data.ifvgs || []).slice(0, 3).map((f, i) => (
          <div key={i} className="text-yellow-400">
            iFVG {f.bottom?.toFixed(2)} – {f.top?.toFixed(2)}
            <span className="text-terminal-muted ml-1">({f.type})</span>
          </div>
        )) : (
          <span className="text-slate-500">None — needs sweep + displacement to form</span>
        )}
      </div>

      {/* Structure + OTE */}
      <div className="bg-terminal-card border border-terminal-border rounded p-2 flex flex-col gap-1">
        <span className="text-terminal-muted uppercase tracking-wider text-[10px]">Structure & OTE</span>
        <span className={
          mss.last_structure?.includes('bullish') ? 'text-green-400' :
          mss.last_structure?.includes('bearish') ? 'text-red-400' : 'text-terminal-muted'
        }>
          MSS: {(mss.last_structure || 'unknown').replace(/_/g, ' ').toUpperCase()}
        </span>
        {in_ote ? (
          <span className="text-yellow-400 font-semibold">★ IN OTE ZONE (0.618–0.786)</span>
        ) : ote.ote_top ? (
          <span className="text-terminal-muted">
            OTE at {ote.ote_bottom?.toFixed(2)}–{ote.ote_top?.toFixed(2)} ({ote.direction})
          </span>
        ) : null}
        {smt.detected && (
          <span className={smt.type === 'bullish' ? 'text-green-400' : 'text-red-400'}>
            SMT Divergence: {smt.type?.toUpperCase()}
          </span>
        )}
      </div>

      {/* Checklist */}
      <div className="bg-terminal-card border border-terminal-border rounded p-2 flex flex-col gap-2">
        <span className="text-terminal-muted uppercase tracking-wider text-[10px]">A+ Setup Checklist</span>
        <div className="flex flex-col gap-1">
          <span className="text-green-400 text-[10px] font-semibold">LONG ({long_s.grade || '--'} · {long_s.score ?? '--'}/100)</span>
          {long_cl.length > 0 ? long_cl.map((item, i) => (
            <Check key={i} ok={item.met} label={item.label || item.name || JSON.stringify(item)} />
          )) : <span className="text-terminal-muted text-[10px]">No checklist data</span>}
        </div>
        <div className="flex flex-col gap-1 mt-1">
          <span className="text-red-400 text-[10px] font-semibold">SHORT ({short_s.grade || '--'} · {short_s.score ?? '--'}/100)</span>
          {short_cl.length > 0 ? short_cl.map((item, i) => (
            <Check key={i} ok={item.met} label={item.label || item.name || JSON.stringify(item)} />
          )) : <span className="text-terminal-muted text-[10px]">No checklist data</span>}
        </div>
      </div>

      {/* Coaching narrative */}
      <div className="bg-terminal-card border border-terminal-border rounded p-2">
        <span className="text-terminal-muted uppercase tracking-wider text-[10px] block mb-2">ICT Coach</span>
        <pre className="text-[10px] text-terminal-text whitespace-pre-wrap font-mono leading-relaxed">
          {data.coaching_narrative}
        </pre>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Learn() {
  const [symbol,       setSymbol]       = useState('QQQ')
  const [interval,     setInterval]     = useState('5m')
  const [endTime,      setEndTime]      = useState(defaultEndTime)
  const [hovered,      setHovered]      = useState(null)
  // loadedParams drives the actual query — set explicitly so step buttons work correctly
  const [loadedParams, setLoadedParams] = useState(null)

  const chartContainerRef = useRef(null)
  const chartRef  = useRef(null)
  const candleRef = useRef(null)
  const volumeRef = useRef(null)
  const linesRef  = useRef([])

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['learn', loadedParams?.symbol, loadedParams?.interval, loadedParams?.endTime],
    queryFn: () => apiFetch(
      `/api/learn/replay?symbol=${encodeURIComponent(loadedParams.symbol)}&interval=${loadedParams.interval}&end_time=${encodeURIComponent(loadedParams.endTime)}&lookback_days=5`
    ),
    enabled: !!loadedParams,
    staleTime: Infinity,
    retry: false,
  })

  // Load current inputs
  function load() {
    setLoadedParams({ symbol, interval, endTime })
  }

  // Advance time in the input AND trigger a new fetch immediately
  function stepAndLoad(minutes) {
    const newTime = shiftTime(endTime, minutes)
    setEndTime(newTime)
    setLoadedParams({ symbol, interval, endTime: newTime })
  }

  // ── Create chart ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 460,
      layout: { background: { type: 'solid', color: '#0D0F14' }, textColor: '#94A3B8' },
      grid:   { vertLines: { color: '#1E2129' }, horzLines: { color: '#1E2129' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#1E2129' },
      timeScale: { borderColor: '#1E2129', timeVisible: true, secondsVisible: false },
    })

    const candle = chart.addCandlestickSeries({
      upColor: '#10B981', downColor: '#EF4444',
      borderUpColor: '#10B981', borderDownColor: '#EF4444',
      wickUpColor: '#10B981', wickDownColor: '#EF4444',
    })

    const volume = chart.addHistogramSeries({
      priceFormat: { type: 'volume' }, priceScaleId: 'volume',
    })
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })

    chartRef.current  = chart
    candleRef.current = candle
    volumeRef.current = volume

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) { setHovered(null); return }
      const c = param.seriesData.get(candle)
      if (c) {
        const v = param.seriesData.get(volume)
        setHovered({ open: c.open, high: c.high, low: c.low, close: c.close, volume: v?.value ?? null })
      }
    })

    const ro = new ResizeObserver((entries) => {
      for (const e of entries) chart.applyOptions({ width: e.contentRect.width })
    })
    ro.observe(chartContainerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = candleRef.current = volumeRef.current = null
    }
  }, [])

  // ── Render data + overlays when learn data arrives ─────────────────────────
  useEffect(() => {
    if (!data || !candleRef.current) return

    const bars = (data.bars || [])
      .filter((b) => b.open != null && b.close != null)
      .map((b) => ({ time: toUnix(b.time), open: b.open, high: b.high, low: b.low, close: b.close }))
      .sort((a, b) => a.time - b.time)

    const vols = (data.bars || [])
      .filter((b) => b.open != null && b.close != null)
      .map((b) => ({ time: toUnix(b.time), value: b.volume || 0, color: b.close >= b.open ? '#10B981cc' : '#EF4444cc' }))
      .sort((a, b) => a.time - b.time)

    try { candleRef.current.setData(bars) }   catch (e) { console.error(e) }
    try { volumeRef.current.setData(vols) }   catch (e) { console.error(e) }
    if (chartRef.current) chartRef.current.timeScale().fitContent()

    // Clear old price lines
    linesRef.current.forEach((pl) => { try { candleRef.current.removePriceLine(pl) } catch (_) {} })
    linesRef.current = []

    const addLine = (price, color, label, style, width = 1) => {
      if (price == null) return
      try {
        const pl = candleRef.current.createPriceLine({ price, color, lineWidth: width, lineStyle: style, axisLabelVisible: true, title: label })
        linesRef.current.push(pl)
      } catch (_) {}
    }

    const sl = data.session_levels || {}
    addLine(sl.asia_high,     '#3B82F6', 'Asia H',  LineStyle.Dashed)
    addLine(sl.asia_low,      '#3B82F6', 'Asia L',  LineStyle.Dashed)
    addLine(sl.london_high,   '#F97316', 'London H',LineStyle.Dashed)
    addLine(sl.london_low,    '#F97316', 'London L',LineStyle.Dashed)
    addLine(sl.prev_day_high, '#6B7280', 'PDH',     LineStyle.Dotted)
    addLine(sl.prev_day_low,  '#6B7280', 'PDL',     LineStyle.Dotted)
    addLine(sl.today_high,    '#E2E8F0', 'Today H', LineStyle.Solid)
    addLine(sl.today_low,     '#E2E8F0', 'Today L', LineStyle.Solid)

    // FVGs
    ;(data.fvgs || []).filter((f) => !f.filled && !f.inverted).slice(0, 6).forEach((f) => {
      const c = f.type === 'bullish' ? '#10B981bb' : '#EF4444bb'
      addLine(f.top,    c, `FVG${f.type === 'bullish' ? '↑' : '↓'} T`, LineStyle.Dashed)
      addLine(f.bottom, c, `FVG${f.type === 'bullish' ? '↑' : '↓'} B`, LineStyle.Dashed)
    })

    // iFVGs
    ;(data.ifvgs || []).slice(0, 4).forEach((f) => {
      addLine(f.top,    '#F59E0B', 'iFVG ↑', LineStyle.Solid, 2)
      addLine(f.bottom, '#F59E0B', 'iFVG ↓', LineStyle.Solid, 2)
    })

    // OBs
    ;(data.order_blocks?.bullish || []).slice(0, 3).forEach((ob) => {
      addLine(ob.high, '#10B981', 'OB H (Demand)', LineStyle.Solid, 2)
      addLine(ob.low,  '#10B981', 'OB L (Demand)', LineStyle.Solid, 2)
    })
    ;(data.order_blocks?.bearish || []).slice(0, 3).forEach((ob) => {
      addLine(ob.high, '#EF4444', 'OB H (Supply)', LineStyle.Solid, 2)
      addLine(ob.low,  '#EF4444', 'OB L (Supply)', LineStyle.Solid, 2)
    })

    // Equal H/L
    const ehl = data.equal_hl || {}
    ;(ehl.equal_highs || []).forEach((e) => addLine(e.level, '#A78BFA', `EQH ×${e.count}`, LineStyle.Dotted))
    ;(ehl.equal_lows  || []).forEach((e) => addLine(e.level, '#A78BFA', `EQL ×${e.count}`, LineStyle.Dotted))

    // DOL
    const dol = data.draw_on_liquidity || {}
    if (dol.target && dol.direction !== 'neutral') {
      addLine(dol.target, dol.direction === 'up' ? '#38BDF8' : '#F87171', `DOL ${dol.direction === 'up' ? '↑' : '↓'}`, LineStyle.Solid, 2)
    }
  }, [data])

  const isUp = hovered ? hovered.close >= hovered.open : true

  return (
    <div className="flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <GraduationCap size={16} className="text-terminal-blue" />
        <span className="text-terminal-blue font-bold text-sm">LEARN / PRACTICE MODE</span>
        <span className="text-terminal-muted text-xs ml-2">
          Step through historical price action — the ICT coach explains each signal in real time
        </span>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2 flex-wrap bg-terminal-card border border-terminal-border rounded p-2">
        {/* Symbol */}
        <div className="flex gap-1">
          {SYMBOLS.map((s) => (
            <button key={s} onClick={() => setSymbol(s)}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                symbol === s ? 'bg-terminal-blue text-white' : 'bg-terminal-bg text-terminal-muted border border-terminal-border hover:text-terminal-text'
              }`}
            >{s}</button>
          ))}
        </div>

        <div className="w-px h-5 bg-terminal-border" />

        {/* Interval */}
        <div className="flex gap-1">
          {INTERVALS.map((iv) => (
            <button key={iv} onClick={() => setInterval(iv)}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                interval === iv ? 'bg-terminal-blue text-white' : 'bg-terminal-bg text-terminal-muted border border-terminal-border hover:text-terminal-text'
              }`}
            >{iv}</button>
          ))}
        </div>

        <div className="w-px h-5 bg-terminal-border" />

        {/* Date-time picker */}
        <input
          type="datetime-local"
          value={endTime}
          onChange={(e) => setEndTime(e.target.value)}
          className="bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text focus:outline-none focus:border-terminal-blue"
          style={{ colorScheme: 'dark' }}
        />

        {/* Load button */}
        <button onClick={load}
          className="px-3 py-1 bg-terminal-blue text-white rounded text-xs font-semibold hover:bg-blue-500 transition-colors"
        >
          {isLoading || isFetching ? 'Loading...' : 'Load'}
        </button>

        <div className="w-px h-5 bg-terminal-border" />

        {/* Step controls */}
        <div className="flex items-center gap-1">
          <button onClick={() => stepAndLoad(-1440)} title="Back 1 day"  className="step-btn"><ChevronsLeft size={12} /></button>
          <button onClick={() => stepAndLoad(-60)}  title="Back 1 hour" className="step-btn"><ChevronLeft  size={12} /><span className="text-[10px]">1h</span></button>
          <button onClick={() => stepAndLoad(-15)}  title="Back 15 min" className="step-btn"><ChevronLeft  size={12} /><span className="text-[10px]">15m</span></button>
          <button onClick={() => stepAndLoad(-5)}   title="Back 5 min"  className="step-btn"><ChevronLeft  size={12} /><span className="text-[10px]">5m</span></button>
          <button onClick={() => stepAndLoad(5)}    title="Fwd 5 min"   className="step-btn"><span className="text-[10px]">5m</span><ChevronRight size={12} /></button>
          <button onClick={() => stepAndLoad(15)}   title="Fwd 15 min"  className="step-btn"><span className="text-[10px]">15m</span><ChevronRight size={12} /></button>
          <button onClick={() => stepAndLoad(60)}   title="Fwd 1 hour"  className="step-btn"><span className="text-[10px]">1h</span><ChevronRight size={12} /></button>
          <button onClick={() => stepAndLoad(1440)} title="Fwd 1 day"   className="step-btn"><ChevronsRight size={12} /></button>
        </div>

        <div className="ml-auto text-xs text-terminal-muted">
          {data && `${data.bar_count} bars · ${data.end_time_label}`}
          {(isLoading || isFetching) && <span className="text-terminal-yellow animate-pulse ml-2">fetching...</span>}
        </div>
      </div>

      {/* Two-column layout: chart + coach */}
      <div className="flex gap-3 items-start">
        {/* Left: chart */}
        <div className="flex-1 flex flex-col gap-2 min-w-0">
          {/* OHLCV strip */}
          <div className="flex items-center gap-3 px-3 py-1.5 bg-terminal-card border border-terminal-border rounded text-xs font-mono h-7">
            {hovered ? (
              <>
                <span className="text-terminal-muted">O</span><span className={isUp ? 'text-green-400' : 'text-red-400'}>{fmt.num(hovered.open)}</span>
                <span className="text-terminal-muted">H</span><span className="text-green-400">{fmt.num(hovered.high)}</span>
                <span className="text-terminal-muted">L</span><span className="text-red-400">{fmt.num(hovered.low)}</span>
                <span className="text-terminal-muted">C</span><span className={`font-bold ${isUp ? 'text-green-400' : 'text-red-400'}`}>{fmt.num(hovered.close)}</span>
              </>
            ) : <span className="text-terminal-muted">Hover to see OHLCV</span>}
          </div>

          {/* Chart */}
          <div className="relative bg-terminal-card border border-terminal-border rounded overflow-hidden">
            {(isLoading || isFetching) && (
              <div className="absolute inset-0 flex items-center justify-center bg-terminal-bg/80 z-10">
                <div className="flex flex-col items-center gap-2">
                  <div className="w-8 h-8 border-2 border-terminal-blue border-t-transparent rounded-full animate-spin" />
                  <span className="text-terminal-muted text-xs">Loading replay data...</span>
                </div>
              </div>
            )}
            {!data && !isLoading && (
              <div className="absolute inset-0 flex items-center justify-center z-10">
                <div className="text-center">
                  <GraduationCap size={32} className="text-terminal-muted mx-auto mb-2" />
                  <p className="text-terminal-muted text-sm">Select a symbol, interval, and date</p>
                  <p className="text-terminal-muted text-xs mt-1">Then click <strong className="text-terminal-text">Load</strong> to start the session</p>
                </div>
              </div>
            )}
            <div ref={chartContainerRef} style={{ width: '100%', height: '460px' }} />
          </div>

          {/* Signal summary bar */}
          {data && (
            <div className="flex items-center gap-4 px-3 py-1.5 bg-terminal-card border border-terminal-border rounded text-xs flex-wrap">
              {(() => {
                const sl = data.session_levels || {}
                const s = data.long_setup || {}
                const ss = data.short_setup || {}
                return (
                  <>
                    {sl.prev_day_high && <span><span className="text-slate-400">PDH/PDL</span> <span className="text-green-400">{fmt.num(sl.prev_day_high)}</span> / <span className="text-red-400">{fmt.num(sl.prev_day_low)}</span></span>}
                    {sl.today_high    && <span><span className="text-slate-300">Today</span> <span className="text-green-400">{fmt.num(sl.today_high)}</span> / <span className="text-red-400">{fmt.num(sl.today_low)}</span></span>}
                    {data.discount_premium?.zone && <span className={data.discount_premium.zone === 'discount' ? 'text-green-400' : 'text-red-400'}>{data.discount_premium.zone.toUpperCase()}</span>}
                    <span><span className="text-yellow-400">iFVG</span> <span className="text-terminal-text">{(data.ifvgs || []).length}</span></span>
                    <span><span className="text-slate-400">Long</span> <span className={s.grade === 'A+' || s.grade === 'A' ? 'text-green-400' : 'text-terminal-muted'}>{s.grade || '--'}</span></span>
                    <span><span className="text-slate-400">Short</span> <span className={ss.grade === 'A+' || ss.grade === 'A' ? 'text-red-400' : 'text-terminal-muted'}>{ss.grade || '--'}</span></span>
                  </>
                )
              })()}
            </div>
          )}
        </div>

        {/* Right: coach panel */}
        <div className="w-72 shrink-0 bg-terminal-card border border-terminal-border rounded p-3" style={{ maxHeight: '580px', overflowY: 'auto' }}>
          <CoachPanel data={data} />
        </div>
      </div>
    </div>
  )
}
