import { useState, useRef, useCallback } from 'react'

const API = import.meta.env.VITE_API_URL || ''

export function useResearch() {
  const [status, setStatus]           = useState('idle')   // idle | running | done | error
  const [events, setEvents]           = useState([])
  const [metrics, setMetrics]         = useState({})        // papers, confidence, round, currency, verdict
  const [agentStatus, setAgentStatus] = useState({})        // agent → 'start' | 'done' | 'error'
  const [result, setResult]           = useState(null)
  const [error, setError]             = useState(null)
  const esRef        = useRef(null)
  const jobIdRef     = useRef(null)   // current job so reconnect uses the right id
  const reconnectRef = useRef(null)   // reconnect timeout handle

  const run = useCallback(async (topic) => {
    esRef.current?.close()
    setStatus('running')
    setEvents([])
    setMetrics({})
    setAgentStatus({})
    setResult(null)
    setError(null)

    try {
      const res = await fetch(`${API}/api/research/start`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ topic }),
      })
      if (!res.ok) throw new Error(
        res.status === 502 || res.status === 503
          ? `Server unavailable (${res.status}) — the pipeline may be starting up. Please try again in a few seconds.`
          : `HTTP ${res.status}`
      )
      const { job_id } = await res.json()
      jobIdRef.current = job_id

      const openSSE = (id) => {
        clearTimeout(reconnectRef.current)
        const es = new EventSource(`${API}/api/research/events/${id}`)
        esRef.current = es

        es.onmessage = (e) => {
          const raw = e.data
          // SSE comment heartbeats come through as empty data — ignore
          if (!raw || raw === 'ping') return
          const data = JSON.parse(raw)

          // Terminal status — pipeline finished or errored.
          // Agent progress events also carry status:'done'/'start', so guard with !data.agent
          if (!data.agent && (data.status === 'done' || data.status === 'error')) {
            es.close()
            if (data.status === 'done') {
              fetch(`${API}/api/research/result/${id}`)
                .then(r => r.json())
                .then(r => { setResult(r); setStatus('done') })
                .catch(() => { setStatus('error'); setError('Failed to load result') })
            } else {
              setStatus('error')
              setError(data.error || 'Pipeline failed')
            }
            return
          }

          // Progress event — add to log
          setEvents(prev => [...prev, data])

          // Extract metrics from event kwargs
          setMetrics(m => ({
            ...m,
            ...(data.paper_count  !== undefined && { papers:     data.paper_count }),
            ...(data.query_count  !== undefined && { queries:    data.query_count }),
            ...(data.confidence   !== undefined && { confidence: data.confidence }),
            ...(data.round        !== undefined && { round:      data.round }),
            ...(data.verdict      !== undefined && { verdict:    data.verdict }),
            ...(data.year_from    !== undefined && { year_from:  data.year_from }),
            ...(data.year_to      !== undefined && { year_to:    data.year_to }),
          }))

          // Track per-agent status
          if (data.agent) {
            setAgentStatus(prev => ({ ...prev, [data.agent]: data.status }))
          }
        }

        es.onerror = () => {
          es.close()
          // If still running, reconnect after 2s — the pipeline keeps running on the server
          setStatus(s => {
            if (s === 'running') {
              reconnectRef.current = setTimeout(() => openSSE(jobIdRef.current), 2000)
            }
            return s
          })
        }
      }

      openSSE(job_id)
    } catch (err) {
      setStatus('error')
      setError(err.message)
    }
  }, [])

  const reset = useCallback(() => {
    clearTimeout(reconnectRef.current)
    esRef.current?.close()
    jobIdRef.current = null
    setStatus('idle')
    setEvents([])
    setMetrics({})
    setAgentStatus({})
    setResult(null)
    setError(null)
  }, [])

  return { run, reset, status, events, metrics, agentStatus, result, error }
}
