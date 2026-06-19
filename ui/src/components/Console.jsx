import { useEffect, useRef, useState, useCallback } from 'react'
import './Console.css'

const EVENT_META = {
  user:        { icon: '▶', label: 'user input',    cls: 'ev-user' },
  thinking:    { icon: '…', label: 'thinking',      cls: 'ev-routing' },
  routing:     { icon: '⇢', label: 'supervisor',    cls: 'ev-routing' },
  agent:       { icon: '◆', label: 'agent active',  cls: 'ev-agent' },
  tool_call:   { icon: '⚙', label: 'tool call',     cls: 'ev-tool' },
  tool_result: { icon: '✓', label: 'tool result',   cls: 'ev-tool-result' },
  llm_start:   { icon: '▷', label: 'llm start',     cls: 'ev-llm-start' },
  llm_end:     { icon: '◁', label: 'llm end',       cls: 'ev-llm-end' },
  milestone:   { icon: '◉', label: 'milestone',     cls: 'ev-milestone' },
  timing:      { icon: '⏱', label: 'timing',        cls: 'ev-timing' },
  message:     { icon: '✓', label: 'response',      cls: 'ev-message' },
  done:        { icon: '■', label: 'done',           cls: 'ev-done' },
  error:       { icon: '✗', label: 'error',          cls: 'ev-error' },
  separator:   { icon: '',  label: '',               cls: 'ev-separator' },
}

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString('en-US', {
    hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function formatMs(ts) {
  return new Date(ts).toLocaleTimeString('en-US', {
    hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
    fractionalSecondDigits: 3,
  })
}

function MsTag({ ms }) {
  if (ms == null) return null
  return <span className="log-ms">{ms}ms</span>
}

function renderBody(type, data, details) {
  switch (type) {
    case 'user':
      return <span className="ev-text">"{data.message}"</span>

    case 'routing':
      return <span className="ev-text dim">{data.message}</span>

    case 'agent':
      return <span className="ev-text"><span className="ev-badge">{data.label}</span></span>

    case 'tool_call': {
      const args = data.args && Object.keys(data.args).length > 0
        ? Object.entries(data.args)
            .map(([k, v]) => `${k}=${JSON.stringify(v).slice(0, details ? 300 : 60)}`)
            .join(', ')
        : ''
      return (
        <span className="ev-text">
          <span className="ev-tool-name">{data.tool}</span>
          {args && <span className="ev-args">({args})</span>}
        </span>
      )
    }

    case 'tool_result': {
      const preview = data.preview
        ? (details ? data.preview : data.preview.slice(0, 100))
        : ''
      return (
        <span className="ev-text">
          <span className="ev-tool-name">{data.tool}</span>
          {data.error
            ? <span className="ev-text error"> ERROR</span>
            : <span className="ev-text dim"> OK</span>
          }
          {preview && <span className="ev-args">  {preview}{!details && data.preview?.length > 100 ? '…' : ''}</span>}
          <MsTag ms={data.ms} />
        </span>
      )
    }

    case 'llm_start':
      return (
        <span className="ev-text dim">
          <span className="ev-model">{data.model}</span>
          {data.prompt_tokens != null && <span className="ev-args">  ~{data.prompt_tokens} prompt tokens</span>}
        </span>
      )

    case 'llm_end': {
      const toks = data.tokens || {}
      const tokStr = Object.entries(toks)
        .map(([k, v]) => `${k}=${v}`)
        .join('  ')
      return (
        <span className="ev-text dim">
          <span className="ev-model">{data.model}</span>
          {tokStr && <span className="ev-args">  {tokStr}</span>}
          <MsTag ms={data.ms} />
        </span>
      )
    }

    case 'milestone':
      return (
        <span className="ev-text">
          {data.message}
          <MsTag ms={data.ms} />
        </span>
      )

    case 'timing':
      return (
        <span className="ev-text dim">
          total <span className="ev-timing-value">{data.total_ms}ms</span>
          {data.thread_id && <span className="ev-args">  thread:{data.thread_id.slice(0, 8)}</span>}
        </span>
      )

    case 'message': {
      const limit = details ? 9999 : 120
      return (
        <span className="ev-text dim">
          [{data.label}] {data.content?.slice(0, limit)}{!details && data.content?.length > 120 ? '…' : ''}
        </span>
      )
    }

    case 'done':
      return <span className="ev-text dim">stream complete</span>

    case 'error':
      return (
        <span className="ev-text error">
          {data.message}
          {details && data.traceback && (
            <span className="ev-traceback">{data.traceback.slice(0, 600)}</span>
          )}
        </span>
      )

    default:
      return <span className="ev-text dim">{JSON.stringify(data)}</span>
  }
}

function buildTooltipText(log) {
  const lines = [
    `type    : ${log.type}`,
    `time    : ${formatMs(log.ts)}`,
    `id      : ${log.id}`,
    ``,
    `── data ──────────────────────────`,
    JSON.stringify(log.data, null, 2),
  ]
  return lines.join('\n')
}

function LogEntry({ log, details }) {
  if (log.type === 'separator') {
    return <div className="log-separator" />
  }

  const meta = EVENT_META[log.type] || { icon: '·', label: log.type, cls: 'ev-default' }
  const [tooltip, setTooltip] = useState(null)
  const entryRef = useRef(null)

  const handleMouseEnter = useCallback(() => {
    const rect = entryRef.current?.getBoundingClientRect()
    if (!rect) return
    setTooltip({ x: rect.left, y: rect.top })
  }, [])

  const handleMouseLeave = useCallback(() => setTooltip(null), [])

  return (
    <>
      <div
        ref={entryRef}
        className={`log-entry ${meta.cls}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <span className="log-ts">{formatTime(log.ts)}</span>
        <span className="log-icon">{meta.icon}</span>
        <span className="log-label">{meta.label}</span>
        <span className="log-body">{renderBody(log.type, log.data, details)}</span>
      </div>

      {details && (
        <div className="log-detail-block">
          <pre className="log-detail-pre">{JSON.stringify(log.data, null, 2)}</pre>
        </div>
      )}

      {tooltip && (
        <div
          className="log-tooltip"
          style={{ top: tooltip.y, left: tooltip.x }}
        >
          <pre className="log-tooltip-pre">{buildTooltipText(log)}</pre>
        </div>
      )}
    </>
  )
}

export default function Console({ logs, onClear }) {
  const bottomRef = useRef(null)
  const [details, setDetails] = useState(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className="console-panel">
      <div className="console-header">
        <span>Console</span>
        <div className="console-actions">
          <span className="log-count">{logs.length} events</span>

          <button
            className={`details-btn${details ? ' active' : ''}`}
            onClick={() => setDetails(d => !d)}
            title="Toggle verbose detail view"
          >
            {details ? 'Details ON' : 'Details'}
          </button>

          <button className="clear-btn" onClick={onClear} disabled={logs.length === 0}>
            Clear
          </button>
        </div>
      </div>

      <div className="log-scroll">
        {logs.length === 0 && (
          <div className="console-empty">Agent activity will appear here</div>
        )}
        {logs.map(log => (
          <LogEntry key={log.id} log={log} details={details} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
