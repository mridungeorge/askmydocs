import { useEffect, useRef } from 'react'
import Message from './Message'

export default function Chat({ messages, loading, streamingText }) {
  const bottomRef = useRef()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, streamingText])

  return (
    <div className="chat-thread">
      <div className="chat-thread-inner">
        {messages.map(msg => (
          <Message
            key={msg.id}
            role={msg.role}
            content={msg.content}
            sources={msg.sources}
            routing={msg.routing}
            agentType={msg.agent_type}
            cacheHit={msg.cache_hit}
            rewrittenQuery={msg.rewritten_query}
            blocked={msg.blocked}
          />
        ))}

        {/* Live streaming text — appears before message is complete */}
        {loading && streamingText && (
          <div className="message message-assistant">
            <div className="message-text" style={{ whiteSpace: 'pre-wrap' }}>
              {streamingText}
              <span style={{
                display: 'inline-block',
                width: 8,
                height: 14,
                background: 'var(--text)',
                marginLeft: 2,
                animation: 'blink 1s step-end infinite',
                verticalAlign: 'text-bottom',
              }} />
            </div>
            <div style={{
              fontSize: '0.8rem',
              color: 'var(--muted)',
              marginTop: '0.5rem',
              fontStyle: 'italic',
            }}>
              streaming…
            </div>
          </div>
        )}

        {/* Loading indicator when retrieving (before streaming starts) */}
        {loading && !streamingText && (
          <div className="loading-indicator">
            <div className="loading-dots">
              <span /><span /><span />
            </div>
            <span className="loading-text">
              classifying · retrieving · generating
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.05); opacity: 0.7; }
        }
        
        .loading-indicator {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 1.5rem;
          gap: 0.8rem;
        }
        
        .loading-dots {
          display: flex;
          gap: 0.5rem;
          font-size: 1.5rem;
        }
        
        .loading-dots span {
          display: inline-block;
          animation: pulse 1.4s ease-in-out infinite;
        }
        
        .loading-dots span:nth-child(2) {
          animation-delay: 0.2s;
        }
        
        .loading-dots span:nth-child(3) {
          animation-delay: 0.4s;
        }
        
        .loading-text {
          font-size: 0.85rem;
          color: var(--muted);
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }
      `}</style>
    </div>
  )
}
