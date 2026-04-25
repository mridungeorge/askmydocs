import { useState } from 'react'
import { useChat, useAuth } from './hooks/useChat'
import Sidebar   from './components/Sidebar'
import Chat      from './components/Chat'
import Input     from './components/Input'
import AuthPage  from './components/AuthPage'
import './index.css'

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const {
    user, loading: authLoading,
    signInWithGoogle, signInWithEmail,
    signUpWithEmail, signInWithPhone,
    verifyOtp, signOut,
  } = useAuth()

  const {
    messages, loading, streamingText, allSources, scope, ingested, status, summaries,
    setScope, ingestUrl, ingestPdf, sendMessage, stopStreaming, clearAll,
  } = useChat()

  // Show loading spinner while checking auth
  if (authLoading) {
    return (
      <div style={{
        minHeight: '100vh',
        background: '#fafaf8',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: "'Noto Serif', serif",
        fontSize: 13,
        color: '#aaa',
        fontStyle: 'italic',
        letterSpacing: '0.05em',
      }}>
        loading…
      </div>
    )
  }

  // Show auth page if not logged in
  if (!user) {
    return (
      <AuthPage
        onSignInGoogle={signInWithGoogle}
        onSignInEmail={signInWithEmail}
        onSignUp={signUpWithEmail}
        onSignInPhone={signInWithPhone}
        onVerifyOtp={verifyOtp}
      />
    )
  }

  // Main app
  return (
    <div className="app">
      {/* Mobile menu button */}
      <button
        className="mobile-menu-btn"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle menu"
      >
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {sidebarOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      {/* Sidebar overlay (mobile) */}
      <div
        className={`sidebar-overlay ${sidebarOpen ? 'active' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      <div className={`sidebar ${sidebarOpen ? 'active' : ''}`}>
        <Sidebar
          ingested={ingested}
          allSources={allSources}
          scope={scope}
          status={status}
          user={user}
          summaries={summaries}
          onCloseSidebar={() => setSidebarOpen(false)}
          onIngestUrl={(url) => {
            ingestUrl(url)
            setSidebarOpen(false)
          }}
          onIngestPdf={(file, useMultimodal) => {
            ingestPdf(file, useMultimodal)
            setSidebarOpen(false)
          }}
          onScopeChange={(newScope) => {
            setScope(newScope)
            setSidebarOpen(false)
          }}
          onClear={() => {
            clearAll()
            setSidebarOpen(false)
          }}
          onSignOut={() => {
            signOut()
            setSidebarOpen(false)
          }}
        />
      </div>

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
                Welcome, {user.email?.split('@')[0]}.<br />
                Load any PDF or public URL from the sidebar.
              </div>
              <div className="hero-pipeline">
                <strong>HyDE</strong>
                <span className="sep">·</span>
                <strong>Hybrid search</strong>
                <span className="sep">·</span>
                <strong>Reranking</strong>
                <span className="sep">·</span>
                <strong>LangGraph routing</strong>
              </div>
            </div>
            <div className="empty">
              <div className="empty-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
                  <polyline points="13 2 13 9 20 9" />
                </svg>
              </div>
              <div className="empty-text">No document loaded.</div>
              <div className="empty-actions">
                <p style={{fontSize: '12px', color: '#888', lineHeight: '1.6', margin: 0}}>
                  ↓ Use the sidebar on the left (or the menu button) to load a PDF or URL
                </p>
                <button 
                  className="empty-btn empty-btn-primary empty-btn-mobile"
                  onClick={() => setSidebarOpen(true)}
                  title="Open sidebar menu to load a document"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor" strokeWidth="0">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z" />
                  </svg>
                  Open sidebar menu
                </button>
              </div>
            </div>
          </>
        ) : (
          <>
            <Chat messages={messages} loading={loading} streamingText={streamingText} />
            <Input onSend={sendMessage} onStop={stopStreaming} disabled={loading && !streamingText} isStreaming={loading && streamingText} />
          </>
        )}
      </main>
    </div>
  )
}
