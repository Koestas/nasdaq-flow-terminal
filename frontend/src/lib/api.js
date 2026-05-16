const BASE = import.meta.env.VITE_API_URL || ''

export async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const fmt = {
  price: (v) => v == null ? '--' : `$${Number(v).toFixed(2)}`,
  pct: (v) => v == null ? '--' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`,
  premium: (v) => {
    if (v == null) return '--'
    const n = Number(v)
    if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`
    if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(1)}K`
    return `$${n.toFixed(0)}`
  },
  num: (v) => v == null ? '--' : Number(v).toLocaleString(),
  timeAgo: (iso) => {
    if (!iso) return '--'
    const diff = Date.now() - new Date(iso).getTime()
    const m = Math.floor(diff / 60000)
    if (m < 1) return 'just now'
    if (m < 60) return `${m}m ago`
    const h = Math.floor(m / 60)
    if (h < 24) return `${h}h ago`
    return `${Math.floor(h / 24)}d ago`
  },
}
