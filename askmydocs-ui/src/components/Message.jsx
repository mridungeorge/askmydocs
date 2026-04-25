import { useState } from 'react'

export default function Message({
  role, content, sources, routing,
  agentType, cacheHit, rewrittenQuery, blocked,
}) {
  const [showSources, setShowSources] = useState(false)

  const agentColors = {
    simple:     '#3a5a7a',
    complex:    '#5a3a7a',
    comparison: '#7a5a3a',
    followup:   '#3a7a5a',
    no_context: '#7a3a3a',
    web_search: '#3a7a7a',
    cached:     '#5a7a3a',
    guardrail:  '#7a3a3a',
  }
  const agentColor = agentColors[agentType] || '#aaa'
  const modelLabel = routing?.model?.includes('70b') ? '70B' : routing?.model === 'none' ? '—' : '8B'

  return (
    <div className={`message message-${role}`}>
      {/* Blocked message styling */}
      {blocked && (
        <div style={{
          fontSize: 10,
          fontFamily: 'var(--sans)',
          color: '#7a3a3a',
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          marginBottom: 6,
        }}>
          Guardrail active
        </div>
      )}

      <div className="message-text" style={{ whiteSpace: 'pre-wrap' }}>
        {content}
      </div>

      {role === 'assistant' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>

          {/* Agent type badge */}
          {agentType && agentType !== 'cached' && (
            <div style={{
              fontFamily: 'var(--serif)',
              fontSize: 10,
              fontStyle: 'italic',
              color: agentColor,
            }}>
              {agentType} agent
            </div>
          )}

          {/* Cache hit badge */}
          {cacheHit && (
            <div style={{
              fontFamily: 'var(--sans)',
              fontSize: 10,
              fontWeight: 300,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              color: '#3a7a3a',
              border: '1px solid #3a7a3a',
              padding: '2px 6px',
            }}>
              cache {cacheHit}
            </div>
          )}

          {/* Model + score */}
          {routing?.model && routing.model !== 'none' && (
            <div style={{
              fontFamily: 'var(--serif)',
              fontSize: 10,
              fontStyle: 'italic',
              color: '#aaa',
            }}>
              {modelLabel} · score {routing.score?.toFixed(2)}
            </div>
          )}

          {/* Rewritten query */}
          {rewrittenQuery && rewrittenQuery !== content?.slice(0, rewrittenQuery.length) && (
            <div style={{
              fontFamily: 'var(--serif)',
              fontSize: 10,
              fontStyle: 'italic',
              color: '#bbb',
            }}>
              rewritten: "{rewrittenQuery.slice(0, 45)}{rewrittenQuery.length > 45 ? '…' : ''}"
            </div>
          )}

          {/* Sources toggle */}
          {sources?.length > 0 && (
            <button
              className={`sources-toggle ${showSources ? 'open' : ''}`}
              onClick={() => setShowSources(s => !s)}
            >
              Sources ({sources.length}) <span className="arrow">▾</span>
            </button>
          )}
        </div>
      )}

      {showSources && sources?.length > 0 && (
        <div className="sources-panel">
          {sources.map((s, i) => (
            <div key={i} className="source-item">
              <div className="source-header">
                <span className="source-name">
                  [{i + 1}] {s.name}
                  {s.type === 'image' && ' 🖼'}
                  {s.type === 'table' && ' 📊'}
                  {s.type === 'web'   && ' 🌐'}
                </span>
                {s.score && <span className="source-score">{s.score}% match</span>}
              </div>
              <div className="source-snippet">{s.snippet}</div>
              {s.url && (
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.05em' }}
                >
                  {s.url.slice(0, 50)}…
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
