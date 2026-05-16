import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch, fmt } from '../lib/api'
import ErrorBoundary from '../components/ErrorBoundary'
import { TableSkeleton } from '../components/LoadingSkeleton'
import { useState } from 'react'
import { Save, GitCompare } from 'lucide-react'
import { clsx } from 'clsx'

export default function Replay() {
  const qc = useQueryClient()
  const [sel1, setSel1] = useState(null)
  const [sel2, setSel2] = useState(null)

  const { data: snapData, isLoading } = useQuery({
    queryKey: ['snapshots'],
    queryFn: () => apiFetch('/api/replay/snapshots?limit=50'),
  })

  const { data: compareData, isLoading: comparing } = useQuery({
    queryKey: ['compare', sel1, sel2],
    queryFn: () => apiFetch(`/api/replay/compare?id1=${sel1}&id2=${sel2}`),
    enabled: !!(sel1 && sel2 && sel1 !== sel2),
  })

  const saveMut = useMutation({
    mutationFn: () => apiFetch('/api/replay/save', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['snapshots'] }),
  })

  const snapshots = snapData?.snapshots || []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-terminal-text">Replay</h1>
        <button
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending}
          className="flex items-center gap-1 px-3 py-1 rounded bg-terminal-blue/20 text-terminal-blue text-xs border border-terminal-blue/30 hover:bg-terminal-blue/30 transition-colors disabled:opacity-50"
        >
          <Save size={12} /> {saveMut.isPending ? 'Saving...' : 'Save Snapshot'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Snapshot list */}
        <ErrorBoundary>
          <div className="card">
            <div className="stat-label mb-3">Saved Snapshots ({snapshots.length})</div>
            {isLoading ? <TableSkeleton rows={6} /> : (
              <div className="space-y-1 max-h-80 overflow-y-auto">
                {snapshots.map(s => (
                  <div key={s.id} className={clsx(
                    'flex items-center justify-between px-3 py-2 rounded cursor-pointer text-xs hover:bg-terminal-border/30',
                    (sel1 === s.id || sel2 === s.id) && 'bg-terminal-blue/10 border border-terminal-blue/30'
                  )}>
                    <div>
                      <span className="text-terminal-text font-semibold">#{s.id}</span>
                      <span className="text-terminal-muted ml-2">
                        {new Date(s.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => setSel1(s.id === sel1 ? null : s.id)}
                        className={clsx('px-2 py-0.5 rounded text-xs', sel1 === s.id ? 'bg-terminal-green text-black' : 'bg-terminal-border text-terminal-muted')}
                      >A</button>
                      <button
                        onClick={() => setSel2(s.id === sel2 ? null : s.id)}
                        className={clsx('px-2 py-0.5 rounded text-xs', sel2 === s.id ? 'bg-terminal-yellow text-black' : 'bg-terminal-border text-terminal-muted')}
                      >B</button>
                    </div>
                  </div>
                ))}
                {snapshots.length === 0 && (
                  <div className="text-center text-terminal-muted py-6 text-xs">
                    No snapshots yet. Click "Save Snapshot" to capture current market state.
                  </div>
                )}
              </div>
            )}
          </div>
        </ErrorBoundary>

        {/* Comparison */}
        <ErrorBoundary>
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <GitCompare size={14} className="text-terminal-blue" />
              <div className="stat-label">Comparison</div>
            </div>
            {!(sel1 && sel2) ? (
              <div className="text-center py-8 text-terminal-muted text-xs">
                Select two snapshots (A and B) to compare them
              </div>
            ) : comparing ? (
              <TableSkeleton rows={5} />
            ) : compareData?.metrics ? (
              <div className="space-y-2">
                <div className="grid grid-cols-3 text-xs border-b border-terminal-border pb-1 mb-1">
                  <span className="text-terminal-muted">Metric</span>
                  <span className="text-terminal-green">Snapshot A (#{sel1})</span>
                  <span className="text-terminal-yellow">Snapshot B (#{sel2})</span>
                </div>
                {Object.entries(compareData.metrics).map(([key, vals]) => (
                  <div key={key} className="grid grid-cols-3 text-xs py-1 border-b border-terminal-border/20">
                    <span className="text-terminal-muted capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className="text-terminal-text">{String(vals.t1 ?? '--')}</span>
                    <span className="text-terminal-text">{String(vals.t2 ?? '--')}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </ErrorBoundary>
      </div>

      <div className="card bg-terminal-card2 text-xs text-terminal-muted space-y-1">
        <div className="text-terminal-text font-semibold text-sm">How to Use Replay</div>
        <p>Save snapshots throughout the session. After the session, compare snapshots to see how conditions evolved.</p>
        <p>Good questions to answer: Was WAVE positive before the big move? Was leadership aligned at the breakout? Did bias shift before or after price?</p>
        <p>This turns the app into a <strong className="text-terminal-text">training tool</strong>, not just a live dashboard.</p>
      </div>
    </div>
  )
}
