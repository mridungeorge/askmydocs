import { useEffect, useRef } from 'react'

const AGENT_COLORS = {
  topic_planner: '#6366f1',
  ingestion:     '#0ea5e9',
  currency:      '#f59e0b',
  memory:        '#8b5cf6',
  rag:           '#10b981',
  error_handler: '#f97316',
  critic_1:      '#ec4899',
  writer:        '#3b82f6',
  critic_2:      '#ef4444',
}

const AGENT_LABELS = {
  topic_planner: 'Planner',
  ingestion:     'Ingestion',
  currency:      'Currency',
  memory:        'Memory',
  rag:           'RAG',
  error_handler: 'Error Handler',
  critic_1:      'Critic 1',
  writer:        'Writer',
  critic_2:      'Critic 2',
}

const STATUS_ICONS = {
  start: '◉',
  done:  '✓',
  error: '✕',
  warn:  '⚠',
  info:  '·',
}

export default function LiveLog({ events = [] }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  return (
    <div style={{
      background:   '#0f0f0f',
      borderRadius: 10,
      padding:      '12px 0',
      fontFamily:   "'JetBrains Mono', 'Fira Code', monospace",
      fontSize:     12,
      lineHeight:   1.6,
      overflowY:    'auto',
      maxHeight:    260,
      color:        '#e2e8f0',
    }}>
      {events.length === 0 && (
        <div style={{ padding: '8px 16px', color: '#4b5563', fontStyle: 'italic' }}>
          Waiting for pipeline events…
        </div>
      )}
      {events.map((ev, i) => {
        const color = AGENT_COLORS[ev.agent] || '#9ca3af'
        const label = AGENT_LABELS[ev.agent] || ev.agent
        const icon  = STATUS_ICONS[ev.status] || '·'
        return (
          <div key={i} style={{ display: 'flex', gap: 8, padding: '3px 16px', alignItems: 'flex-start' }}>
            <span style={{ color: '#4b5563', whiteSpace: 'nowrap', flexShrink: 0 }}>{ev.ts}</span>
            <span style={{ color, fontWeight: 600, whiteSpace: 'nowrap', flexShrink: 0, minWidth: 80 }}>
              {icon} {label}
            </span>
            <span style={{ color: '#cbd5e1', wordBreak: 'break-word' }}>{ev.msg}</span>
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
