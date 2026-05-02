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
    web_search: '#0084ff',
    cached:     '#31a24c',
    guardrail:  '#c53030',
    stream:     '#7a5a3a',
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
          {agentType && (
            <div style={{
              fontFamily: 'var(--serif)',
              fontSize: 10,
              fontStyle: 'italic',
              color: agentColor,
              fontWeight: agentType === 'web_search' || agentType === 'cached' ? 600 : 400,
            }}>
              {agentType === 'web_search' ? '🌐 web' : agentType === 'cached' ? '⚡ cached' : agentType + ' agent'}
            </div>
          )}

          {/* Cache hit badge */}
          {cacheHit && agentType !== 'cached' && (
            <div style={{
              fontFamily: 'var(--sans)',
              fontSize: 10,
              fontWeight: 300,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              color: '#31a24c',
              border: '1px solid #31a24c',
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
              {(() => {
                const displayQuery = rewrittenQuery.split(' OR ')[0].trim().replace(/"/g, '').slice(0, 45)
                return `rewritten: "${displayQuery}${rewrittenQuery.length > 45 ? '…' : ''}"`
              })()}
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
