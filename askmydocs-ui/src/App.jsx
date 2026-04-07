import Sidebar from './components/Sidebar'
import Chat    from './components/Chat'
import Input   from './components/Input'
import { useChat } from './hooks/useChat'
import './index.css'

export default function App() {
  const {
    messages, loading, allSources, scope, ingested, status,
    setScope, ingestUrl, ingestPdf, sendMessage, clearAll,
  } = useChat()

  return (
    <div className="app">
      <Sidebar
        ingested={ingested}
        allSources={allSources}
        scope={scope}
        status={status}
        onIngestUrl={ingestUrl}
        onIngestPdf={ingestPdf}
        onScopeChange={setScope}
        onClear={clearAll}
      />

      <main className="main">
        {!ingested ? (
          <>
            <div className="hero">
              <div className="hero-eyebrow">RAG · Document Intelligence</div>
              <div className="hero-title">
                Ask anything.<br />
                <em>Get cited answers.</em>
              </div>
              <div className="hero-sub">
                Load any PDF or public URL from the sidebar.<br />
                Ask questions. Every answer is cited.
              </div>
              <div className="hero-pipeline">
                <strong>HyDE</strong>
                <span className="sep">·</span>
                <strong>Hybrid search</strong>
                <span className="sep">·</span>
                <strong>Reranking</strong>
                <span className="sep">·</span>
                <strong>Conversation memory</strong>
              </div>
            </div>
            <div className="empty">
              <div className="empty-mark" />
              <div className="empty-text">No document loaded.</div>
              <div className="empty-hint">← load a source to begin</div>
            </div>
          </>
        ) : (
          <>
            <Chat messages={messages} loading={loading} />
            <Input onSend={sendMessage} disabled={loading} />
          </>
        )}
      </main>
    </div>
  )
}
