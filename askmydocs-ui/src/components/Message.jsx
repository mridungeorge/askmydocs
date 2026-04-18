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
              h1: (props) => <h3 style={{marginTop: '12px', marginBottom: '8px', fontSize: '14px', fontWeight: 400}} {...props} />,
              h2: (props) => <h4 style={{marginTop: '12px', marginBottom: '8px', fontSize: '13px', fontWeight: 400}} {...props} />,
              h3: (props) => <h5 style={{marginTop: '12px', marginBottom: '8px', fontSize: '12px', fontWeight: 400}} {...props} />,
              ul: (props) => <ul style={{marginLeft: '1.2em', lineHeight: '1.9', marginBottom: '8px'}} {...props} />,
              ol: (props) => <ol style={{marginLeft: '1.2em', lineHeight: '1.9', marginBottom: '8px'}} {...props} />,
              li: (props) => <li style={{marginBottom: '4px'}} {...props} />,
              p: (props) => <p style={{marginBottom: '8px'}} {...props} />,
              code: ({inline, ...props}) => 
                inline ? (
                  <code style={{backgroundColor: 'var(--bg-3)', padding: '2px 6px', borderRadius: '2px', fontFamily: 'monospace', fontSize: '13px'}} {...props} />
                ) : (
                  <pre style={{backgroundColor: 'var(--bg-3)', padding: '10px', borderRadius: '2px', overflow: 'auto', marginBottom: '8px'}}>
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
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '12px',
              marginTop: '16px',
            }}>
              {agent_type && (
                <span style={{
                  fontFamily: "'Noto Serif', serif",
                  fontSize: '10px',
                  fontStyle: 'italic',
                  color: '#888',
                  letterSpacing: '0.05em',
                }}>
                  {agent_type} agent
                </span>
              )}

              {cache_hit && (
                <span style={{
                  fontFamily: "'Noto Sans JP', sans-serif",
                  fontSize: '10px',
                  fontWeight: 300,
                  letterSpacing: '0.15em',
                  textTransform: 'uppercase',
                  color: '#3a7a3a',
                  padding: '2px 6px',
                  border: '1px solid #3a7a3a',
                }}>
                  cache {cache_hit}
                </span>
              )}

              {routing && (
                <span style={{
                  fontFamily: "'Noto Serif', serif",
                  fontSize: '10px',
                  fontStyle: 'italic',
                  color: '#888',
                  letterSpacing: '0.05em',
                }}>
                  {modelLabel}  score {routing.score?.toFixed(2)}
                </span>
              )}

              {rewritten_query && (
                <span style={{
                  fontFamily: "'Noto Serif', serif",
                  fontSize: '10px',
                  fontStyle: 'italic',
                  color: '#888',
                  letterSpacing: '0.05em',
                }}>
                  rewritten: "{rewritten_query.slice(0, 40)}{rewritten_query.length > 40 ? '' : ''}"
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
