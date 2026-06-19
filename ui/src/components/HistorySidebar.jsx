import { useEffect, useState, useCallback } from 'react'
import './HistorySidebar.css'

function relativeTime(isoStr) {
  const d = new Date(isoStr)
  const now = Date.now()
  const diff = Math.floor((now - d.getTime()) / 1000)
  if (diff < 60)    return 'just now'
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function HistorySidebar({ currentThreadId, onSelectThread, authHeaders }) {
  const [threads, setThreads]   = useState([])
  const [loading, setLoading]   = useState(false)
  const [open, setOpen]         = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await fetch('/history', { headers: authHeaders() })
      if (r.ok) setThreads(await r.json())
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [authHeaders])

  useEffect(() => { load() }, [load])

  // Refresh when the current thread changes (new message sent)
  useEffect(() => {
    const id = setTimeout(load, 1500)
    return () => clearTimeout(id)
  }, [currentThreadId, load])

  return (
    <div className={`history-sidebar${open ? ' open' : ' collapsed'}`}>
      <div className="history-header" onClick={() => setOpen(o => !o)}>
        <span className="history-title">{open ? 'Sessions' : '⟨'}</span>
        {open && (
          <button className="history-refresh" onClick={e => { e.stopPropagation(); load() }} title="Refresh">
            ↻
          </button>
        )}
      </div>

      {open && (
        <div className="history-list">
          {loading && threads.length === 0 && (
            <div className="history-empty">Loading…</div>
          )}
          {!loading && threads.length === 0 && (
            <div className="history-empty">No sessions yet</div>
          )}
          {threads.map(t => (
            <div
              key={t.thread_id}
              className={`history-item${t.thread_id === currentThreadId ? ' active' : ''}`}
              onClick={() => onSelectThread(t.thread_id)}
              title={t.title}
            >
              <div className="history-item-title">{t.title}</div>
              <div className="history-item-meta">
                <span className="history-item-count">{t.message_count} msg{t.message_count !== 1 ? 's' : ''}</span>
                <span className="history-item-time">{relativeTime(t.last_active)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
