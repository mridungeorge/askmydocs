import { useState, useRef, useEffect } from 'react'

export default function Input({ onSend, onStop, disabled, isStreaming }) {
  const [value, setValue] = useState('')
  const textareaRef       = useRef()

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }, [value])

  const handleSend = () => {
    if (!value.trim() || disabled) return
    onSend(value.trim())
    setValue('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleStop = () => {
    if (onStop) onStop()
  }

  return (
    <div className="chat-input-bar">
      <div className="chat-input-inner">
        {isStreaming ? (
          <>
            <textarea
              ref={textareaRef}
              className="chat-textarea"
              placeholder="Ask a question…"
              value={value}
              onChange={e => setValue(e.target.value)}
              onKeyDown={handleKey}
              rows={1}
              disabled={true}
            />
            <button
              className="stop-btn"
              onClick={handleStop}
              title="Stop streaming"
              style={{
                background: '#7a3a3a',
                color: 'white',
                border: 'none',
                width: 40,
                height: 40,
                borderRadius: 4,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                fontWeight: 500,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
              }}
            >
              Stop
            </button>
          </>
        ) : (
          <>
            <textarea
              ref={textareaRef}
              className="chat-textarea"
              placeholder="Ask a question…"
              value={value}
              onChange={e => setValue(e.target.value)}
              onKeyDown={handleKey}
              rows={1}
              disabled={disabled}
            />
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={!value.trim() || disabled}
              title="Send (Shift+Enter for multiline)"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </>
        )}
      </div>
    </div>
  )
}
