import { useState, useRef } from 'react'

export default function Sidebar({
  ingested, allSources, scope, status,
  onIngestUrl, onIngestPdf, onScopeChange, onClear,
}) {
  const [activeTab, setActiveTab] = useState('url')
  const [url, setUrl]             = useState('')
  const [files, setFiles]         = useState([])
  const fileRef                   = useRef()

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files)
    if (selectedFiles.length > 0) {
      setFiles(selectedFiles)
    }
  }

  const handleUrlSubmit = () => {
    if (!url.trim()) return
    onIngestUrl(url.trim())
    setUrl('')
  }

  const handlePdfSubmit = () => {
    if (files.length === 0) return
    onIngestPdf(files)
    setFiles([])
    fileRef.current.value = ''
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
              multiple
              onChange={handleFileChange}
            />
            <div className="file-drop-label">
              {files.length === 0 ? 'click to select PDFs' : `${files.length} file${files.length > 1 ? 's' : ''} selected`}
            </div>
            {files.length > 0 && (
              <div className="file-list">
                {files.map((f, i) => (
                  <div key={i} className="file-name">{f.name}</div>
                ))}
              </div>
            )}
          </div>
          <button
            className="btn-primary"
            onClick={handlePdfSubmit}
            disabled={files.length === 0 || status?.type === 'loading'}
          >
            Index {files.length > 0 ? `${files.length} PDF${files.length > 1 ? 's' : ''}` : 'PDFs'}
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
