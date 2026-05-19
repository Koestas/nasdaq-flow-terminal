import { useEffect, useRef, useState } from 'react'
import { Bell, BellOff, X, AlertTriangle } from 'lucide-react'

function playBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const freqs = [880, 1100, 880]
    let t = ctx.currentTime
    freqs.forEach(f => {
      const osc = ctx.createOscillator()
      const g = ctx.createGain()
      osc.connect(g); g.connect(ctx.destination)
      osc.type = 'sine'; osc.frequency.value = f
      g.gain.setValueAtTime(0.2, t)
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.22)
      osc.start(t); osc.stop(t + 0.22)
      t += 0.22
    })
  } catch { /* audio unavailable */ }
}

function inKillzone() {
  const et = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }))
  const day = et.getDay()
  if (day === 0 || day === 6) return false
  const mins = et.getHours() * 60 + et.getMinutes()
  return mins >= 9 * 60 + 30 && mins <= 11 * 60 + 30
}

export default function AlertSystem() {
  const [enabled, setEnabled]   = useState(true)
  const [alerts, setAlerts]     = useState([])
  const lastKeyRef              = useRef('')
  const timerRef                = useRef(null)

  const check = async () => {
    if (!enabled || !inKillzone()) return
    try {
      const res = await fetch('/api/ict/alert-check')
      if (!res.ok) return
      const data = await res.json()
      if (!data.alert) return

      const key = `${data.direction}_${data.grade}_${data.sweep_summary}`
      if (key === lastKeyRef.current) return
      lastKeyRef.current = key

      const msg = `${data.direction?.toUpperCase()} ${data.grade} — ${data.sweep_summary || 'Sweep + iFVG'}`
      const time = new Date().toLocaleTimeString('en-US', {
        timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit',
      })

      setAlerts(prev => [{ id: Date.now(), direction: data.direction, grade: data.grade, msg, time }, ...prev.slice(0, 3)])
      playBeep()

      if (Notification.permission === 'granted') {
        new Notification('NQ Flow — ICT Setup Alert', { body: msg })
      }
    } catch { /* silent */ }
  }

  useEffect(() => {
    if (Notification.permission === 'default') Notification.requestPermission()

    const schedule = () => {
      check()
      timerRef.current = setTimeout(schedule, inKillzone() ? 30_000 : 120_000)
    }
    schedule()
    return () => clearTimeout(timerRef.current)
  }, [enabled]) // eslint-disable-line

  const dismiss = (id) => setAlerts(prev => prev.filter(a => a.id !== id))

  return (
    <>
      {/* Bell toggle — fixed near topbar right edge */}
      <button
        onClick={() => setEnabled(e => !e)}
        title={enabled ? 'Alerts ON — click to disable' : 'Alerts OFF — click to enable'}
        className={`fixed top-[14px] right-[90px] z-[200] transition-colors
          ${enabled ? 'text-terminal-yellow hover:text-yellow-300' : 'text-terminal-muted hover:text-terminal-text'}`}
      >
        {enabled ? <Bell size={13} /> : <BellOff size={13} />}
      </button>

      {/* Toast stack — bottom right */}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-72">
        {alerts.map(a => (
          <div key={a.id}
            className={`flex items-start gap-2 px-3 py-2 rounded-lg border text-xs shadow-lg
              ${a.direction === 'bullish'
                ? 'bg-green-950/95 border-terminal-green/50 text-terminal-green'
                : a.direction === 'bearish'
                  ? 'bg-red-950/95 border-terminal-red/50 text-terminal-red'
                  : 'bg-terminal-card border-terminal-border text-terminal-text'}`}>
            <AlertTriangle size={13} className="shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-bold">{a.msg}</div>
              <div className="text-[10px] opacity-70 mt-0.5">{a.time} ET · NY Killzone</div>
            </div>
            <button onClick={() => dismiss(a.id)} className="opacity-60 hover:opacity-100 shrink-0">
              <X size={11} />
            </button>
          </div>
        ))}
      </div>
    </>
  )
}
