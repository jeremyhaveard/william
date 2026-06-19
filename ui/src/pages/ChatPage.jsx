import { useState, useRef, useEffect, useCallback } from 'react'

const randomUUID = () => crypto.randomUUID?.() ?? ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c => (c ^ (Math.random() * 16 >> c / 4)).toString(16))
import { useNavigate } from 'react-router-dom'
import Chat from '../components/Chat'
import Console from '../components/Console'
import HistorySidebar from '../components/HistorySidebar'
import { useAuth } from '../auth/AuthContext'
import '../App.css'

const API = ''

export default function ChatPage() {
  const { user, logout, token, AUTH_ENABLED } = useAuth()
  const navigate = useNavigate()

  const [threadId, setThreadId] = useState(null)
  const [messages, setMessages] = useState([])
  const [logs, setLogs]         = useState([])
  const [loading, setLoading]   = useState(false)
  const abortRef = useRef(null)

  // Build auth headers — include JWT when Cognito is configured
  const authHeaders = useCallback(() => {
    const h = { 'Content-Type': 'application/json' }
    if (AUTH_ENABLED && token) h['Authorization'] = `Bearer ${token}`
    return h
  }, [AUTH_ENABLED, token])

  useEffect(() => {
    fetch(`${API}/thread`, { method: 'POST', headers: authHeaders() })
      .then(r => r.json())
      .then(d => setThreadId(d.thread_id))
      .catch(() => setThreadId(randomUUID()))
  }, [authHeaders])

  const addLog = useCallback((type, data) => {
    setLogs(prev => [...prev, { id: randomUUID(), type, data, ts: Date.now() }])
  }, [])

  // Like addLog but updates the most recent entry of the same type+agent instead of appending
  const upsertMessageLog = useCallback((data) => {
    setLogs(prev => {
      const idx = [...prev].reverse().findIndex(
        l => l.type === 'message' && l.data.agent === data.agent
      )
      if (idx !== -1) {
        const realIdx = prev.length - 1 - idx
        const updated = [...prev]
        updated[realIdx] = { ...updated[realIdx], data, ts: Date.now() }
        return updated
      }
      return [...prev, { id: randomUUID(), type: 'message', data, ts: Date.now() }]
    })
  }, [])

  const sendMessage = useCallback(async (text) => {
    if (!threadId || loading) return

    setMessages(prev => [...prev, { id: randomUUID(), role: 'user', content: text }])
    setLoading(true)
    // Add a separator + user event to mark a new request cycle in the console
    setLogs(prev => [
      ...prev,
      ...(prev.length > 0 ? [{ id: randomUUID(), type: 'separator', data: {}, ts: Date.now() }] : []),
      { id: randomUUID(), type: 'user', data: { message: text }, ts: Date.now() },
    ])

    const assistantId = randomUUID()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', pending: true }])

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch(`${API}/chat/${threadId}`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ message: text }),
        signal: controller.signal,
      })

      if (res.status === 401) {
        logout()
        navigate('/login')
        return
      }

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        let currentEvent = null
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))

              if (currentEvent === 'message') {
                // Update existing console entry for this agent rather than appending
                upsertMessageLog(data)
                setMessages(prev => prev.map(m =>
                  m.id === assistantId
                    ? { ...m, content: data.content, label: data.label, pending: false }
                    : m
                ))
              } else {
                addLog(currentEvent, data)
              }

              if (currentEvent === 'done') {
                setMessages(prev => prev.map(m =>
                  m.id === assistantId ? { ...m, pending: false } : m
                ))
              }
            } catch { /* ignore parse errors */ }
            currentEvent = null
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        addLog('error', { message: err.message })
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, content: 'Error: ' + err.message, pending: false, error: true }
            : m
        ))
      }
    } finally {
      setLoading(false)
      abortRef.current = null
    }
  }, [threadId, loading, addLog, authHeaders, logout, navigate])

  const newThread = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort()
    setMessages([])
    setLogs([])
    setLoading(false)
    try {
      const r = await fetch(`${API}/thread`, { method: 'POST', headers: authHeaders() })
      const d = await r.json()
      setThreadId(d.thread_id)
    } catch {
      setThreadId(randomUUID())
    }
  }, [authHeaders])

  // Resume a past session from the history sidebar
  const loadThread = useCallback((tid) => {
    if (abortRef.current) abortRef.current.abort()
    setMessages([])
    setLogs([])
    setLoading(false)
    setThreadId(tid)
  }, [])

  function handleLogout() {
    if (abortRef.current) abortRef.current.abort()
    logout()
    navigate('/')
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <span className="logo">William</span>
          <span className="thread-id">
            {threadId ? `session · ${threadId.slice(0, 8)}` : 'connecting…'}
          </span>
          {user && <span className="header-user">{user.email}</span>}
        </div>
        <div className="header-right">
          <button className="new-btn" onClick={newThread}>+ New Session</button>
          {AUTH_ENABLED && (
            <button className="new-btn" onClick={handleLogout}>Sign Out</button>
          )}
        </div>
      </header>
      <div className="panels">
        <HistorySidebar
          currentThreadId={threadId}
          onSelectThread={loadThread}
          authHeaders={authHeaders}
        />
        <Chat messages={messages} onSend={sendMessage} loading={loading} />
        <Console logs={logs} onClear={() => setLogs([])} />
      </div>
    </div>
  )
}
