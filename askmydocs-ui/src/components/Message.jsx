import { useState } from 'react'

export default function Message({ role, content, sources, routing }) {
  const [showSources, setShowSources] = useState(false)

  const modelLabel = routing?.model?.includes('70b') ? '70B' : '8B'
  const modelColor = routing?.is_complex ? '#7a5a3a' : '#3a5a7a'

  return (
    <div className={`message message-${role}`}>
      <div className="message-text">{content}</div>

      {role === 'assistant' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
          {routing && (
            <div style={{
              fontFamily: "'Noto Serif', serif",
              fontSize: 10,
              fontStyle: 'italic',
              color: modelColor,
              letterSpacing: '0.05em',
            }}>
              {modelLabel} · score {routing.score}
            </div>
          )}

          {sources?.length > 0 && (
            <button
              className={`sources-toggle ${showSources ? 'open' : ''}`}
              onClick={() => setShowSources(s => !s)}
            >
              Sources ({sources.length})
              <span className="arrow">▾</span>
            </button>
          )}
        </div>
      )}

      {showSources && sources?.length > 0 && (
        <div className="sources-panel">
          {sources.map((s, i) => (
            <div key={i} className="source-item">
              <div className="source-header">
                <span className="source-name">[{i + 1}] {s.name}</span>
                {s.score && <span className="source-score">{s.score}% match</span>}
              </div>
              <div className="source-snippet">{s.snippet}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
