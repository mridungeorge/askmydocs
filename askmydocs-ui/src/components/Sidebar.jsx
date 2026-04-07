import { useState, useRef } from 'react'

export default function Sidebar({
  ingested, allSources, scope, status,
  onIngestUrl, onIngestPdf, onScopeChange, onClear,
}) {
  const [activeTab, setActiveTab] = useState('url')
  const [url, setUrl]             = useState('')
  const [fileName, setFileName]   = useState('')
  const [file, setFile]           = useState(null)
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
    onIngestPdf(file)
    setFile(null)
    setFileName('')
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-mark">Document</div>
      <div className="section-label">Load source</div>

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'url' ? 'active' : ''}`}
          onClick={() => setActiveTab('url')}
        >URL</button>
        <button
          className={`tab ${activeTab === 'pdf' ? 'active' : ''}`}
          onClick={() => setActiveTab('pdf')}
        >PDF</button>
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
          <button
            className="btn-primary"
            onClick={handleUrlSubmit}
            disabled={!url.trim() || status?.type === 'loading'}
          >
            Index URL
          </button>
        </>
      )}

      {activeTab === 'pdf' && (
        <>
          <div
            className="file-drop"
            onClick={() => fileRef.current?.click()}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
            />
            <div className="file-drop-label">
              {fileName ? '' : 'click to select PDF'}
            </div>
            {fileName && (
              <div className="file-name">{fileName}</div>
            )}
          </div>
          <button
            className="btn-primary"
            onClick={handlePdfSubmit}
            disabled={!file || status?.type === 'loading'}
          >
            Index PDF
          </button>
        </>
      )}

      {status && (
        <div className={`status ${status.type}`}>
          {status.text}
        </div>
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
            <div className="badge"><span className="badge-dot" />HyDE active</div>
            <div className="badge"><span className="badge-dot" />Hybrid search active</div>
            <div className="badge"><span className="badge-dot" />Conversation memory</div>
          </div>

          <button className="btn-ghost" onClick={onClear}>
            Clear all
          </button>
        </>
      )}

      <div className="sidebar-footer">AskMyDocs · 2026</div>
    </aside>
  )
}
