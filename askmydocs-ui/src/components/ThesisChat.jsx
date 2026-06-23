import { useState, useRef, useEffect } from 'react'
import { useThesisChat } from '../hooks/useThesisChat'

const PILLS = [
  { label: 'Literature Review', prompt: 'Write a comprehensive literature review for my thesis based on the research findings.' },
  { label: 'Methodology',       prompt: 'Draft a methodology section explaining how the research approach and methods align with the findings.' },
  { label: 'Introduction',      prompt: 'Write an introduction chapter with background, problem statement, and research objectives.' },
  { label: 'Discussion',        prompt: 'Write a discussion section interpreting the findings in light of the existing literature.' },
  { label: 'Conclusion',        prompt: 'Write a conclusion summarising key contributions, limitations, and future research directions.' },
  { label: 'Bibliography',      prompt: 'Format a bibliography in APA 7th edition using all source papers from the research.' },
]

export default function ThesisChat({ researchResult, chatHook }) {
  const fallback = useThesisChat()
  const { messages, streaming, send, clear } = chatHook || fallback
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, streaming])

  const submit = (text) => {
    if (!text.trim() || streaming) return
    send(text, researchResult)
    setInput('')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', margin: 0 }}>Write Your Thesis</h3>
          <p style={{ fontSize: 12, color: '#888', marginTop: 2 }}>Grounded in your research findings</p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clear}
            style={{ fontSize: 11, color: '#888', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px' }}
          >
            Clear chat
          </button>
        )}
      </div>

      {/* Quick-start pills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {PILLS.map(p => (
          <button
            key={p.label}
            onClick={() => submit(p.prompt)}
            disabled={streaming}
            style={{
              padding:      '6px 14px',
              borderRadius: 20,
              border:       '1px solid #e5e7eb',
              background:   '#f9fafb',
              fontSize:     12,
              color:        '#374151',
              cursor:       streaming ? 'not-allowed' : 'pointer',
              transition:   'background 0.15s',
            }}
            onMouseEnter={e => { if (!streaming) e.target.style.background = '#eff6ff' }}
            onMouseLeave={e => { e.target.style.background = '#f9fafb' }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Message thread */}
      {messages.length > 0 && (
        <div style={{
          display:       'flex',
          flexDirection: 'column',
          gap:           12,
          maxHeight:     420,
          overflowY:     'auto',
          padding:       '4px 0',
        }}>
          {messages.map((msg, i) => (
            <div
              key={msg.id || i}
              style={{
                display:       'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              <div style={{
                maxWidth:     '82%',
                padding:      '10px 14px',
                borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '4px 16px 16px 16px',
                background:   msg.role === 'user' ? '#4f46e5' : '#f0fdf4',
                color:        msg.role === 'user' ? '#fff' : '#14532d',
                fontSize:     13,
                lineHeight:   1.6,
                whiteSpace:   'pre-wrap',
                wordBreak:    'break-word',
                border:       msg.role === 'assistant' ? '1px solid #bbf7d0' : 'none',
              }}>
                {msg.content || (streaming && i === messages.length - 1 ? '▌' : '')}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Input */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(input) } }}
          placeholder="Ask about your research, or click a quick-start above…"
          rows={2}
          style={{
            flex:        1,
            padding:     '10px 12px',
            borderRadius: 10,
            border:      '1px solid #e5e7eb',
            fontSize:    13,
            resize:      'none',
            fontFamily:  'inherit',
            outline:     'none',
            background:  '#fafaf8',
          }}
        />
        <button
          onClick={() => submit(input)}
          disabled={!input.trim() || streaming}
          style={{
            padding:      '10px 20px',
            borderRadius: 10,
            border:       'none',
            background:   input.trim() && !streaming ? '#4f46e5' : '#e5e7eb',
            color:        input.trim() && !streaming ? '#fff' : '#9ca3af',
            fontSize:     13,
            fontWeight:   600,
            cursor:       input.trim() && !streaming ? 'pointer' : 'not-allowed',
            transition:   'background 0.15s',
            flexShrink:   0,
          }}
        >
          {streaming ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
