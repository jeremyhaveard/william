import { useState, useRef, useEffect } from 'react'
import './Chat.css'

const AGENT_COLORS = {
  norm:   '#58a6ff',
  karen:  '#f78166',
  dirk:   '#d2a8ff',
  rex:    '#3fb950',
  govcon: '#ffa657',
}

function agentColor(label = '') {
  const key = label.toLowerCase().split(' ')[0]
  return AGENT_COLORS[key] || '#8b949e'
}

function Bubble({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="bubble-row user">
        <div className="bubble user-bubble">{msg.content}</div>
      </div>
    )
  }

  return (
    <div className="bubble-row assistant">
      {msg.label && (
        <div className="agent-label" style={{ color: agentColor(msg.label) }}>
          {msg.label}
        </div>
      )}
      <div className={`bubble assistant-bubble${msg.error ? ' error' : ''}`}>
        {msg.pending && !msg.content
          ? <span className="dots"><span /><span /><span /></span>
          : <pre className="msg-pre">{msg.content}</pre>
        }
      </div>
    </div>
  )
}

export default function Chat({ messages, onSend, loading }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const submit = () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    onSend(text)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">Chat</div>
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty-state">Ask William anything</div>
        )}
        {messages.map(m => <Bubble key={m.id} msg={m} />)}
        <div ref={bottomRef} />
      </div>
      <div className="input-bar">
        <textarea
          ref={textareaRef}
          className="chat-input"
          rows={3}
          placeholder="Message William… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          disabled={loading}
        />
        <button
          className="send-btn"
          onClick={submit}
          disabled={loading || !input.trim()}
        >
          {loading ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
