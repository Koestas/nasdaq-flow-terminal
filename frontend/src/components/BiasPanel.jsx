import { useState } from 'react'
import { clsx } from 'clsx'
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { fmt } from '../lib/api'

function ScoreGauge({ score }) {
  const pct = ((score + 100) / 200) * 100
  const color = score > 25 ? '#00ff88' : score < -25 ? '#ff4466' : '#ffd700'
  return (
    <div className="relative w-full h-3 bg-terminal-border rounded-full overflow-hidden">
      <div
        className="absolute top-0 left-0 h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
      <div className="absolute top-0 left-1/2 w-px h-full bg-terminal-muted/50" />
    </div>
  )
}

export default function BiasPanel({ bias, wave, expanded: defaultExpanded = true }) {
  const [showPlan, setShowPlan] = useState(false)

  if (!bias) return null

  const scoreColor = bias.score > 25 ? 'text-terminal-green'
    : bias.score < -25 ? 'text-terminal-red'
    : 'text-terminal-yellow'

  return (
    <div className="card space-y-4">
      {/* No Trade Warning */}
      {bias.no_trade_warning && (
        <div className="flex items-start gap-2 bg-terminal-yellow/10 border border-terminal-yellow/30 rounded-lg p-3">
          <AlertTriangle size={16} className="text-terminal-yellow shrink-0 mt-0.5" />
          <div>
            <div className="text-terminal-yellow font-semibold text-sm">No Trade Zone</div>
            <div className="text-terminal-muted text-xs">{bias.no_trade_reason}</div>
          </div>
        </div>
      )}

      <div className="flex items-start justify-between gap-4">
        {/* Score */}
        <div>
          <div className={`text-4xl font-bold ${scoreColor}`}>
            {bias.score > 0 ? '+' : ''}{bias.score}
          </div>
          <div className={`text-lg font-semibold ${scoreColor}`}>{bias.label}</div>
          <div className="text-terminal-muted text-xs mt-1">
            Confidence: <span className="text-terminal-text font-semibold">{bias.confidence}% ({bias.confidence_label})</span>
          </div>
          <div className="text-terminal-muted text-xs">
            Regime: <span className="text-terminal-blue font-semibold">{bias.regime}</span>
          </div>
        </div>

        {/* Checklist */}
        <div className="flex-1 space-y-1">
          {(bias.checklist || []).map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              {item.value
                ? <CheckCircle size={12} className="text-terminal-green shrink-0" />
                : <XCircle size={12} className="text-terminal-muted shrink-0" />}
              <span className={item.value ? 'text-terminal-text' : 'text-terminal-muted'}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Gauge */}
      <div>
        <ScoreGauge score={bias.score} />
        <div className="flex justify-between text-xs text-terminal-muted mt-1">
          <span>-100 Bearish</span>
          <span>Neutral</span>
          <span>Bullish +100</span>
        </div>
      </div>

      {/* Reasons */}
      {(bias.reasons_bullish?.length > 0 || bias.reasons_bearish?.length > 0) && (
        <div className="grid grid-cols-2 gap-3">
          {bias.reasons_bullish?.length > 0 && (
            <div>
              <div className="text-terminal-green text-xs font-semibold mb-1 uppercase tracking-wider">Bullish</div>
              {bias.reasons_bullish.map((r, i) => (
                <div key={i} className="text-xs text-terminal-muted flex gap-1">
                  <span className="text-terminal-green">+</span> {r}
                </div>
              ))}
            </div>
          )}
          {bias.reasons_bearish?.length > 0 && (
            <div>
              <div className="text-terminal-red text-xs font-semibold mb-1 uppercase tracking-wider">Bearish</div>
              {bias.reasons_bearish.map((r, i) => (
                <div key={i} className="text-xs text-terminal-muted flex gap-1">
                  <span className="text-terminal-red">−</span> {r}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Trade Plan toggle */}
      <button
        onClick={() => setShowPlan(s => !s)}
        className="flex items-center gap-1 text-xs text-terminal-blue hover:underline"
      >
        {showPlan ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {showPlan ? 'Hide Trade Plan' : 'Show Trade Plan'}
      </button>

      {showPlan && bias.trade_plan && (
        <div className="bg-terminal-card2 border border-terminal-border/50 rounded-lg p-3 space-y-2 text-xs">
          <div>
            <span className="text-terminal-blue font-semibold uppercase tracking-wider text-xs">Primary Plan</span>
            <div className="text-terminal-text mt-0.5">{bias.trade_plan.primary}</div>
          </div>
          <div>
            <span className="text-terminal-green font-semibold">Long Setup: </span>
            <span className="text-terminal-muted">{bias.trade_plan.long_setup}</span>
          </div>
          <div>
            <span className="text-terminal-red font-semibold">Short Setup: </span>
            <span className="text-terminal-muted">{bias.trade_plan.short_setup}</span>
          </div>
          <div>
            <span className="text-terminal-yellow font-semibold">Invalidation: </span>
            <span className="text-terminal-muted">{bias.trade_plan.invalidation}</span>
          </div>
          <div>
            <span className="text-terminal-muted font-semibold">Avoid: </span>
            <span className="text-terminal-muted">{bias.trade_plan.avoid}</span>
          </div>
          {bias.trade_plan.key_levels?.length > 0 && (
            <div>
              <span className="text-terminal-purple font-semibold">Key Levels: </span>
              <span className="text-terminal-muted">{bias.trade_plan.key_levels.join(' | ')}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
