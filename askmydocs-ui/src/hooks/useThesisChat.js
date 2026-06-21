import { useState, useCallback } from 'react'

const API = import.meta.env.VITE_API_URL || 'https://web-production-203a0.up.railway.app'

export function useThesisChat() {
  const [messages,  setMessages]  = useState([])
  const [streaming, setStreaming] = useState(false)

  const send = useCallback(async (text, researchResult) => {
    if (!text.trim() || streaming) return

    const userMsg = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setStreaming(true)

    const history = messages.map(m => ({ role: m.role, content: m.content }))
    let   buffer  = ''
    const aiId    = Date.now()

    setMessages(prev => [...prev, { id: aiId, role: 'assistant', content: '' }])

    try {
      const res = await fetch(`${API}/api/research/chat`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: text, result: researchResult || {}, history }),
      })

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.done) break
            if (data.token) {
              buffer += data.token
              setMessages(prev =>
                prev.map(m => m.id === aiId ? { ...m, content: buffer } : m)
              )
            }
            if (data.error) throw new Error(data.error)
          } catch {}
        }
      }
    } catch (err) {
      setMessages(prev =>
        prev.map(m => m.id === aiId ? { ...m, content: `Error: ${err.message}` } : m)
      )
    } finally {
      setStreaming(false)
    }
  }, [messages, streaming])

  const clear = useCallback(() => setMessages([]), [])

  return { messages, streaming, send, clear }
}
