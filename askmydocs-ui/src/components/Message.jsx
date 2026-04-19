import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function Message({ 
  role, content, sources, routing, 
  agent_type, cache_hit, rewritten_query, quality_score 
}) {
  const [showSources, setShowSources] = useState(false)
  const modelLabel = routing?.model?.includes('70b') ? '70B' : '8B'

  return (
    <div className={`message message-${role}`}>
      <div className="message-text">
        {role === 'assistant' ? (
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={{
              h1: (props) => <h3 style={{marginTop: '12px', marginBottom: '8px', fontSize: 'clamp(13px, 5vw, 14px)', fontWeight: 400}} {...props} />,
              h2: (props) => <h4 style={{marginTop: '12px', marginBottom: '8px', fontSize: 'clamp(12px, 4.5vw, 13px)', fontWeight: 400}} {...props} />,
              h3: (props) => <h5 style={{marginTop: '12px', marginBottom: '8px', fontSize: 'clamp(11px, 4vw, 12px)', fontWeight: 400}} {...props} />,
              ul: (props) => <ul style={{marginLeft: 'max(1em, 2vw)', lineHeight: '1.9', marginBottom: '8px'}} {...props} />,
              ol: (props) => <ol style={{marginLeft: 'max(1em, 2vw)', lineHeight: '1.9', marginBottom: '8px'}} {...props} />,
              li: (props) => <li style={{marginBottom: '4px'}} {...props} />,
              p: (props) => <p style={{marginBottom: '8px', wordBreak: 'break-word'}} {...props} />,
              code: ({inline, ...props}) => 
                inline ? (
                  <code style={{backgroundColor: 'var(--bg-3)', padding: '2px 6px', borderRadius: '2px', fontFamily: 'monospace', fontSize: 'clamp(12px, 3vw, 13px)', wordBreak: 'break-word'}} {...props} />
                ) : (
                  <pre style={{backgroundColor: 'var(--bg-3)', padding: '10px', borderRadius: '2px', overflow: 'auto', marginBottom: '8px', fontSize: 'clamp(11px, 3vw, 12px)'}}>
                    <code {...props} />
                  </pre>
                ),
            }}
          >
            {content}
          </ReactMarkdown>
        ) : (
          content
        )}
      </div>

      {role === 'assistant' && (
        <>
          {(agent_type || cache_hit || routing || rewritten_query) && (
            <div className="message-metadata">
              {agent_type && (
                <span className="metadata-badge metadata-agent">
                  {agent_type} agent
                </span>
              )}

              {cache_hit && (
                <span className="metadata-badge metadata-cache">
                  cache {cache_hit}
                </span>
              )}

              {routing && (
                <span className="metadata-badge metadata-routing">
                  {modelLabel} · score {routing.score?.toFixed(2)}
                </span>
              )}

              {rewritten_query && (
                <span className="metadata-badge metadata-query" title={rewritten_query}>
                  rewritten: "{rewritten_query.slice(0, 40)}{rewritten_query.length > 40 ? '…' : ''}"
                </span>
              )}
            </div>
          )}

          {sources && sources.length > 0 && (
            <>
              <button
                className={`sources-toggle ${showSources ? 'open' : ''}`}
                onClick={() => setShowSources(s => !s)}
                style={{ marginTop: '10px' }}
              >
                {showSources ? '' : ''} Sources ({sources.length})
              </button>
              
              {showSources && (
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
            </>
          )}
        </>
      )}
    </div>
  )
}
