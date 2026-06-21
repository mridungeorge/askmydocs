import { useState, useRef, useCallback } from 'react'

const API = import.meta.env.VITE_API_URL || 'https://web-production-203a0.up.railway.app'

export function useResearch() {
  const [status, setStatus]           = useState('idle')   // idle | running | done | error
  const [events, setEvents]           = useState([])
  const [metrics, setMetrics]         = useState({})        // papers, confidence, round, currency, verdict
  const [agentStatus, setAgentStatus] = useState({})        // agent → 'start' | 'done' | 'error'
  const [result, setResult]           = useState(null)
  const [error, setError]             = useState(null)
  const esRef = useRef(null)

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
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const { job_id } = await res.json()

      const es = new EventSource(`${API}/api/research/events/${job_id}`)
      esRef.current = es

      es.onmessage = (e) => {
        const data = JSON.parse(e.data)

        // Terminal status — pipeline finished or errored
        if (data.status === 'done' || data.status === 'error') {
          es.close()
          if (data.status === 'done') {
            fetch(`${API}/api/research/result/${job_id}`)
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
        setStatus(s => {
          if (s !== 'done') { setError('Connection lost'); return 'error' }
          return s
        })
      }
    } catch (err) {
      setStatus('error')
      setError(err.message)
    }
  }, [])

  const reset = useCallback(() => {
    esRef.current?.close()
    setStatus('idle')
    setEvents([])
    setMetrics({})
    setAgentStatus({})
    setResult(null)
    setError(null)
  }, [])

  return { run, reset, status, events, metrics, agentStatus, result, error }
}
