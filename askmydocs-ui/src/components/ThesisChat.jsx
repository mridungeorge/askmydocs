import { useState, useRef, useEffect, useCallback } from 'react'
import { useThesisChat } from '../hooks/useThesisChat'

const SUGGESTIONS = [
  { icon: '📚', label: 'Literature Review', prompt: 'Write a comprehensive literature review for my thesis based on the research findings.' },
  { icon: '🔬', label: 'Methodology',       prompt: 'Draft a methodology section explaining how the research approach and methods align with the findings.' },
  { icon: '✍️', label: 'Introduction',      prompt: 'Write an introduction chapter with background, problem statement, and research objectives.' },
  { icon: '💬', label: 'Discussion',        prompt: 'Write a discussion section interpreting the findings in light of the existing literature.' },
  { icon: '🎯', label: 'Conclusion',        prompt: 'Write a conclusion summarising key contributions, limitations, and future research directions.' },
  { icon: '📖', label: 'Bibliography',      prompt: 'Format a bibliography in APA 7th edition using all source papers from the research.' },
]

/* ─── Animations ────────────────────────────────────────────────────────────── */
const CSS = `
  @keyframes materialIn {
    from { opacity: 0; transform: translateY(8px); filter: blur(3px); }
    to   { opacity: 1; transform: translateY(0);   filter: blur(0); }
  }

  @keyframes bubblePop {
    0%   { opacity: 0; transform: scale(0.88) translateY(10px); filter: blur(3px); }
    60%  { opacity: 1; transform: scale(1.02) translateY(-2px); filter: blur(0); }
    80%  { transform: scale(0.99) translateY(0.5px); }
    100% { transform: scale(1) translateY(0); }
  }

  @keyframes bubblePopRight {
    0%   { opacity: 0; transform: scale(0.88) translateY(10px) translateX(8px); filter: blur(3px); }
    60%  { opacity: 1; transform: scale(1.02) translateY(-2px) translateX(-1px); filter: blur(0); }
    80%  { transform: scale(0.99) translateY(0.5px) translateX(0); }
    100% { transform: scale(1) translateY(0) translateX(0); }
  }

  @keyframes chipIn {
    from { opacity: 0; transform: translateY(10px) scale(0.92); filter: blur(2px); }
    to   { opacity: 1; transform: translateY(0)    scale(1);    filter: blur(0); }
  }

  @keyframes thinkDot {
    0%, 60%, 100% { transform: translateY(0);    opacity: 0.25; }
    30%           { transform: translateY(-5px);  opacity: 1; }
  }

  @keyframes headerSlide {
    from { opacity: 0; transform: translateY(-100%); }
    to   { opacity: 1; transform: translateY(0); }
  }

  @keyframes breathe {
    0%, 100% { opacity: 0.5; transform: scale(1); }
    50%       { opacity: 0;   transform: scale(1.4); }
  }

  .tc-chip:hover:not(:disabled) {
    background: var(--bg-2, #f2f2ee) !important;
    border-color: var(--text, #1a1a1a) !important;
    color: var(--text, #1a1a1a) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
  }
  .tc-chip:active:not(:disabled) { transform: scale(0.96) !important; }

  .tc-send:hover:not(:disabled) {
    background: var(--text-2, #555) !important;
    transform: scale(1.06) !important;
  }
  .tc-send:active:not(:disabled) { transform: scale(0.94) !important; }

  .tc-clear:hover { color: var(--text, #1a1a1a) !important; }

  .tc-scroll::-webkit-scrollbar { width: 3px; }
  .tc-scroll::-webkit-scrollbar-track { background: transparent; }
  .tc-scroll::-webkit-scrollbar-thumb { background: var(--border, #d8d8d2); }
`

/* ─── Sub-components ─────────────────────────────────────────────────────────── */
function ThinkingDots() {
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', height: 16 }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: 5, height: 5, borderRadius: '50%',
          background: 'var(--text-3, #888)',
          display: 'inline-block',
          animation: `thinkDot 1.3s ease-in-out ${i * 0.18}s infinite`,
        }} />
      ))}
    </span>
  )
}

function Avatar({ size = 28, pulsing = false }) {
  return (
    <div style={{ position: 'relative', flexShrink: 0, width: size, height: size }}>
      {pulsing && (
        <div style={{
          position: 'absolute', inset: -3, borderRadius: '50%',
          border: '1.5px solid var(--text-4, #aaa)',
          animation: 'breathe 1.8s ease-in-out infinite',
        }} />
      )}
      <div style={{
        width: size, height: size, borderRadius: '50%',
        background: 'var(--text, #1a1a1a)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--bg, #fafaf8)',
        fontFamily: 'var(--serif, serif)',
        fontSize: size * 0.38,
        fontStyle: 'italic',
        letterSpacing: '-0.02em',
        position: 'relative', zIndex: 1,
      }}>
        a
      </div>
    </div>
  )
}

