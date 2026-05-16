import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { TableSkeleton } from '../components/LoadingSkeleton'
import { useState } from 'react'
import { clsx } from 'clsx'
import { PlusCircle } from 'lucide-react'

const SETUPS = ['VWAP Reclaim Long', 'VWAP Rejection Short', 'OR Breakout', 'OR Breakdown', 'Trend Pull', 'Reversal', 'Other']
const MISTAKES = ['Chased entry', 'Ignored invalidation', 'No confirmation', 'Traded chop', 'Oversized', 'Early exit', 'None']

function TradeForm({ onSubmit, loading }) {
  const [form, setForm] = useState({ symbol: 'MNQ', direction: 'long', entry: '', exit: '', result: '', r_multiple: '', setup_type: '', bias_at_entry: '', confidence: '', notes: '', mistake_tag: '', lesson: '' })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({
      ...form,
      entry: form.entry ? parseFloat(form.entry) : null,
      exit: form.exit ? parseFloat(form.exit) : null,
      result: form.result ? parseFloat(form.result) : null,
      r_multiple: form.r_multiple ? parseFloat(form.r_multiple) : null,
      confidence: form.confidence ? parseInt(form.confidence) : null,
    })
    setForm(f => ({ ...f, entry: '', exit: '', result: '', r_multiple: '', notes: '', lesson: '' }))
  }

  return (
    <form onSubmit={handleSubmit} className="card space-y-3">
      <div className="text-sm font-semibold text-terminal-text">Log Trade</div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Symbol', key: 'symbol', placeholder: 'MNQ' },
          { label: 'Entry', key: 'entry', placeholder: '21000' },
          { label: 'Exit', key: 'exit', placeholder: '21050' },
          { label: 'Result ($)', key: 'result', placeholder: '+500' },
          { label: 'R Multiple', key: 'r_multiple', placeholder: '2.5' },
          { label: 'Confidence %', key: 'confidence', placeholder: '70' },
        ].map(({ label, key, placeholder }) => (
          <div key={key}>
            <label className="text-xs text-terminal-muted">{label}</label>
            <input
              value={form[key]}
              onChange={e => set(key, e.target.value)}
              placeholder={placeholder}
              className="w-full mt-1 bg-terminal-card2 border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text focus:outline-none focus:border-terminal-blue"
            />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label className="text-xs text-terminal-muted">Direction</label>
          <select value={form.direction} onChange={e => set('direction', e.target.value)} className="w-full mt-1 bg-terminal-card2 border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text">
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-terminal-muted">Setup Type</label>
          <select value={form.setup_type} onChange={e => set('setup_type', e.target.value)} className="w-full mt-1 bg-terminal-card2 border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text">
            <option value="">Select...</option>
            {SETUPS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-terminal-muted">Bias at Entry</label>
          <select value={form.bias_at_entry} onChange={e => set('bias_at_entry', e.target.value)} className="w-full mt-1 bg-terminal-card2 border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text">
            <option value="">Select...</option>
            {['Strongly Bullish', 'Bullish Lean', 'Neutral', 'Bearish Lean', 'Strongly Bearish', 'Chop'].map(b => <option key={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-terminal-muted">Mistake Tag</label>
          <select value={form.mistake_tag} onChange={e => set('mistake_tag', e.target.value)} className="w-full mt-1 bg-terminal-card2 border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text">
            <option value="">None</option>
            {MISTAKES.map(m => <option key={m}>{m}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-terminal-muted">Notes</label>
          <textarea value={form.notes} onChange={e => set('notes', e.target.value)} placeholder="What happened?" rows={2} className="w-full mt-1 bg-terminal-card2 border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text resize-none focus:outline-none focus:border-terminal-blue" />
        </div>
        <div>
          <label className="text-xs text-terminal-muted">Lesson Learned</label>
          <textarea value={form.lesson} onChange={e => set('lesson', e.target.value)} placeholder="What to do differently?" rows={2} className="w-full mt-1 bg-terminal-card2 border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text resize-none focus:outline-none focus:border-terminal-blue" />
        </div>
      </div>

      <button type="submit" disabled={loading} className="flex items-center gap-1 px-4 py-2 rounded bg-terminal-blue text-white text-xs font-semibold hover:bg-terminal-blue/80 transition-colors disabled:opacity-50">
        <PlusCircle size={12} /> Log Trade
      </button>
    </form>
  )
}

export default function Journal() {
  const qc = useQueryClient()

  const { data: tradesData, isLoading } = useQuery({
    queryKey: ['trades'],
    queryFn: () => apiFetch('/api/journal/trades'),
  })

  const { data: statsData } = useQuery({
    queryKey: ['journal-stats'],
    queryFn: () => apiFetch('/api/journal/stats'),
  })

  const addTrade = useMutation({
    mutationFn: (trade) => apiFetch('/api/journal/trades', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(trade) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trades'] })
      qc.invalidateQueries({ queryKey: ['journal-stats'] })
    },
  })

  const trades = tradesData?.trades || []
  const stats = statsData || {}

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-terminal-text">Trade Journal</h1>

      {/* Stats */}
      {stats.total > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: 'Total Trades', value: stats.total, color: 'text-terminal-text' },
            { label: 'Win Rate', value: `${stats.win_rate}%`, color: stats.win_rate >= 50 ? 'text-terminal-green' : 'text-terminal-red' },
            { label: 'Avg R', value: stats.avg_r != null ? stats.avg_r.toFixed(2) : '--', color: (stats.avg_r || 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red' },
            { label: 'Total P/L', value: fmt.price(stats.total_result), color: (stats.total_result || 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red' },
          ].map(({ label, value, color }) => (
            <div key={label} className="card">
              <div className="stat-label">{label}</div>
              <div className={`stat-value mt-1 ${color}`}>{value}</div>
            </div>
          ))}
        </div>
      )}

      <TradeForm onSubmit={(t) => addTrade.mutate(t)} loading={addTrade.isPending} />

      <ErrorBoundary>
        <div className="card overflow-x-auto">
          <div className="stat-label mb-3">Trade History</div>
          {isLoading ? <TableSkeleton rows={6} /> : (
            <table className="w-full text-xs min-w-[700px]">
              <thead>
                <tr>
                  {['Date', 'Symbol', 'Dir', 'Entry', 'Exit', 'Result', 'R', 'Setup', 'Bias', 'Mistake'].map(h => (
                    <th key={h} className="table-header">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i} className="hover:bg-terminal-border/20">
                    <td className="table-cell text-terminal-muted">{new Date(t.timestamp).toLocaleDateString()}</td>
                    <td className="table-cell font-semibold">{t.symbol}</td>
                    <td className={`table-cell font-bold ${t.direction === 'long' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {t.direction?.toUpperCase()}
                    </td>
                    <td className="table-cell">{t.entry ?? '--'}</td>
                    <td className="table-cell">{t.exit ?? '--'}</td>
                    <td className={`table-cell font-semibold ${(t.result || 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {t.result != null ? fmt.price(t.result) : '--'}
                    </td>
                    <td className={`table-cell ${(t.r_multiple || 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {t.r_multiple != null ? `${t.r_multiple}R` : '--'}
                    </td>
                    <td className="table-cell text-terminal-muted">{t.setup_type || '--'}</td>
                    <td className="table-cell text-terminal-muted text-xs">{t.bias_at_entry || '--'}</td>
                    <td className="table-cell">{t.mistake_tag ? <span className="badge-yellow">{t.mistake_tag}</span> : <span className="text-terminal-muted">—</span>}</td>
                  </tr>
                ))}
                {trades.length === 0 && (
                  <tr><td colSpan={10} className="table-cell text-center text-terminal-muted py-8">No trades logged yet</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </ErrorBoundary>
    </div>
  )
}
