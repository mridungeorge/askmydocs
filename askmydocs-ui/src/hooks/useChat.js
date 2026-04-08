import { useState, useCallback, useEffect } from 'react'
import { createClient } from '@supabase/supabase-js'
import axios from 'axios'

// Multi-document support enabled: add multiple PDFs/URLs via sidebar
const API_URL    = import.meta.env.VITE_API_URL    || 'https://askmydocs-production-a2bf.up.railway.app'
const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON)

// Axios instance that automatically adds the auth token
const api = axios.create({ baseURL: API_URL })
api.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

export function useAuth() {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check current session on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => setUser(session?.user ?? null)
    )
    return () => subscription.unsubscribe()
  }, [])

  const signInWithGoogle = () =>
    supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })

  const signInWithEmail = (email, password) =>
    supabase.auth.signInWithPassword({ email, password })

  const signUpWithEmail = (email, password) =>
    supabase.auth.signUp({ email, password })

  const signInWithPhone = (phone) =>
    supabase.auth.signInWithOtp({ phone })

  const verifyOtp = (phone, token) =>
    supabase.auth.verifyOtp({ phone, token, type: 'sms' })

  const signOut = () => supabase.auth.signOut()

  return {
    user, loading,
    signInWithGoogle, signInWithEmail,
    signUpWithEmail, signInWithPhone,
    verifyOtp, signOut,
  }
}

export function useChat() {
  const [messages, setMessages]     = useState([])
  const [chatLoading, setChatLoading] = useState(false)
  const [allSources, setAllSources] = useState([])
  const [scope, setScope]           = useState(null)
  const [ingested, setIngested]     = useState(false)
  const [status, setStatus]         = useState(null)

  const ingestUrl = useCallback(async (url) => {
    setStatus({ type: 'loading', text: 'fetching · chunking · embedding…' })
    try {
      const res = await api.post('/api/ingest', { url })
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

  const ingestPdf = useCallback(async (file) => {
    setStatus({ type: 'loading', text: 'reading · chunking · embedding…' })
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await api.post('/api/ingest-pdf', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
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

  const sendMessage = useCallback(async (query) => {
    if (!query.trim() || chatLoading) return
    const userMsg = { role: 'user', content: query, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setChatLoading(true)
    try {
      const res = await api.post('/api/chat', {
        query,
        source_name: scope,
        history: messages.map(m => ({ role: m.role, content: m.content })),
      })
      const { answer, sources, routing } = res.data
      setMessages(prev => [...prev, {
        role: 'assistant', content: answer,
        sources, routing, id: Date.now() + 1,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Something went wrong. Please try again.',
        sources: [], id: Date.now() + 1,
      }])
    } finally {
      setChatLoading(false)
    }
  }, [chatLoading, messages, scope])

  const clearAll = useCallback(() => {
    setMessages([])
    setAllSources([])
    setScope(null)
    setIngested(false)
    setStatus(null)
  }, [])

  return {
    messages, loading: chatLoading,
    allSources, scope, ingested, status,
    setScope, ingestUrl, ingestPdf,
    sendMessage, clearAll,
  }
}
