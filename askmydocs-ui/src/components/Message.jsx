import { useState } from 'react'

export default function Message({ role, content, sources }) {
  const [showSources, setShowSources] = useState(false)

  return (
    <div className={`message message-${role}`}>
      <div className="message-text">{content}</div>

      {role === 'assistant' && sources?.length > 0 && (
        <>
          <button
            className={`sources-toggle ${showSources ? 'open' : ''}`}
            onClick={() => setShowSources(s => !s)}
          >
            Sources ({sources.length})
            <span className="arrow">▾</span>
          </button>

          {showSources && (
            <div className="sources-panel">
              {sources.map((s, i) => (
                <div key={i} className="source-item">
                  <div className="source-header">
                    <span className="source-name">[{i + 1}] {s.name}</span>
                    {s.score && (
                      <span className="source-score">{s.score}% match</span>
                    )}
                  </div>
                  <div className="source-snippet">{s.snippet}</div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
