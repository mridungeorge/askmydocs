import streamlit as st
from backend.ingest import ingest, extract_from_url, extract_from_pdf
from backend.retrieval import retrieve
from backend.generation import answer
from backend.logger import log_query

st.set_page_config(
    page_title="AskMyDocs",
    page_icon="◻",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wght@0,300;0,400;1,300&family=Noto+Sans+JP:wght@300;400&display=swap');

/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; }

/* ── Root ── */
html, body, [data-testid="stAppViewContainer"] {
    background: #fafaf8 !important;
    color: #1a1a1a !important;
}

[data-testid="stAppViewContainer"] {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-weight: 300 !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #f2f2ee !important;
    border-right: 1px solid #d8d8d2 !important;
    width: 320px !important;
}

[data-testid="stSidebar"] > div {
    padding: 48px 32px !important;
}

/* ── Sidebar header mark ── */
.sidebar-mark {
    font-family: 'Noto Serif', serif;
    font-size: 11px;
    font-weight: 300;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 40px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.sidebar-mark::before {
    content: '';
    display: block;
    width: 20px;
    height: 1px;
    background: #888;
}

/* ── Section labels ── */
.section-label {
    font-family: 'Noto Serif', serif;
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #aaa;
    margin-bottom: 16px;
}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] {
    gap: 0 !important;
    border-bottom: 1px solid #d8d8d2 !important;
    margin-bottom: 24px !important;
}

[data-testid="stTabs"] [role="tab"] {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 11px !important;
    font-weight: 300 !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    color: #aaa !important;
    padding: 8px 16px 8px 0 !important;
    border: none !important;
    background: transparent !important;
}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #1a1a1a !important;
    border-bottom: 1px solid #1a1a1a !important;
}

/* ── Input fields ── */
[data-testid="stTextInput"] input,
[data-testid="stFileUploader"] {
    background: #fafaf8 !important;
    border: 1px solid #d8d8d2 !important;
    border-radius: 0 !important;
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 13px !important;
    font-weight: 300 !important;
    color: #1a1a1a !important;
    padding: 10px 14px !important;
}

[data-testid="stTextInput"] input:focus {
    border-color: #1a1a1a !important;
    box-shadow: none !important;
}

/* ── Buttons ── */
[data-testid="stButton"] button {
    background: #1a1a1a !important;
    color: #fafaf8 !important;
    border: none !important;
    border-radius: 0 !important;
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 11px !important;
    font-weight: 300 !important;
    letter-spacing: 0.2em !important;
    text-transform: uppercase !important;
    padding: 10px 20px !important;
    width: 100% !important;
    transition: background 0.2s !important;
}

[data-testid="stButton"] button:hover {
    background: #333 !important;
}

[data-testid="stButton"] button:disabled {
    background: #ccc !important;
    color: #888 !important;
}

/* ── Success / error ── */
[data-testid="stAlert"] {
    border-radius: 0 !important;
    border: none !important;
    border-left: 2px solid currentColor !important;
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 12px !important;
    font-weight: 300 !important;
}

/* ── Selectbox ── */
[data-testid="stSelectbox"] select,
[data-testid="stSelectbox"] > div > div {
    border-radius: 0 !important;
    border: 1px solid #d8d8d2 !important;
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 12px !important;
    font-weight: 300 !important;
    background: #fafaf8 !important;
}

/* ── Divider ── */
hr {
    border: none !important;
    border-top: 1px solid #d8d8d2 !important;
    margin: 32px 0 !important;
}

/* ── Main content area ── */
[data-testid="stMain"] {
    padding: 0 !important;
}

.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

/* ── Hero ── */
.hero {
    padding: 80px 80px 60px;
    border-bottom: 1px solid #d8d8d2;
}

.hero-eyebrow {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.4em;
    text-transform: uppercase;
    color: #aaa;
    margin-bottom: 24px;
}

