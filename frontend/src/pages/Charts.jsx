import { useEffect, useRef, useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'
import { apiFetch, fmt } from '../lib/api'

const SYMBOLS = [
  { symbol: 'NQ=F', label: 'MNQ (NQ=F)' },
  { symbol: 'ES=F', label: 'MES (ES=F)' },
  { symbol: 'GC=F', label: 'MGC (GC=F)' },
]

const INTERVAL_PERIODS = {
  '1m':  { label: '1m',  periods: ['1d', '5d'] },
  '5m':  { label: '5m',  periods: ['1d', '5d', '1mo'] },
  '15m': { label: '15m', periods: ['5d', '1mo', '3mo'] },
  '1h':  { label: '1h',  periods: ['1mo', '3mo', '6mo'] },
  '1D':  { label: '1D',  periods: ['3mo', '6mo', '1y', '2y'] },
}

const PERIOD_LABELS = {
  '1d': '1D', '5d': '5D', '1mo': '1M', '3mo': '3M',
  '6mo': '6M', '1y': '1Y', '2y': '2Y',
}

function toUnixSeconds(isoTime) {
  return Math.floor(new Date(isoTime).getTime() / 1000)
}

export default function Charts() {
  const [symbol, setSymbol] = useState('NQ=F')
  const [interval, setInterval] = useState('5m')
  const [period, setPeriod] = useState('1d')
  const [hovered, setHovered] = useState(null)

  const chartContainerRef = useRef(null)
  const chartRef = useRef(null)
  const candleSeriesRef = useRef(null)
  const volumeSeriesRef = useRef(null)
  const vwapSeriesRef = useRef(null)
  const priceLinesRef = useRef([])

  // When interval changes, reset period to first valid option
  const handleIntervalChange = useCallback((newInterval) => {
    setInterval(newInterval)
    const validPeriods = INTERVAL_PERIODS[newInterval]?.periods || []
    if (validPeriods.length > 0) setPeriod(validPeriods[0])
  }, [])

  const validPeriods = INTERVAL_PERIODS[interval]?.periods || []
  const isIntraday = ['1m', '5m', '15m', '30m', '1h'].includes(interval)

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['chart', symbol, interval, period],
    queryFn: () => apiFetch(`/api/market/chart?symbol=${symbol}&interval=${interval}&period=${period}`),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  // Create chart once on mount
  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 500,
      layout: {
        background: { type: 'solid', color: '#0D0F14' },
        textColor: '#94A3B8',
      },
      grid: {
        vertLines: { color: '#1E2129' },
        horzLines: { color: '#1E2129' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: '#1E2129',
      },
      timeScale: {
        borderColor: '#1E2129',
        timeVisible: true,
        secondsVisible: false,
      },
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10B981',
      downColor: '#EF4444',
      borderUpColor: '#10B981',
      borderDownColor: '#EF4444',
      wickUpColor: '#10B981',
      wickDownColor: '#EF4444',
    })

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    const vwapSeries = chart.addLineSeries({
      color: '#F59E0B',
      lineWidth: 2,
      title: 'VWAP',
      priceLineVisible: false,
      lastValueVisible: true,
    })

    chartRef.current = chart
    candleSeriesRef.current = candleSeries
    volumeSeriesRef.current = volumeSeries
    vwapSeriesRef.current = vwapSeries

    // Subscribe to crosshair move for OHLCV hover info
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) {
        setHovered(null)
        return
      }
      const candle = param.seriesData.get(candleSeries)
      if (candle) {
        const volBar = param.seriesData.get(volumeSeries)
        setHovered({
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
          volume: volBar?.value ?? null,
          time: param.time,
        })
      }
    })

    // ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width })
      }
    })
    resizeObserver.observe(chartContainerRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
      candleSeriesRef.current = null
      volumeSeriesRef.current = null
      vwapSeriesRef.current = null
    }
  }, [])

  // Update data when query result changes
  useEffect(() => {
    if (!data || !candleSeriesRef.current || !volumeSeriesRef.current || !vwapSeriesRef.current) return

    const bars = (data.bars || [])
      .filter((b) => b.open != null && b.high != null && b.low != null && b.close != null)
      .map((b) => ({
        time: toUnixSeconds(b.time),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }))
      .sort((a, b) => a.time - b.time)

    const volumeBars = (data.bars || [])
      .filter((b) => b.open != null && b.close != null)
      .map((b) => ({
        time: toUnixSeconds(b.time),
        value: b.volume || 0,
        color: b.close >= b.open ? '#10B981cc' : '#EF4444cc',
      }))
      .sort((a, b) => a.time - b.time)

    try {
      candleSeriesRef.current.setData(bars)
      volumeSeriesRef.current.setData(volumeBars)
    } catch (e) {
      console.error('Error setting candle/volume data:', e)
    }

    // VWAP
    const vwapBars = (data.vwap_data || [])
      .map((v) => ({ time: toUnixSeconds(v.time), value: v.value }))
      .sort((a, b) => a.time - b.time)

    try {
      vwapSeriesRef.current.setData(vwapBars)
    } catch (e) {
      console.error('Error setting VWAP data:', e)
    }

    // Remove old price lines
    priceLinesRef.current.forEach((pl) => {
      try { candleSeriesRef.current.removePriceLine(pl) } catch (_) {}
    })
    priceLinesRef.current = []

    // Session level lines
    const levels = data.session_levels || {}
    const levelDefs = [
      { key: 'asia_high',      label: 'Asia H',    color: '#3B82F6', style: LineStyle.Dashed },
      { key: 'asia_low',       label: 'Asia L',    color: '#3B82F6', style: LineStyle.Dashed },
      { key: 'london_high',    label: 'London H',  color: '#F97316', style: LineStyle.Dashed },
      { key: 'london_low',     label: 'London L',  color: '#F97316', style: LineStyle.Dashed },
      { key: 'prev_day_high',  label: 'PDH',       color: '#6B7280', style: LineStyle.Dotted },
      { key: 'prev_day_low',   label: 'PDL',       color: '#6B7280', style: LineStyle.Dotted },
      { key: 'today_high',     label: "Today H",   color: '#E2E8F0', style: LineStyle.Solid },
      { key: 'today_low',      label: "Today L",   color: '#E2E8F0', style: LineStyle.Solid },
    ]

    levelDefs.forEach(({ key, label, color, style }) => {
      const price = levels[key]
      if (price == null) return
      try {
        const pl = candleSeriesRef.current.createPriceLine({
          price,
          color,
          lineWidth: 1,
          lineStyle: style,
          axisLabelVisible: true,
          title: label,
        })
        priceLinesRef.current.push(pl)
      } catch (e) {
        console.error('Error creating price line:', e)
      }
    })

    // Fit chart to show all data
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent()
    }
  }, [data])

  const isUp = hovered ? hovered.close >= hovered.open : true

  return (
    <div className="flex flex-col gap-3">
      {/* Header controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="text-terminal-blue font-bold text-sm">CHARTS</div>

        {/* Symbol selector */}
        <div className="flex gap-1">
          {SYMBOLS.map((s) => (
            <button
              key={s.symbol}
              onClick={() => setSymbol(s.symbol)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                symbol === s.symbol
                  ? 'bg-terminal-blue text-white'
                  : 'bg-terminal-card text-terminal-muted hover:text-terminal-text border border-terminal-border'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="w-px h-5 bg-terminal-border" />

        {/* Interval buttons */}
        <div className="flex gap-1">
          {Object.entries(INTERVAL_PERIODS).map(([iv, { label }]) => (
            <button
              key={iv}
              onClick={() => handleIntervalChange(iv)}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                interval === iv
                  ? 'bg-terminal-blue text-white'
                  : 'bg-terminal-card text-terminal-muted hover:text-terminal-text border border-terminal-border'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="w-px h-5 bg-terminal-border" />

        {/* Period buttons */}
        <div className="flex gap-1">
          {validPeriods.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                period === p
                  ? 'bg-terminal-yellow/20 text-terminal-yellow border border-terminal-yellow/40'
                  : 'bg-terminal-card text-terminal-muted hover:text-terminal-text border border-terminal-border'
              }`}
            >
              {PERIOD_LABELS[p] || p}
            </button>
          ))}
        </div>

        {/* Bar count + loading */}
        <div className="ml-auto flex items-center gap-2 text-xs text-terminal-muted">
          {isFetching && <span className="animate-pulse text-terminal-yellow">updating...</span>}
          {data?.bar_count != null && (
            <span>{data.bar_count} bars</span>
          )}
        </div>
      </div>

      {/* OHLCV hover strip */}
      <div className="flex items-center gap-4 px-3 py-1.5 bg-terminal-card border border-terminal-border rounded text-xs font-mono h-8">
        {hovered ? (
          <>
            <span className="text-terminal-muted">O</span>
            <span className={isUp ? 'text-terminal-green' : 'text-terminal-red'}>{fmt.num(hovered.open)}</span>
            <span className="text-terminal-muted">H</span>
            <span className="text-terminal-green">{fmt.num(hovered.high)}</span>
            <span className="text-terminal-muted">L</span>
            <span className="text-terminal-red">{fmt.num(hovered.low)}</span>
            <span className="text-terminal-muted">C</span>
            <span className={isUp ? 'text-terminal-green font-bold' : 'text-terminal-red font-bold'}>{fmt.num(hovered.close)}</span>
            {hovered.volume != null && (
              <>
                <span className="text-terminal-muted">V</span>
                <span className="text-terminal-text">{fmt.num(Math.round(hovered.volume))}</span>
              </>
            )}
          </>
        ) : (
          <span className="text-terminal-muted">Hover over a candle to see OHLCV data</span>
        )}
      </div>

      {/* Chart container */}
      <div className="relative bg-terminal-card border border-terminal-border rounded overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-terminal-bg/80 z-10">
            <div className="flex flex-col items-center gap-2">
              <div className="w-8 h-8 border-2 border-terminal-blue border-t-transparent rounded-full animate-spin" />
              <span className="text-terminal-muted text-xs">Loading chart data...</span>
            </div>
          </div>
        )}
        <div ref={chartContainerRef} style={{ width: '100%', height: '500px' }} />
      </div>

      {/* Session levels info bar */}
      {data?.session_levels && Object.keys(data.session_levels).length > 0 && (
        <div className="flex items-center gap-4 px-3 py-2 bg-terminal-card border border-terminal-border rounded text-xs flex-wrap">
          <span className="text-terminal-muted font-medium shrink-0">Session Levels:</span>
          {data.session_levels.asia_high && (
            <span>
              <span className="text-blue-400">Asia</span>{' '}
              <span className="text-terminal-text">{fmt.num(data.session_levels.asia_high)} / {fmt.num(data.session_levels.asia_low)}</span>
            </span>
          )}
          {data.session_levels.london_high && (
            <span>
              <span className="text-orange-400">London</span>{' '}
              <span className="text-terminal-text">{fmt.num(data.session_levels.london_high)} / {fmt.num(data.session_levels.london_low)}</span>
            </span>
          )}
          {data.session_levels.prev_day_high && (
            <span>
              <span className="text-terminal-muted">Prev Day</span>{' '}
              <span className="text-terminal-text">{fmt.num(data.session_levels.prev_day_high)} / {fmt.num(data.session_levels.prev_day_low)}</span>
            </span>
          )}
          {data.session_levels.today_high && (
            <span>
              <span className="text-terminal-text font-medium">Today</span>{' '}
              <span className="text-terminal-green">{fmt.num(data.session_levels.today_high)}</span>
              <span className="text-terminal-muted"> / </span>
              <span className="text-terminal-red">{fmt.num(data.session_levels.today_low)}</span>
            </span>
          )}
          {isIntraday && data.vwap_data?.length > 0 && (
            <span>
              <span className="text-yellow-400">VWAP</span>{' '}
              <span className="text-terminal-text">{fmt.num(data.vwap_data[data.vwap_data.length - 1]?.value)}</span>
            </span>
          )}
        </div>
      )}
    </div>
  )
}
