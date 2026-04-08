import { useEffect, useRef } from 'react'
import Message from './Message'

export default function Chat({ messages, loading }) {
  const bottomRef = useRef()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

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
          />
        ))}

        {loading && (
          <div className="thinking">
            <div className="thinking-dots">
              <span /><span /><span />
            </div>
            <span className="thinking-text">
              retrieving · reranking · generating
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