.hero-title {
    font-family: 'Noto Serif', serif;
    font-size: 52px;
    font-weight: 300;
    line-height: 1.1;
    color: #1a1a1a;
    margin-bottom: 20px;
    letter-spacing: -0.02em;
}

.hero-title em {
    font-style: italic;
    color: #555;
}

.hero-sub {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 13px;
    font-weight: 300;
    color: #888;
    letter-spacing: 0.05em;
    line-height: 1.8;
}

/* ── Empty state ── */
.empty-state {
    padding: 120px 80px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
}

.empty-mark {
    width: 40px;
    height: 1px;
    background: #d8d8d2;
    margin-bottom: 8px;
}

.empty-text {
    font-family: 'Noto Serif', serif;
    font-size: 18px;
    font-weight: 300;
    color: #aaa;
    font-style: italic;
}

.empty-hint {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 11px;
    font-weight: 300;
    color: #bbb;
    letter-spacing: 0.1em;
}

/* ── Chat area ── */
.chat-area {
    padding: 48px 80px;
    max-width: 860px;
}

/* ── Messages ── */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin-bottom: 40px !important;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 14px !important;
    font-weight: 300 !important;
    line-height: 1.9 !important;
    color: #1a1a1a !important;
}

/* User message bubble */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #f2f2ee !important;
    padding: 20px 28px !important;
    border-left: 2px solid #1a1a1a !important;
}

/* ── Expander (sources) ── */
[data-testid="stExpander"] {
    border: 1px solid #e8e8e4 !important;
    border-radius: 0 !important;
    background: #fafaf8 !important;
}

[data-testid="stExpander"] summary {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 10px !important;
    font-weight: 300 !important;
    letter-spacing: 0.25em !important;
    text-transform: uppercase !important;
    color: #aaa !important;
    padding: 12px 16px !important;
}

[data-testid="stExpander"] summary:hover {
    color: #1a1a1a !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] {
    border-top: 1px solid #d8d8d2 !important;
    background: #fafaf8 !important;
    padding: 20px 80px !important;
}

[data-testid="stChatInput"] textarea {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 14px !important;
    font-weight: 300 !important;
    border: none !important;
    border-bottom: 1px solid #d8d8d2 !important;
    border-radius: 0 !important;
    background: transparent !important;
    color: #1a1a1a !important;
    resize: none !important;
    padding: 0 !important;
}

[data-testid="stChatInput"] textarea:focus {
    border-bottom-color: #1a1a1a !important;
    box-shadow: none !important;
}

[data-testid="stChatInput"] button {
    background: #1a1a1a !important;
    border-radius: 0 !important;
    color: #fafaf8 !important;
}

/* ── Doc pill ── */
.doc-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 11px;
    font-weight: 300;
    color: #555;
    padding: 6px 0;
    border-bottom: 1px solid #e8e8e4;
    width: 100%;
    letter-spacing: 0.05em;
}

.doc-pill::before {
    content: '';
    width: 4px;
    height: 4px;
    background: #1a1a1a;
    border-radius: 50%;
    flex-shrink: 0;
}

/* ── Source card ── */
.source-card {
    padding: 12px 0;
    border-bottom: 1px solid #e8e8e4;
}

