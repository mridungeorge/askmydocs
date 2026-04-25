import { useState, useRef } from 'react'

export default function Sidebar({
  ingested, allSources, scope, status, user, summaries,
  onIngestUrl, onIngestPdf, onScopeChange, onClear, onSignOut, onCloseSidebar,
}) {
  const [activeTab, setActiveTab] = useState('url')
  const [url, setUrl]             = useState('')
  const [fileName, setFileName]   = useState('')
  const [file, setFile]           = useState(null)
  const [useMultimodal, setUseMultimodal] = useState(true)
  const fileRef                   = useRef()

  const handleFileChange = (e) => {
    const f = e.target.files[0]
    if (f) { setFile(f); setFileName(f.name) }
  }

  const handleUrlSubmit = () => {
    if (!url.trim()) return
    onIngestUrl(url.trim())
    setUrl('')
  }

  const handlePdfSubmit = () => {
    if (!file) return
    onIngestPdf(file, useMultimodal)
    setFile(null)
    setFileName('')
  }

  return (
    <aside className="sidebar-inner">
      {/* Mobile close button */}
      <button
        className="sidebar-close-btn"
        onClick={onCloseSidebar}
        aria-label="Close sidebar"
      >
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* User info */}
      <div style={{
        marginBottom: 32,
        paddingBottom: 20,
        borderBottom: '1px solid #e8e8e4',
      }}>
        <div style={{
          fontSize: 11,
          fontWeight: 300,
          color: '#aaa',
          letterSpacing: '0.1em',
          marginBottom: 4,
        }}>
          {user?.email || 'User'}
        </div>
        <button
          onClick={onSignOut}
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: 10,
            fontFamily: "'Noto Sans JP', sans-serif",
            fontWeight: 300,
            color: '#ccc',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          Sign out
        </button>
      </div>

      <div className="sidebar-mark">Document</div>
      <div className="section-label">Load source</div>

      <div className="tabs">
        <button className={`tab ${activeTab === 'url' ? 'active' : ''}`} onClick={() => setActiveTab('url')}>URL</button>
        <button className={`tab ${activeTab === 'pdf' ? 'active' : ''}`} onClick={() => setActiveTab('pdf')}>PDF</button>
      </div>

      {activeTab === 'url' && (
        <>
          <input
            className="input-field"
            type="text"
            placeholder="https://..."
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleUrlSubmit()}
          />
          <button className="btn-primary" onClick={handleUrlSubmit} disabled={!url.trim() || status?.type === 'loading'}>
            {status?.type === 'loading' ? (
              <>
                <svg className="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 6v6l4 2" strokeLinecap="round" />
                </svg>
                Processing…
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V5h2v4h4v2z" />
                </svg>
                Index URL
              </>
            )}
          </button>
        </>
      )}

      {activeTab === 'pdf' && (
        <>
          <div className="file-drop" onClick={() => fileRef.current?.click()}>
            <input ref={fileRef} type="file" accept=".pdf" onChange={handleFileChange} />
            <div className="file-drop-icon">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
              </svg>
            </div>
            <div className="file-drop-label">{fileName ? 'PDF selected' : 'Click to select PDF'}</div>
            {fileName && <div className="file-name">{fileName}</div>}
          </div>

          {/* Multimodal toggle */}
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 11,
            color: '#aaa',
            margin: '12px 0 16px 0',
            cursor: 'pointer',
          }}>
            <input
              type="checkbox"
              checked={useMultimodal}
              onChange={e => setUseMultimodal(e.target.checked)}
              style={{ cursor: 'pointer' }}
            />
            Extract images & tables
          </label>

          <button className="btn-primary" onClick={handlePdfSubmit} disabled={!file || status?.type === 'loading'}>
            {status?.type === 'loading' ? (
              <>
                <svg className="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 6v6l4 2" strokeLinecap="round" />
                </svg>
                Processing…
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V5h2v4h4v2z" />
                </svg>
                Index PDF
              </>
            )}
          </button>
        </>
      )}

      {status && (
        <div className={`status ${status.type}`}>{status.text}</div>
      )}

      {ingested && (
        <>
          <hr className="divider" />
          <div className="section-label">Loaded</div>
          {allSources.map(doc => (
            <div key={doc} className="doc-pill">
              {doc.length > 34 ? doc.slice(0, 34) + '…' : doc}
            </div>
          ))}

          {/* Document Summaries */}
          {Object.keys(summaries).length > 0 && (
            <>
              <br />
              <div className="section-label">Summaries</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {Object.entries(summaries).map(([docTitle, summary]) => (
                  <div key={docTitle} style={{
                    padding: 8,
                    backgroundColor: '#f8f7f3',
                    borderRadius: 4,
                    fontSize: 10,
                    lineHeight: 1.5,
                    color: '#666',
                  }}>
                    <div style={{ fontWeight: 500, marginBottom: 4, color: '#333' }}>
                      {docTitle.length > 30 ? docTitle.slice(0, 30) + '…' : docTitle}
                    </div>
                    {summary}
                  </div>
                ))}
              </div>
            </>
          )}

          <br />
          <div className="section-label">Scope</div>
          <select
            className="scope-select"
            value={scope || ''}
            onChange={e => onScopeChange(e.target.value || null)}
          >
            <option value="">All documents</option>
            {allSources.map(doc => (
              <option key={doc} value={doc}>{doc}</option>
            ))}
          </select>

          <div className="badge-row">
            <div className="badge"><span className="badge-dot" />Multimodal active</div>
            <div className="badge"><span className="badge-dot" />Hybrid search active</div>
            <div className="badge"><span className="badge-dot" />LangGraph routing</div>
            <div className="badge"><span className="badge-dot" />Conversation memory</div>
          </div>

          <button className="btn-ghost" onClick={onClear}>Clear all</button>
        </>
      )}

      <div className="sidebar-footer">AskMyDocs · 2026</div>
    </aside>
  )
}