function Bubble({ role, content, isStreaming }) {
  const isAI = role === 'assistant'
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-end', gap: 10,
      flexDirection: isAI ? 'row' : 'row-reverse',
      animation: `${isAI ? 'bubblePop' : 'bubblePopRight'} 0.4s cubic-bezier(0.34,1.2,0.64,1) both`,
    }}>
      {isAI && <Avatar size={26} pulsing={isStreaming} />}

      <div style={{
        maxWidth: '78%',
        padding: '10px 14px',
        borderRadius: isAI ? '2px 14px 14px 14px' : '14px 14px 2px 14px',
        background: isAI ? 'var(--bg, #fafaf8)' : 'var(--text, #1a1a1a)',
        color: isAI ? 'var(--text, #1a1a1a)' : 'var(--bg, #fafaf8)',
        fontSize: 13,
        lineHeight: 1.75,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        fontWeight: 300,
        letterSpacing: '0.01em',
        boxShadow: isAI
          ? '0 0 0 1px var(--border, #d8d8d2), 0 2px 8px rgba(0,0,0,0.04)'
          : '0 4px 16px rgba(0,0,0,0.18)',
      }}>
        {isStreaming ? <ThinkingDots /> : content}
      </div>
    </div>
  )
}

/* ─── Main ────────────────────────────────────────────────────────────────────── */
export default function ThesisChat({ researchResult, chatHook }) {
  const fallback = useThesisChat()
  const { messages, streaming, send, clear } = chatHook || fallback
  const [input, setInput]       = useState('')
  const [focused, setFocused]   = useState(false)
  const [pressed, setPressed]   = useState(false)
  const bottomRef               = useRef(null)
  const textareaRef             = useRef(null)
  const isEmpty = messages.length === 0
  const canSend = input.trim() && !streaming

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, streaming])

  const submit = useCallback((text) => {
    if (!text.trim() || streaming) return
    send(text, researchResult)
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [streaming, send, researchResult])

  const handleSend = () => {
    setPressed(true)
    setTimeout(() => setPressed(false), 180)
    submit(input)
  }

  return (
    <>
      <style>{CSS}</style>

      <div style={{
        display: 'flex', flexDirection: 'column', height: '100%',
        background: 'var(--bg-2, #f2f2ee)',
        borderRadius: 0,
        overflow: 'hidden',
        border: '1px solid var(--border, #d8d8d2)',
      }}>

        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 20px',
          borderBottom: '1px solid var(--border, #d8d8d2)',
          background: 'var(--bg, #fafaf8)',
          flexShrink: 0,
          animation: 'headerSlide 0.35s cubic-bezier(0.34,1.2,0.64,1) both',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Avatar size={32} pulsing={streaming} />
            <div>
              <div style={{
                fontFamily: 'var(--serif, serif)',
                fontSize: 13,
                fontWeight: 300,
                fontStyle: 'italic',
                color: 'var(--text, #1a1a1a)',
                letterSpacing: '0.01em',
              }}>
                Thesis Assistant
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-4, #aaa)', letterSpacing: '0.12em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 5, marginTop: 1 }}>
                <span style={{
                  width: 5, height: 5, borderRadius: '50%',
                  background: streaming ? 'var(--text-3, #888)' : 'var(--text, #1a1a1a)',
                  display: 'inline-block',
                  transition: 'background 0.4s ease',
                }} />
                {streaming ? 'Writing…' : 'Grounded in your research'}
              </div>
            </div>
          </div>
          {!isEmpty && (
            <button
              className="tc-clear"
              onClick={clear}
              style={{
                fontSize: 10, color: 'var(--text-4, #aaa)',
                background: 'none', border: 'none',
                cursor: 'pointer', padding: '4px 8px',
                letterSpacing: '0.15em', textTransform: 'uppercase',
                fontFamily: 'var(--sans, sans-serif)',
                transition: 'color 0.15s',
              }}
            >
              Clear
            </button>
          )}
        </div>

        {/* Messages */}
        <div
          className="tc-scroll"
          style={{
            flex: 1, overflowY: 'auto',
            padding: '20px 20px 10px',
            display: 'flex', flexDirection: 'column', gap: 14,
            minHeight: 0,
          }}
        >
          {/* Empty state — greeting + chips */}
          {isEmpty && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18, animation: 'materialIn 0.4s ease 0.1s both' }}>

              {/* Greeting bubble */}
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10 }}>
                <Avatar size={26} />
                <div style={{
                  maxWidth: '82%', padding: '10px 14px',
                  borderRadius: '2px 14px 14px 14px',
                  background: 'var(--bg, #fafaf8)',
                  boxShadow: '0 0 0 1px var(--border, #d8d8d2), 0 2px 8px rgba(0,0,0,0.04)',
                  fontSize: 13, lineHeight: 1.75,
                  color: 'var(--text, #1a1a1a)',
                  fontWeight: 300, letterSpacing: '0.01em',
                }}>
                  Hi — I've read through your research findings. What section of your thesis would you like me to draft?
                </div>
              </div>

              {/* Suggestion chips */}
              <div style={{ paddingLeft: 36 }}>
                <div style={{
                  fontSize: 9, fontWeight: 300, color: 'var(--text-4, #aaa)',
                  letterSpacing: '0.3em', textTransform: 'uppercase',
                  marginBottom: 10,
                  animation: 'materialIn 0.35s ease 0.3s both',
                  fontFamily: 'var(--serif, serif)', fontStyle: 'italic',
                }}>
                  Quick starts
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                  {SUGGESTIONS.map((s, i) => (
                    <button
                      key={s.label}
                      className="tc-chip"
                      onClick={() => submit(s.prompt)}
                      disabled={streaming}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '6px 12px',
                        border: '1px solid var(--border, #d8d8d2)',
                        background: 'var(--bg, #fafaf8)',
                        fontSize: 11.5,
                        color: 'var(--text-2, #555)',
                        cursor: streaming ? 'not-allowed' : 'pointer',
                        fontFamily: 'var(--sans, sans-serif)',
                        fontWeight: 300,
                        letterSpacing: '0.03em',
                        borderRadius: 0,
                        transition: 'transform 0.16s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.16s ease, background 0.15s, border-color 0.15s, color 0.15s',
                        animation: `chipIn 0.36s cubic-bezier(0.34,1.2,0.64,1) ${0.35 + i * 0.055}s both`,
                      }}
                    >
                      <span style={{ fontSize: 13 }}>{s.icon}</span>
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Chat messages */}
          {messages.map((msg, i) => {
            const isLastAI = msg.role === 'assistant' && i === messages.length - 1
            return (
              <Bubble
                key={msg.id || i}
                role={msg.role}
                content={msg.content || ''}
                isStreaming={isLastAI && streaming && !msg.content}
              />
            )
          })}

          {/* Typing indicator */}
          {streaming && messages.length > 0 && messages[messages.length - 1]?.role === 'user' && (
            <div style={{
              display: 'flex', alignItems: 'flex-end', gap: 10,
              animation: 'bubblePop 0.32s cubic-bezier(0.34,1.2,0.64,1) both',
            }}>
              <Avatar size={26} pulsing />
              <div style={{
                padding: '10px 14px', borderRadius: '2px 14px 14px 14px',
                background: 'var(--bg, #fafaf8)',
                boxShadow: '0 0 0 1px var(--border, #d8d8d2), 0 2px 8px rgba(0,0,0,0.04)',
              }}>
                <ThinkingDots />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div style={{
          padding: '12px 16px 16px',
          borderTop: '1px solid var(--border, #d8d8d2)',
          background: 'var(--bg, #fafaf8)',
          flexShrink: 0,
          animation: 'materialIn 0.4s ease 0.15s both',
        }}>
          <div style={{
            display: 'flex', gap: 8, alignItems: 'flex-end',
            borderBottom: `1px solid ${focused ? 'var(--text, #1a1a1a)' : 'var(--border, #d8d8d2)'}`,
            paddingBottom: 8,
            transition: 'border-color 0.15s ease',
          }}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
              }}
              onInput={e => {
                e.target.style.height = 'auto'
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
              }}
              placeholder="Ask about your research…"
              rows={1}
              style={{
                flex: 1, border: 'none', background: 'transparent',
                fontSize: 13, resize: 'none', fontFamily: 'var(--sans, sans-serif)',
                fontWeight: 300, color: 'var(--text, #1a1a1a)',
                lineHeight: 1.65, maxHeight: 120, overflowY: 'auto',
                outline: 'none', letterSpacing: '0.01em',
              }}
            />
            <button
              className="tc-send"
              onClick={handleSend}
              disabled={!canSend}
              style={{
                width: 30, height: 30,
                border: '1px solid var(--text, #1a1a1a)',
                background: canSend ? 'var(--text, #1a1a1a)' : 'transparent',
                color: canSend ? 'var(--bg, #fafaf8)' : 'var(--border, #d8d8d2)',
                borderColor: canSend ? 'var(--text, #1a1a1a)' : 'var(--border, #d8d8d2)',
                cursor: canSend ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, fontSize: 14, borderRadius: 0,
                transition: 'all 0.15s ease',
                transform: pressed ? 'scale(0.92)' : 'scale(1)',
              }}
            >
              ↑
            </button>
          </div>
          <div style={{
            fontSize: 9.5, color: 'var(--text-5, #ccc)',
            marginTop: 7, letterSpacing: '0.12em',
            textTransform: 'uppercase',
            fontFamily: 'var(--sans, sans-serif)',
            fontWeight: 300,
            opacity: focused ? 1 : 0,
            transition: 'opacity 0.2s ease',
          }}>
            Enter to send · Shift+Enter new line
          </div>
        </div>
      </div>
    </>
  )
}