.source-title {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 11px;
    font-weight: 400;
    color: #333;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}

.source-score {
    font-family: 'Noto Serif', serif;
    font-size: 10px;
    font-style: italic;
    color: #aaa;
    float: right;
}

.source-snippet {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 11px;
    font-weight: 300;
    color: #888;
    line-height: 1.7;
}

/* ── Spinner ── */
[data-testid="stSpinner"] {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 12px !important;
    font-weight: 300 !important;
    color: #aaa !important;
    letter-spacing: 0.1em !important;
}

/* ── Caption ── */
[data-testid="stCaptionContainer"] p {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 11px !important;
    font-weight: 300 !important;
    color: #888 !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d8d8d2; }
::-webkit-scrollbar-thumb:hover { background: #aaa; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border: 1px dashed #d8d8d2 !important;
    border-radius: 0 !important;
    padding: 16px !important;
}

[data-testid="stFileUploader"] label {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 12px !important;
    font-weight: 300 !important;
}

/* ── Column buttons (toggle, delete, etc) ── */
[data-testid="stButton"] button[kind="secondary"] {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 14px !important;
    font-weight: 300 !important;
    border: 1px solid #d8d8d2 !important;
    background: #fafaf8 !important;
    color: #1a1a1a !important;
}

[data-testid="stButton"] button[kind="secondary"]:hover {
    background: #f2f2ee !important;
}

/* ── Columns layout ── */
[data-testid="stColumn"] {
    gap: 0 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages"      not in st.session_state: st.session_state.messages      = []
if "source_name"   not in st.session_state: st.session_state.source_name   = None
if "ingested"      not in st.session_state: st.session_state.ingested      = False
if "all_sources"   not in st.session_state: st.session_state.all_sources   = []
if "source_filter" not in st.session_state: st.session_state.source_filter = None
if "show_upload"   not in st.session_state: st.session_state.show_upload   = True
if "show_logs"     not in st.session_state: st.session_state.show_logs     = False

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-mark">Document</div>', unsafe_allow_html=True)
    
    # ── Upload section (always accessible) ──
    col1, col2 = st.columns([1, 4])
    with col1:
        toggle = "−" if st.session_state.show_upload else "+"
        if st.button(toggle, key="upload_toggle", use_container_width=True):
            st.session_state.show_upload = not st.session_state.show_upload
            st.rerun()
    with col2:
        st.markdown('<div class="section-label">Add Source</div>', unsafe_allow_html=True)
    
    if st.session_state.show_upload:
        tab_url, tab_pdf = st.tabs(["URL", "PDF"])

        with tab_url:
            url = st.text_input(
                "URL",
                placeholder="https://...",
                label_visibility="collapsed"
            )
            if st.button("Index URL", disabled=not url):
                with st.spinner("fetching · chunking · embedding"):
                    try:
                        title, text = extract_from_url(url)
                        n = ingest(title, "url", text)
                        st.session_state.source_name = title
                        st.session_state.ingested    = True
                        st.session_state.messages    = []
                        if title not in st.session_state.all_sources:
                            st.session_state.all_sources.append(title)
                        st.success(f"{n} chunks indexed")
                    except Exception as e:
                        st.error(str(e))

        with tab_pdf:
            pdf = st.file_uploader(
                "PDF",
                type=["pdf"],
                label_visibility="collapsed"
            )
            if st.button("Index PDF", disabled=not pdf):
                with st.spinner("reading · chunking · embedding"):
                    try:
                        title, text = extract_from_pdf(pdf.read(), pdf.name)
                        n = ingest(title, "pdf", text)
                        st.session_state.source_name = title
                        st.session_state.ingested    = True
                        st.session_state.messages    = []
                        if title not in st.session_state.all_sources:
                            st.session_state.all_sources.append(title)
                        st.success(f"{n} chunks indexed")
                    except Exception as e:
                        st.error(str(e))

    # ── Loaded documents section ──
    if st.session_state.ingested:
        st.markdown("---")
        st.markdown('<div class="section-label">Loaded</div>', unsafe_allow_html=True)

        for doc in st.session_state.all_sources:
            short = doc[:36] + "…" if len(doc) > 36 else doc
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f'<div class="doc-pill">{short}</div>', unsafe_allow_html=True)
            with col2:
                if st.button("×", key=f"del_{doc}", use_container_width=True):
                    st.session_state.all_sources.remove(doc)
                    if doc == st.session_state.source_name:
                        st.session_state.source_name = None
                        if st.session_state.all_sources:
                            st.session_state.source_name = st.session_state.all_sources[0]
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">Scope</div>', unsafe_allow_html=True)

        selected = st.selectbox(
            "Scope",
            ["All documents"] + st.session_state.all_sources,
            label_visibility="collapsed"
        )
        st.session_state.source_filter = (
            None if selected == "All documents" else selected
        )

        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear all", use_container_width=True):
                st.session_state.messages    = []
                st.session_state.source_name = None
                st.session_state.ingested    = False
                st.session_state.all_sources = []
                st.session_state.show_upload = True
                st.rerun()
        with col2:
            if st.button("Logs", use_container_width=True):
                st.session_state.show_logs = True

    # Footer
    st.markdown("<br>" * 4, unsafe_allow_html=True)
    st.markdown(
        '<div style="font-family:\'Noto Serif\',serif;font-size:10px;'
        'color:#ccc;letter-spacing:0.2em;font-style:italic;">'
        'AskMyDocs · 2026</div>',
        unsafe_allow_html=True
    )

# ── Main ──────────────────────────────────────────────────────────────────────
if not st.session_state.ingested:
    # Hero + empty state
    st.markdown("""
    <div class="hero">
        <div class="hero-eyebrow">RAG · Document Intelligence</div>
        <div class="hero-title">Ask anything.<br><em>Get cited answers.</em></div>
        <div class="hero-sub">
            Load a document from the sidebar —<br>
            PDF or any public URL.
        </div>
    </div>
    <div class="empty-state">
        <div class="empty-mark"></div>
        <div class="empty-text">No document loaded.</div>
        <div class="empty-hint">← load a source to begin</div>
    </div>
    """, unsafe_allow_html=True)

else:
    # Chat history
    st.markdown('<div class="chat-area">', unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("Sources"):
                    for i, s in enumerate(msg["sources"]):
                        score_txt = f"{s['score']}% match" if s.get("score") else ""
                        st.markdown(
                            f'<div class="source-card">'
                            f'<div class="source-title">'
                            f'[{i+1}] {s["name"]}'
                            f'<span class="source-score">{score_txt}</span>'
                            f'</div>'
                            f'<div class="source-snippet">{s["snippet"]}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

    st.markdown('</div>', unsafe_allow_html=True)

    # Input
    query = st.chat_input("Ask a question…")
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("retrieving · reranking · generating"):
                scope  = st.session_state.source_filter or st.session_state.source_name
                chunks = retrieve(query, scope)
                response, srcs = answer(query, chunks)

            st.markdown(response)

            if srcs:
                with st.expander("Sources"):
                    for i, s in enumerate(srcs):
                        score_txt = f"{s['score']}% match" if s.get("score") else ""
                        st.markdown(
                            f'<div class="source-card">'
                            f'<div class="source-title">'
                            f'[{i+1}] {s["name"]}'
                            f'<span class="source-score">{score_txt}</span>'
                            f'</div>'
                            f'<div class="source-snippet">{s["snippet"]}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

            log_query(query, scope, len(chunks), len(response))

        st.session_state.messages.append({
            "role":    "assistant",
            "content": response,
            "sources": srcs,
        })

# ── Logs modal ────────────────────────────────────────────────────────────────
if st.session_state.show_logs:
    st.markdown("---")
    st.markdown('<div class="section-label">Query Logs</div>', unsafe_allow_html=True)
    
    import json, os
    if os.path.exists("query_log.json"):
        with open("query_log.json") as f:
            logs = json.load(f)
        
        st.markdown(f"**Total queries:** {len(logs)}")
        
        if logs:
            # Show last 10 queries
            for log in reversed(logs[-10:]):
                timestamp = log.get("timestamp", "unknown")[:10]
                query = log.get("query", "")[:50]
                chunks = log.get("chunks_used", 0)
                st.caption(f"📅 {timestamp} | {query}... | {chunks} chunks")
            
            if st.button("Close Logs"):
                st.session_state.show_logs = False
                st.rerun()
    else:
        st.info("No queries logged yet.")