import { useState, useRef }  from 'react'
import { useResearch }       from '../hooks/useResearch'
import { useThesisChat }     from '../hooks/useThesisChat'
import PipelineDiagram       from './PipelineDiagram'
import LiveLog               from './LiveLog'
import ThesisChat            from './ThesisChat'

const CURRENCY_COLORS = {
  EMERGING:  { bg: '#f0fdf4', text: '#15803d', border: '#86efac' },
  STABLE:    { bg: '#eff6ff', text: '#1d4ed8', border: '#93c5fd' },
  DECLINING: { bg: '#fefce8', text: '#a16207', border: '#fde047' },
  DEAD:      { bg: '#fef2f2', text: '#b91c1c', border: '#fca5a5' },
}

function MetricChip({ label, value, highlight }) {
  return (
    <div style={{
      padding:      '6px 14px',
      borderRadius: 20,
      background:   highlight ? '#4f46e5' : '#f3f4f6',
      color:        highlight ? '#fff' : '#374151',
      fontSize:     12,
      fontWeight:   500,
      display:      'flex',
      gap:          6,
      alignItems:   'center',
    }}>
      <span style={{ color: highlight ? '#c7d2fe' : '#9ca3af', fontSize: 11 }}>{label}</span>
      <span>{value ?? '—'}</span>
    </div>
  )
}

