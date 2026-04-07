import { useState, useCallback } from 'react'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'https://askmydocs-production-a2bf.up.railway.app'

export function useChat() {
  const [messages, setMessages]     = useState([])
  const [sources, setSources]       = useState([])
  const [loading, setLoading]       = useState(false)
  const [allSources, setAllSources] = useState([])
  const [scope, setScope]           = useState(null)
  const [ingested, setIngested]     = useState(false)
  const [status, setStatus]         = useState(null) // {type, text}

  const ingestUrl = useCallback(async (url) => {
    setStatus({ type: 'loading', text: 'fetching · chunking · embedding…' })
    try {
      const res = await axios.post(`${API_URL}/api/ingest`, { url })
      const { title, chunks } = res.data
      setAllSources(prev => prev.includes(title) ? prev : [...prev, title])
      setScope(title)
      setIngested(true)
      setMessages([])
      setStatus({ type: 'success', text: `${chunks} chunks indexed` })
    } catch (err) {
      setStatus({ type: 'error', text: err.response?.data?.detail || err.message })
    }
  }, [])

  const ingestPdf = useCallback(async (fileArray) => {
    const files = Array.isArray(fileArray) ? fileArray : [fileArray]
    setStatus({ type: 'loading', text: `reading · chunking · embedding ${files.length} file${files.length > 1 ? 's' : ''}…` })
    try {
      let totalChunks = 0
      let lastTitle = ''
      const uniqueSources = new Set(allSources)
      
      for (const file of files) {
        const form = new FormData()
        form.append('file', file)
        const res = await axios.post(`${API_URL}/api/ingest-pdf`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        const { title, chunks } = res.data
        totalChunks += chunks
        lastTitle = title
        if (!uniqueSources.has(title)) {
          uniqueSources.add(title)
        }
      }
      
      setAllSources(Array.from(uniqueSources))
      setScope(lastTitle)
      setIngested(true)
      setMessages([])
      setStatus({ type: 'success', text: `${totalChunks} chunks indexed from ${files.length} file${files.length > 1 ? 's' : ''}` })
    } catch (err) {
      setStatus({ type: 'error', text: err.response?.data?.detail || err.message })
    }
  }, [allSources])

  const sendMessage = useCallback(async (query) => {
    if (!query.trim() || loading) return

    const userMsg = { role: 'user', content: query, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await axios.post(`${API_URL}/api/chat`, {
        query,
        source_name: scope,
        history: messages.map(m => ({ role: m.role, content: m.content })),
      })
      const { answer, sources: srcs } = res.data
      const assistantMsg = {
        role: 'assistant',
        content: answer,
        sources: srcs,
        id: Date.now() + 1,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      const errMsg = {
        role: 'assistant',
        content: 'Something went wrong. Please try again.',
        sources: [],
        id: Date.now() + 1,
      }
      setMessages(prev => [...prev, errMsg])
    } finally {
      setLoading(false)
    }
  }, [loading, messages, scope])

  const clearAll = useCallback(() => {
    setMessages([])
    setAllSources([])
    setScope(null)
    setIngested(false)
    setStatus(null)
  }, [])

  return {
    messages, loading, allSources, scope, ingested, status,
    setScope, ingestUrl, ingestPdf, sendMessage, clearAll,
  }
}
