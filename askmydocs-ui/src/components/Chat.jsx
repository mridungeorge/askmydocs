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
          </div>
        )}

        {/* Loading indicator when retrieving (before streaming starts) */}
        {loading && !streamingText && (
          <div className="thinking">
            <div className="thinking-dots">
              <span /><span /><span />
            </div>
            <span className="thinking-text">
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
      `}</style>
    </div>
  )
}
