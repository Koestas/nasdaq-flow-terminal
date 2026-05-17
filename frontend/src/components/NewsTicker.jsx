import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'

const DOT = {
  bullish: 'text-green-400',
  bearish: 'text-red-400',
  neutral: 'text-slate-500',
  alert:   'text-blue-400',
  warn:    'text-yellow-400',
}

const TEXT = {
  bullish: 'text-green-300',
  bearish: 'text-red-300',
  neutral: 'text-slate-300',
  alert:   'text-blue-300',
  warn:    'text-yellow-300',
}

function buildAlerts(overview, futures) {
  const items = []

  if (overview?.price?.price != null) {
    const up = (overview.price.change_pct || 0) >= 0
    items.push({
      type: up ? 'bullish' : 'bearish',
      text: `QQQ ${fmt.price(overview.price.price)} ${fmt.pct(overview.price.change_pct)}`,
    })
  }

  if (overview?.bias?.label) {
    const score = overview.bias.score
    items.push({
      type: score > 25 ? 'bullish' : score < -25 ? 'bearish' : 'alert',
      text: `Bias: ${overview.bias.label} (${score > 0 ? '+' : ''}${score})`,
    })
  }

  if (overview?.vwap_status) {
    items.push({
      type: overview.vwap_status === 'above' ? 'bullish' : 'bearish',
      text: `QQQ ${overview.vwap_status === 'above' ? 'ABOVE' : 'BELOW'} VWAP`,
    })
  }

  if (overview?.bias?.regime) {
    items.push({ type: 'alert', text: `Regime: ${overview.bias.regime}` })
  }

  if (futures?.length) {
    futures.forEach((f) => {
      if (f.price == null) return
      items.push({
        type: f.bullish ? 'bullish' : 'bearish',
        text: `${f.instrument} ${fmt.num(Math.round(f.price))} ${fmt.pct(f.change_pct)}`,
      })
    })
  }

  return items
}

export default function NewsTicker() {
  const [paused, setPaused] = useState(false)

  const { data: overview } = useQuery({
    queryKey: ['overview'],
    queryFn: () => apiFetch('/api/market/overview'),
    refetchInterval: 30_000,
  })

  const { data: futures } = useQuery({
    queryKey: ['futures-prices'],
    queryFn: () => apiFetch('/api/market/futures'),
    refetchInterval: 30_000,
  })

  const { data: newsData } = useQuery({
    queryKey: ['ticker-news'],
    queryFn: () => apiFetch('/api/market/news'),
    refetchInterval: 60_000,
    staleTime: 60_000,
  })

  const alerts = buildAlerts(overview, futures)
  const news = (newsData?.news || []).slice(0, 20).map((n) => ({
    type: n.sentiment || 'neutral',
    text: n.title,
    source: n.publisher,
  }))

  const items = [...alerts, ...news]

  // Always reserve the 28px space even while loading
  if (items.length === 0) {
    return <div className="fixed left-0 right-0 z-40 h-7 bg-[#080a0f] border-b border-terminal-border" style={{ top: 48 }} />
  }

  const duration = Math.max(120, items.length * 8)

  const renderItems = () =>
    items.map((item, i) => (
      <span key={i} className="inline-flex items-center shrink-0">
        <span className={`mr-1.5 text-[8px] ${DOT[item.type] || DOT.neutral}`}>●</span>
        <span className={`text-[11px] leading-none ${TEXT[item.type] || TEXT.neutral}`}>
          {item.text}
          {item.source && (
            <span className="text-slate-600 ml-1.5 text-[10px]">— {item.source}</span>
          )}
        </span>
        <span className="mx-5 text-slate-700 text-[10px]">◆</span>
      </span>
    ))

  return (
    <div
      className="fixed left-0 right-0 z-40 h-7 bg-[#080a0f] border-b border-terminal-border flex items-center overflow-hidden"
      style={{ top: 48 }}
    >
      {/* LIVE label */}
      <div className="shrink-0 px-2.5 h-full flex items-center border-r border-terminal-border bg-terminal-card">
        <span className="text-[10px] font-bold text-terminal-blue tracking-widest">LIVE</span>
      </div>

      {/* Scrolling strip */}
      <div
        className="flex-1 overflow-hidden"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        <div
          className="inline-flex whitespace-nowrap items-center"
          style={{
            animation: `ticker-scroll ${duration}s linear infinite`,
            animationPlayState: paused ? 'paused' : 'running',
          }}
        >
          {renderItems()}
          {renderItems()}
        </div>
      </div>

      {paused && (
        <div className="shrink-0 px-2 h-full flex items-center border-l border-terminal-border bg-terminal-card">
          <span className="text-[10px] text-slate-500">PAUSED</span>
        </div>
      )}
    </div>
  )
}
