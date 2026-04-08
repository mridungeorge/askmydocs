import streamlit as st
from backend.ingest import ingest, extract_from_url, extract_from_pdf
from backend.retrieval import retrieve
from backend.generation import answer
from backend.logger import log_query

st.set_page_config(
    page_title="AskMyDocs",
    page_icon="◻",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wght@0,300;0,400;1,300&family=Noto+Sans+JP:wght@300;400&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background: #fafaf8 !important;
    color: #1a1a1a !important;
}
[data-testid="stAppViewContainer"] {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-weight: 300 !important;
}

#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }

[data-testid="stSidebar"] {
    background: #f2f2ee !important;
    border-right: 1px solid #d8d8d2 !important;
    min-width: 300px !important;
    max-width: 320px !important;
}
[data-testid="stSidebar"] > div {
    padding: 40px 28px !important;
}

.sidebar-mark {
    font-family: 'Noto Serif', serif;
    font-size: 11px;
    font-weight: 300;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 32px;
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

.section-label {
    font-family: 'Noto Serif', serif;
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #aaa;
    margin-bottom: 12px;
}

.retrieval-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.1em;
    color: #888;
    padding: 4px 0;
}
.badge-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #1a1a1a;
}

[data-testid="stTabs"] [role="tablist"] {
    gap: 0 !important;
    border-bottom: 1px solid #d8d8d2 !important;
    margin-bottom: 20px !important;
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

[data-testid="stTextInput"] input {
    background: #fafaf8 !important;
    border: 1px solid #d8d8d2 !important;
    border-radius: 0 !important;
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 13px !important;
    font-weight: 300 !important;
    color: #1a1a1a !important;
    padding: 10px 12px !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #1a1a1a !important;
    box-shadow: none !important;
}

[data-testid="stButton"] > button {
    background: #1a1a1a !important;
    color: #fafaf8 !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 0 !important;
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 11px !important;
    font-weight: 400 !important;
    letter-spacing: 0.2em !important;
    text-transform: uppercase !important;
    padding: 10px 20px !important;
    width: 100% !important;
    margin-top: 8px !important;
    transition: all 0.15s !important;
}
[data-testid="stButton"] > button:hover {
    background: #fafaf8 !important;
    color: #1a1a1a !important;
}
[data-testid="stButton"] > button:disabled {
    background: #e8e8e4 !important;
    color: #bbb !important;
    border-color: #e8e8e4 !important;
}

[data-testid="stFileUploader"] {
    border: 1px dashed #d8d8d2 !important;
    border-radius: 0 !important;
    padding: 12px !important;
    background: #fafaf8 !important;
}

hr {
    border: none !important;
    border-top: 1px solid #d8d8d2 !important;
    margin: 24px 0 !important;
}

[data-testid="stSelectbox"] > div > div {
    border-radius: 0 !important;
    border: 1px solid #d8d8d2 !important;
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 12px !important;
    font-weight: 300 !important;
    background: #fafaf8 !important;
}

.block-container { padding: 0 !important; max-width: 100% !important; }

.hero {
    padding: 72px 72px 52px;
    border-bottom: 1px solid #d8d8d2;
}
.hero-eyebrow {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.4em;
    text-transform: uppercase;
    color: #aaa;
    margin-bottom: 20px;
}
.hero-title {
    font-family: 'Noto Serif', serif;
    font-size: 48px;
    font-weight: 300;
    line-height: 1.15;
    color: #1a1a1a;
    margin-bottom: 16px;
    letter-spacing: -0.02em;
}
.hero-title em { font-style: italic; color: #555; }
.hero-sub {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 13px;
    font-weight: 300;
    color: #888;
    letter-spacing: 0.05em;
    line-height: 1.8;
}
.hero-pipeline {
    margin-top: 28px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.15em;
    color: #bbb;
    text-transform: uppercase;
}
.hero-pipeline span { color: #1a1a1a; font-weight: 400; }
.hero-pipeline .sep { color: #ddd; }

.empty-state {
    padding: 80px 72px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.empty-mark {
    width: 32px;
    height: 1px;
    background: #d8d8d2;
    margin-bottom: 4px;
}
.empty-text {
    font-family: 'Noto Serif', serif;
    font-size: 17px;
    font-weight: 300;
    color: #aaa;
    font-style: italic;
}
.empty-hint {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 11px;
    font-weight: 300;
    color: #ccc;
    letter-spacing: 0.1em;
}

.chat-area { padding: 40px 72px; max-width: 820px; }

[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin-bottom: 32px !important;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 14px !important;
    font-weight: 300 !important;
    line-height: 1.9 !important;
    color: #1a1a1a !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #f2f2ee !important;
    padding: 18px 24px !important;
    border-left: 2px solid #1a1a1a !important;
}

[data-testid="stExpander"] {
    border: 1px solid #e8e8e4 !important;
    border-radius: 0 !important;
    background: #fafaf8 !important;
    margin-top: 8px !important;
}
[data-testid="stExpander"] summary {
    font-family: 'Noto Sans JP', sans-serif !important;
    font-size: 10px !important;
    font-weight: 300 !important;
    letter-spacing: 0.25em !important;
    text-transform: uppercase !important;
    color: #aaa !important;
    padding: 10px 14px !important;
}
[data-testid="stExpander"] summary:hover { color: #1a1a1a !important; }

[data-testid="stChatInput"] {
    border-top: 1px solid #d8d8d2 !important;
    background: #fafaf8 !important;
    padding: 16px 72px !important;
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
}
[data-testid="stChatInput"] textarea:focus {
    border-bottom-color: #1a1a1a !important;
    box-shadow: none !important;
}
[data-testid="stChatInput"] button {
    background: #1a1a1a !important;
    border-radius: 0 !important;
}

.doc-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 11px;
    font-weight: 300;
    color: #555;
    padding: 6px 0;
    border-bottom: 1px solid #e8e8e4;
    letter-spacing: 0.03em;
}
.doc-pill::before {
    content: '';
    width: 4px;
    height: 4px;
    background: #1a1a1a;
    border-radius: 50%;
    flex-shrink: 0;
}

.source-card {
    padding: 10px 0;
    border-bottom: 1px solid #f0f0ec;
}
.source-title {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 11px;
    font-weight: 400;
    color: #333;
    letter-spacing: 0.04em;
    margin-bottom: 3px;
    display: flex;
    justify-content: space-between;
}
.source-score {
    font-family: 'Noto Serif', serif;
    font-size: 10px;
    font-style: italic;
    color: #aaa;
}
.source-snippet {
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 11px;
    font-weight: 300;
    color: #888;
    line-height: 1.7;
}

::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d8d8d2; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "messages":      [],
    "source_name":   None,
    "ingested":      False,
    "all_sources":   [],
    "source_filter": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-mark">Document</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Load source</div>', unsafe_allow_html=True)

    tab_url, tab_pdf = st.tabs(["URL", "PDF"])

    with tab_url:
        url = st.text_input("URL", placeholder="https://...", label_visibility="collapsed")
        if st.button("Index URL", disabled=not url, key="btn_url"):
            with st.spinner("fetching · chunking · embedding"):
                try:
                    title, text = extract_from_url(url)
                    n = ingest(title, "url", text)
                    st.session_state.source_name = title
                    st.session_state.ingested = True
                    st.session_state.messages = []
                    if title not in st.session_state.all_sources:
                        st.session_state.all_sources.append(title)
                    st.success(f"{n} chunks indexed")
                except Exception as e:
                    st.error(str(e))

    with tab_pdf:
        pdf = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
        if st.button("Index PDF", disabled=not pdf, key="btn_pdf"):
            with st.spinner("reading · chunking · embedding"):
                try:
                    title, text = extract_from_pdf(pdf.read(), pdf.name)
                    n = ingest(title, "pdf", text)
                    st.session_state.source_name = title
                    st.session_state.ingested = True
                    st.session_state.messages = []
                    if title not in st.session_state.all_sources:
                        st.session_state.all_sources.append(title)
                    st.success(f"{n} chunks indexed")
                except Exception as e:
                    st.error(str(e))

    if st.session_state.ingested:
        st.markdown("---")
        st.markdown('<div class="section-label">Loaded</div>', unsafe_allow_html=True)
        for doc in st.session_state.all_sources:
            short = doc[:34] + "…" if len(doc) > 34 else doc
            st.markdown(f'<div class="doc-pill">{short}</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">Scope</div>', unsafe_allow_html=True)
        selected = st.selectbox(
            "Scope",
            ["All documents"] + st.session_state.all_sources,
            label_visibility="collapsed",
        )
        st.session_state.source_filter = None if selected == "All documents" else selected

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="badge-row">
            <div class="badge"><span class="badge-dot"></span>HyDE active</div>
            <div class="badge"><span class="badge-dot"></span>Hybrid search active</div>
            <div class="badge"><span class="badge-dot"></span>LLM routing active</div>
            <div class="badge"><span class="badge-dot"></span>Conversation memory</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Clear all", key="btn_clear"):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()

    st.markdown("<br>" * 3, unsafe_allow_html=True)
    st.markdown(
        '<div style="font-family:\'Noto Serif\',serif;font-size:10px;'
        'color:#ccc;letter-spacing:0.2em;font-style:italic;">AskMyDocs · 2026</div>',
        unsafe_allow_html=True,
    )

# ── Main ──────────────────────────────────────────────────────────────────────
if not st.session_state.ingested:
    st.markdown("""
    <div class="hero">
        <div class="hero-eyebrow">RAG · Document Intelligence</div>
        <div class="hero-title">Ask anything.<br><em>Get cited answers.</em></div>
        <div class="hero-sub">
            Load any PDF or public URL from the sidebar.<br>
            Ask questions. Every answer is cited.
        </div>
        <div class="hero-pipeline">
            <span>HyDE</span>
            <span class="sep">·</span>
            <span>Hybrid search</span>
            <span class="sep">·</span>
            <span>Reranking</span>
            <span class="sep">·</span>
            <span>LLM routing</span>
        </div>
    </div>
    <div class="empty-state">
        <div class="empty-mark"></div>
        <div class="empty-text">No document loaded.</div>
        <div class="empty-hint">← load a source to begin</div>
    </div>
    """, unsafe_allow_html=True)

else:
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
                            f'<div class="source-title">[{i+1}] {s["name"]}'
                            f'<span class="source-score">{score_txt}</span></div>'
                            f'<div class="source-snippet">{s["snippet"]}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
            if msg.get("routing"):
                r = msg["routing"]
                model_short = "70B" if "70b" in r.get("model","") else "8B"
                st.caption(f"Model: {model_short} · complexity: {r.get('score', 0):.2f}")

    st.markdown("</div>", unsafe_allow_html=True)

    query = st.chat_input("Ask a question…")
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("thinking · retrieving · generating"):
                scope = st.session_state.source_filter or st.session_state.source_name
                # Pass full history for conversation memory
                history = st.session_state.messages[:-1]  # exclude current question
                chunks = retrieve(query, scope, history=history)
                result = answer(query, chunks, history=history)
                if len(result) == 3:
                    response, srcs, routing = result
                else:
                    response, srcs = result
                    routing = {}

            st.markdown(response)
            if srcs:
                with st.expander("Sources"):
                    for i, s in enumerate(srcs):
                        score_txt = f"{s['score']}% match" if s.get("score") else ""
                        st.markdown(
                            f'<div class="source-card">'
                            f'<div class="source-title">[{i+1}] {s["name"]}'
                            f'<span class="source-score">{score_txt}</span></div>'
                            f'<div class="source-snippet">{s["snippet"]}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

            if routing:
                model_short = "70B" if "70b" in routing.get("model","") else "8B"
                st.caption(f"Model: {model_short} · complexity: {routing.get('score',0):.2f}")

            log_query(query, scope, len(chunks), len(response))

        st.session_state.messages.append({
            "role":    "assistant",
            "content": response,
            "sources": srcs,
            "routing": routing,
        })