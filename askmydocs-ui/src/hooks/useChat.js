import { useState, useCallback, useEffect, useRef } from 'react'
import { createClient } from '@supabase/supabase-js'
import axios from 'axios'

const API_URL       = import.meta.env.VITE_API_URL    || 'https://askmydocs-production-a2bf.up.railway.app'
const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON)

const api = axios.create({ baseURL: API_URL })
api.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

async function getAuthToken() {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token || ''
}

export function useAuth() {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setLoading(false)
    })
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => setUser(session?.user ?? null)
    )
    return () => subscription.unsubscribe()
  }, [])

  return {
    user, loading,
    signInWithGoogle: () => supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    }),
    signInWithEmail: (email, password) => supabase.auth.signInWithPassword({ email, password }),
    signUpWithEmail: (email, password) => supabase.auth.signUp({ email, password }),
    signInWithPhone: (phone) => supabase.auth.signInWithOtp({ phone }),
    verifyOtp: (phone, token) => supabase.auth.verifyOtp({ phone, token, type: 'sms' }),
    signOut: () => supabase.auth.signOut(),
  }
}

export function useChat() {
  const [messages, setMessages]         = useState([])
  const [chatLoading, setChatLoading]   = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [allSources, setAllSources]     = useState([])
  const [scope, setScope]               = useState(null)
  const [ingested, setIngested]         = useState(false)
  const [status, setStatus]             = useState(null)
  const [summaries, setSummaries]       = useState({})
  const abortRef                        = useRef(null)

  const ingestUrl = useCallback(async (url) => {
    setStatus({ type: 'loading', text: 'fetching · chunking · embedding…' })
    try {
      const res = await api.post('/api/ingest', { url })
      const { title, chunks, summary } = res.data
      setAllSources(prev => prev.includes(title) ? prev : [...prev, title])
      if (summary) setSummaries(prev => ({ ...prev, [title]: summary }))
      setScope(title)
      setIngested(true)
      setMessages([])
      setStatus({ type: 'success', text: `${chunks} chunks indexed` })
    } catch (err) {
      setStatus({ type: 'error', text: err.response?.data?.detail || err.message })
    }
  }, [])

  const ingestPdf = useCallback(async (file, useMultimodal = true) => {
    setStatus({ type: 'loading', text: 'reading · extracting images · embedding…' })
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await api.post(
        `/api/ingest-pdf?multimodal=${useMultimodal}`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      const { title, chunks, extra_chunks, summary } = res.data
      setAllSources(prev => prev.includes(title) ? prev : [...prev, title])
      if (summary) setSummaries(prev => ({ ...prev, [title]: summary }))
      setScope(title)
      setIngested(true)
      setMessages([])
      const extraNote = extra_chunks > 0 ? ` + ${extra_chunks} images/tables` : ''
      setStatus({ type: 'success', text: `${chunks}${extraNote} chunks indexed` })
    } catch (err) {
      setStatus({ type: 'error', text: err.response?.data?.detail || err.message })
    }
  }, [])

  const sendMessage = useCallback(async (query, useStreaming = true) => {
    if (!query.trim() || chatLoading) return

    const userMsg = { role: 'user', content: query, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setChatLoading(true)
    setStreamingText('')

    const token = await getAuthToken()
    const endpoint = useStreaming ? '/api/chat/stream' : '/api/chat'

    if (useStreaming) {
      // ── Streaming path ───────────────────────────────────────────────────
      const controller = new AbortController()
      abortRef.current = controller

      try {
        const response = await fetch(`${API_URL}${endpoint}`, {
          method:  'POST',
          headers: {
            'Content-Type':  'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body:   JSON.stringify({
            query,
            source_name: scope,
            history: messages.map(m => ({ role: m.role, content: m.content })),
          }),
          signal: controller.signal,
        })

        if (!response.ok) throw new Error(`API error: ${response.statusText}`)

        const reader    = response.body.getReader()
        const decoder   = new TextDecoder()
        let   fullText  = ''
        let   metadata  = {}

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const data = JSON.parse(line.slice(6))

              if (data.type === 'token') {
                fullText += data.content
                setStreamingText(fullText)  // live update

              } else if (data.type === 'done') {
                metadata = data

              } else if (data.type === 'error') {
                fullText = `Error: ${data.message}`
              }
            } catch (_) {
              // Malformed SSE line — skip
            }
          }
        }

        // Convert streaming text to permanent message
        setStreamingText('')
        setMessages(prev => [...prev, {
          role:            'assistant',
          content:         fullText,
          sources:         metadata.sources || [],
          routing:         metadata.routing || {},
          agent_type:      metadata.agent_type || 'stream',
          cache_hit:       metadata.cache_hit || '',
          rewritten_query: metadata.rewritten_query || query,
          blocked:         metadata.blocked || false,
          id:              Date.now() + 1,
        }])

      } catch (err) {
        if (err.name !== 'AbortError') {
          setStreamingText('')
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: 'Something went wrong. Please try again.',
            sources: [], id: Date.now() + 1,
          }])
        }
      }

    } else {
      // ── Non-streaming path (fallback) ────────────────────────────────────
      try {
        const res = await api.post('/api/chat', {
          query,
          source_name: scope,
          history: messages.map(m => ({ role: m.role, content: m.content })),
        })
        const { answer, sources, routing, agent_type, quality_score,
                cache_hit, rewritten_query, blocked } = res.data
        setMessages(prev => [...prev, {
          role: 'assistant', content: answer, sources, routing,
          agent_type, quality_score, cache_hit, rewritten_query, blocked,
          id: Date.now() + 1,
        }])
      } catch (err) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Something went wrong. Please try again.',
          sources: [], id: Date.now() + 1,
        }])
      }
    }

    setChatLoading(false)
  }, [chatLoading, messages, scope])

  const stopStreaming = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      setChatLoading(false)
      setStreamingText('')
    }
  }, [])

  const clearAll = useCallback(() => {
    setMessages([])
    setAllSources([])
    setScope(null)
    setIngested(false)
    setStatus(null)
    setSummaries({})
  }, [])

  return {
    messages, loading: chatLoading, streamingText,
    allSources, scope, ingested, status, summaries,
    setScope, ingestUrl, ingestPdf,
    sendMessage, stopStreaming, clearAll,
  }
}