function OutstandingIssues({ issues = [], onFixAll, fixing }) {
  if (!issues.length) return null
  return (
    <div style={{
      background:   '#fffbeb',
      border:       '1px solid #fde68a',
      borderRadius: 10,
      padding:      16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h4 style={{ fontSize: 13, fontWeight: 600, color: '#92400e', margin: 0 }}>
          Outstanding Issues ({issues.length})
        </h4>
        {onFixAll && (
          <button
            onClick={onFixAll}
            disabled={fixing}
            style={{
              padding:      '5px 14px',
              borderRadius: 8,
              border:       'none',
              background:   fixing ? '#e5e7eb' : '#92400e',
              color:        fixing ? '#9ca3af' : '#fff',
              fontSize:     12,
              fontWeight:   600,
              cursor:       fixing ? 'not-allowed' : 'pointer',
            }}
          >
            {fixing ? 'Fixing…' : 'Fix All Issues'}
          </button>
        )}
      </div>
      <ul style={{ margin: 0, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {issues.map((issue, i) => (
          <li key={i} style={{ fontSize: 13, color: '#78350f', lineHeight: 1.5 }}>{issue}</li>
        ))}
      </ul>
    </div>
  )
}

function DownloadBtn({ label, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding:      '7px 16px',
        borderRadius: 8,
        border:       '1px solid #e5e7eb',
        background:   '#fff',
        fontSize:     12,
        color:        '#374151',
        cursor:       'pointer',
        fontWeight:   500,
      }}
    >
      ↓ {label}
    </button>
  )
}

export default function ResearchConductor() {
  const { run, reset, status, events, metrics, agentStatus, result, error } = useResearch()
  const thesisChat = useThesisChat()
  const chatSectionRef = useRef(null)
  const [topic, setTopic] = useState('')

  const handleFixAll = () => {
    if (!result?.critic_feedback?.length) return
    const issues = result.critic_feedback.map((iss, i) => `${i + 1}. ${iss}`).join('\n')
    const prompt = `Please rewrite the research draft addressing ALL of these outstanding issues and produce a complete, polished version with proper in-text citations (Author et al., Year):\n\n${issues}`
    thesisChat.send(prompt, result)
    // Scroll to chat
    setTimeout(() => chatSectionRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
  }

  const handleRun = () => {
    if (!topic.trim() || status === 'running') return
    run(topic.trim())
  }

  const downloadTxt = () => {
    if (!result?.draft) return
    const blob = new Blob([result.draft], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = 'research-draft.txt'; a.click()
    URL.revokeObjectURL(url)
  }

  const downloadJson = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = 'research-result.json'; a.click()
    URL.revokeObjectURL(url)
  }

  const currencyStyle = CURRENCY_COLORS[metrics.currency || result?.currency_verdict] || {}
  const confidence    = result?.confidence ?? metrics.confidence
  const confPct       = confidence !== undefined ? `${Math.round(confidence * 100)}%` : '—'
  const confOk        = confidence !== undefined && confidence >= 0.80

  return (
    <div style={{ padding: '32px 40px', maxWidth: 860, margin: '0 auto', fontFamily: 'var(--sans)' }}>

      {/* Title */}
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: '#1a1a1a', margin: 0 }}>Research Conductor</h2>
        <p style={{ fontSize: 13, color: '#888', marginTop: 4 }}>
          Multi-agent pipeline · 6 paper sources · RAG-grounded writing · Confidence-gated quality loop
        </p>
      </div>

      {/* Input phase */}
      {status === 'idle' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <textarea
            value={topic}
            onChange={e => setTopic(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleRun() } }}
            placeholder="Enter a research topic…  e.g. 'Agentic RAG systems for enterprise knowledge management'"
            rows={3}
            style={{
              width:        '100%',
              padding:      '14px 16px',
              borderRadius: 12,
              border:       '1.5px solid #e5e7eb',
              fontSize:     14,
              resize:       'none',
              fontFamily:   'inherit',
              outline:      'none',
              background:   '#fafaf8',
              boxSizing:    'border-box',
            }}
          />
          <button
            onClick={handleRun}
            disabled={!topic.trim()}
            style={{
              padding:      '12px 32px',
              borderRadius: 10,
              border:       'none',
              background:   topic.trim() ? '#4f46e5' : '#e5e7eb',
              color:        topic.trim() ? '#fff' : '#9ca3af',
              fontSize:     14,
              fontWeight:   600,
              cursor:       topic.trim() ? 'pointer' : 'not-allowed',
              alignSelf:    'flex-start',
            }}
          >
            Run Research
          </button>
        </div>
      )}

      {/* Running / done header with new research button */}
      {status !== 'idle' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 13, color: '#888', marginBottom: 4 }}>Topic</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a' }}>{topic}</div>
          </div>
          {status !== 'running' && (
            <button
              onClick={reset}
              style={{
                padding:      '8px 18px',
                borderRadius: 8,
                border:       '1px solid #e5e7eb',
                background:   '#fff',
                fontSize:     12,
                color:        '#374151',
                cursor:       'pointer',
                fontWeight:   500,
              }}
            >
              ＋ New Research
            </button>
          )}
        </div>
      )}

      {/* Pipeline diagram — always visible once started */}
      {status !== 'idle' && (
        <div style={{ marginBottom: 20 }}>
          <PipelineDiagram agentStatus={agentStatus} />
        </div>
      )}

      {/* Metrics chips */}
      {status !== 'idle' && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
          <MetricChip label="Papers" value={metrics.papers ?? result?.papers?.length} />
          <MetricChip label="Round"  value={metrics.round  ?? result?.round_num} />
          <MetricChip
            label="Confidence"
            value={confPct}
            highlight={confOk}
          />
          {(metrics.currency || result?.currency_verdict) && (
            <div style={{
              padding:      '6px 14px',
              borderRadius: 20,
              fontSize:     12,
              fontWeight:   500,
              background:   currencyStyle.bg   || '#f3f4f6',
              color:        currencyStyle.text  || '#374151',
              border:       `1px solid ${currencyStyle.border || '#e5e7eb'}`,
            }}>
              {metrics.currency || result?.currency_verdict}
            </div>
          )}
          {status === 'running' && (
            <div style={{ padding: '6px 14px', borderRadius: 20, background: '#fef3c7', color: '#92400e', fontSize: 12, fontWeight: 500 }}>
              ◉ Running…
            </div>
          )}
          {status === 'done' && (
            <div style={{ padding: '6px 14px', borderRadius: 20, background: '#f0fdf4', color: '#15803d', fontSize: 12, fontWeight: 500 }}>
              ✓ Complete
            </div>
          )}
        </div>
      )}

      {/* Error banner */}
      {status === 'error' && (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 10, padding: 16, marginBottom: 20 }}>
          <div style={{ fontWeight: 600, color: '#b91c1c', marginBottom: 4 }}>Pipeline Error</div>
          <div style={{ fontSize: 13, color: '#7f1d1d' }}>{error}</div>
          <button
            onClick={reset}
            style={{ marginTop: 12, padding: '6px 16px', borderRadius: 8, border: '1px solid #fca5a5', background: '#fff', fontSize: 12, cursor: 'pointer', color: '#b91c1c' }}
          >
            Try Again
          </button>
        </div>
      )}

      {/* Live log — shown while running */}
      {status === 'running' && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 8, fontWeight: 500 }}>Live Log</div>
          <LiveLog events={events} />
        </div>
      )}

      {/* Results — shown when done */}
      {status === 'done' && result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* Final verdict */}
          <div style={{
            padding:      '12px 16px',
            borderRadius: 10,
            background:   result.final_verdict === 'PASS' ? '#f0fdf4' : '#fffbeb',
            border:       `1px solid ${result.final_verdict === 'PASS' ? '#86efac' : '#fde68a'}`,
            display:      'flex',
            gap:          12,
            alignItems:   'center',
          }}>
            <span style={{ fontSize: 20 }}>{result.final_verdict === 'PASS' ? '✓' : '⚠'}</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: result.final_verdict === 'PASS' ? '#15803d' : '#92400e' }}>
                {result.final_verdict === 'PASS' ? 'Research passed quality review' : 'Research requires human review'}
              </div>
              <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                Confidence {confPct}
                {result.papers?.length > 0 ? ` · ${result.papers.length} papers` : ' · no papers found'}
                {result.round_num > 0 ? ` · ${result.round_num} review round(s)` : ''}
              </div>
            </div>
          </div>

          {/* Outstanding issues */}
          <OutstandingIssues
            issues={result.critic_feedback || []}
            onFixAll={handleFixAll}
            fixing={thesisChat.streaming}
          />

          {/* Research draft */}
          {result.draft && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', margin: 0 }}>Research Draft</h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <DownloadBtn label="TXT"  onClick={downloadTxt} />
                  <DownloadBtn label="JSON" onClick={downloadJson} />
                </div>
              </div>
              <div style={{
                background:   '#fafaf8',
                border:       '1px solid #e5e7eb',
                borderRadius: 10,
                padding:      20,
                maxHeight:    360,
                overflowY:    'auto',
                fontSize:     13,
                lineHeight:   1.75,
                color:        '#1a1a1a',
                whiteSpace:   'pre-wrap',
                wordBreak:    'break-word',
              }}>
                {result.draft}
              </div>
            </div>
          )}

          {/* Source papers */}
          {result.papers?.length > 0 && (
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', marginBottom: 10 }}>
                Source Papers ({result.papers.length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {result.papers.map((p, i) => (
                  <div key={i} style={{
                    padding:      '10px 14px',
                    background:   '#f9fafb',
                    borderRadius: 8,
                    border:       '1px solid #f3f4f6',
                    fontSize:     12,
                  }}>
                    <div style={{ fontWeight: 600, color: '#1a1a1a', marginBottom: 2 }}>{p.title}</div>
                    <div style={{ color: '#6b7280' }}>
                      {p.authors} · {p.year} · <span style={{ color: '#9ca3af' }}>{p.source}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Thesis chat */}
          <div ref={chatSectionRef} style={{ borderTop: '1px solid #e5e7eb', paddingTop: 28 }}>
            <ThesisChat researchResult={result} chatHook={thesisChat} />
          </div>
        </div>
      )}
    </div>
  )
}
