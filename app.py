import streamlit as st
import os
from backend.ingest import ingest, extract_from_url, extract_from_pdf
from backend.cache import get_cached_answer, set_cached_answer, get_cache_stats
from backend.retrieval import embed_query
from backend.agents import run_agent
from backend.logger import log_query
from backend.guardrails import check_guardrails
from backend.summariser import get_summary

st.set_page_config(
    page_title="AskMyDocs",
    page_icon="Γù╗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wght@0,300;0,400;1,300&family=Noto+Sans+JP:wght@300;400;500&display=swap');
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, [data-testid="stAppViewContainer"] { background: #fafaf8 !important; color: #1a1a1a !important; }
[data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif !important; font-weight: 300 !important; }
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
[data-testid="stSidebar"] { background: #f2f2ee !important; border-right: 1px solid #d8d8d2 !important; min-width: 300px !important; max-width: 320px !important; }
[data-testid="stSidebar"] > div { padding: 40px 28px !important; }
.sidebar-mark { font-family: 'Noto Serif', serif; font-size: 11px; font-weight: 300; letter-spacing: 0.25em; text-transform: uppercase; color: #888; margin-bottom: 32px; display: flex; align-items: center; gap: 10px; }
.sidebar-mark::before { content: ''; display: block; width: 20px; height: 1px; background: #888; }
.section-label { font-family: 'Noto Serif', serif; font-size: 10px; font-weight: 300; letter-spacing: 0.3em; text-transform: uppercase; color: #aaa; margin-bottom: 12px; }
[data-testid="stTabs"] [role="tablist"] { gap: 0 !important; border-bottom: 1px solid #d8d8d2 !important; margin-bottom: 20px !important; }
[data-testid="stTabs"] [role="tab"] { font-family: 'Noto Sans JP', sans-serif !important; font-size: 11px !important; font-weight: 300 !important; letter-spacing: 0.15em !important; text-transform: uppercase !important; color: #aaa !important; padding: 8px 16px 8px 0 !important; border: none !important; background: transparent !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: #1a1a1a !important; border-bottom: 1px solid #1a1a1a !important; }
[data-testid="stTextInput"] input { background: #fafaf8 !important; border: 1px solid #d8d8d2 !important; border-radius: 0 !important; font-family: 'Noto Sans JP', sans-serif !important; font-size: 13px !important; font-weight: 300 !important; color: #1a1a1a !important; padding: 10px 12px !important; }
[data-testid="stButton"] > button { background: #1a1a1a !important; color: #fafaf8 !important; border: 1px solid #1a1a1a !important; border-radius: 0 !important; font-family: 'Noto Sans JP', sans-serif !important; font-size: 11px !important; font-weight: 400 !important; letter-spacing: 0.2em !important; text-transform: uppercase !important; padding: 10px 20px !important; width: 100% !important; margin-top: 8px !important; }
[data-testid="stButton"] > button:hover { background: #fafaf8 !important; color: #1a1a1a !important; }
[data-testid="stButton"] > button:disabled { background: #e8e8e4 !important; color: #bbb !important; border-color: #e8e8e4 !important; }
[data-testid="stFileUploader"] { border: 1px dashed #d8d8d2 !important; border-radius: 0 !important; padding: 12px !important; }
hr { border: none !important; border-top: 1px solid #d8d8d2 !important; margin: 24px 0 !important; }
[data-testid="stSelectbox"] > div > div { border-radius: 0 !important; border: 1px solid #d8d8d2 !important; font-family: 'Noto Sans JP', sans-serif !important; font-size: 12px !important; background: #fafaf8 !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }
.hero { padding: 72px 72px 52px; border-bottom: 1px solid #d8d8d2; }
.hero-eyebrow { font-size: 10px; font-weight: 300; letter-spacing: 0.4em; text-transform: uppercase; color: #aaa; margin-bottom: 20px; }
.hero-title { font-family: 'Noto Serif', serif; font-size: 48px; font-weight: 300; line-height: 1.15; color: #1a1a1a; margin-bottom: 16px; letter-spacing: -0.02em; }
.hero-title em { font-style: italic; color: #555; }
.hero-sub { font-size: 13px; font-weight: 300; color: #888; line-height: 1.8; }
.hero-pipeline { display: flex; align-items: center; gap: 8px; margin-top: 28px; font-size: 10px; letter-spacing: 0.15em; text-transform: uppercase; color: #ccc; }
.hero-pipeline strong { color: #1a1a1a; font-weight: 400; }
.hero-pipeline .sep { color: #ddd; }
.empty-state { padding: 80px 72px; display: flex; flex-direction: column; gap: 12px; }
.empty-mark { width: 32px; height: 1px; background: #d8d8d2; margin-bottom: 4px; }
.empty-text { font-family: 'Noto Serif', serif; font-size: 17px; font-weight: 300; color: #aaa; font-style: italic; }
.empty-hint { font-size: 11px; font-weight: 300; color: #ccc; letter-spacing: 0.1em; }
.chat-area { padding: 40px 72px; max-width: 820px; }
[data-testid="stChatMessage"] { background: transparent !important; border: none !important; padding: 0 !important; margin-bottom: 32px !important; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p { font-family: 'Noto Sans JP', sans-serif !important; font-size: 14px !important; font-weight: 300 !important; line-height: 1.9 !important; color: #1a1a1a !important; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: #f2f2ee !important; padding: 18px 24px !important; border-left: 2px solid #1a1a1a !important; }
[data-testid="stExpander"] { border: 1px solid #e8e8e4 !important; border-radius: 0 !important; background: #fafaf8 !important; margin-top: 8px !important; }
[data-testid="stExpander"] summary { font-family: 'Noto Sans JP', sans-serif !important; font-size: 10px !important; font-weight: 300 !important; letter-spacing: 0.25em !important; text-transform: uppercase !important; color: #aaa !important; padding: 10px 14px !important; }
[data-testid="stChatInput"] { border-top: 1px solid #d8d8d2 !important; background: #fafaf8 !important; padding: 16px 72px !important; }
[data-testid="stChatInput"] textarea { font-family: 'Noto Sans JP', sans-serif !important; font-size: 14px !important; font-weight: 300 !important; border: none !important; border-bottom: 1px solid #d8d8d2 !important; border-radius: 0 !important; background: transparent !important; color: #1a1a1a !important; }
.doc-pill { display: flex; align-items: center; gap: 8px; font-size: 11px; font-weight: 300; color: #555; padding: 6px 0; border-bottom: 1px solid #e8e8e4; }
.doc-pill::before { content: ''; width: 4px; height: 4px; background: #1a1a1a; border-radius: 50%; flex-shrink: 0; }
.source-card { padding: 10px 0; border-bottom: 1px solid #f0f0ec; }
.source-title { font-size: 11px; font-weight: 400; color: #333; margin-bottom: 3px; display: flex; justify-content: space-between; }
.source-score { font-family: 'Noto Serif', serif; font-size: 10px; font-style: italic; color: #aaa; }
.source-snippet { font-size: 11px; font-weight: 300; color: #888; line-height: 1.7; }
.badge-row { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.badge { display: flex; align-items: center; gap: 7px; font-size: 10px; font-weight: 300; color: #888; }
.badge-dot { width: 5px; height: 5px; border-radius: 50%; background: #1a1a1a; flex-shrink: 0; }
.agent-tag { display: inline-block; font-size: 10px; font-family: 'Noto Serif', serif; font-style: italic; color: #aaa; letter-spacing: 0.05em; margin-right: 12px; }
.cache-tag { display: inline-block; font-size: 10px; font-family: 'Noto Sans JP', sans-serif; font-weight: 300; letter-spacing: 0.15em; text-transform: uppercase; color: #3a7a3a; padding: 2px 6px; border: 1px solid #3a7a3a; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: #d8d8d2; }
</style>
""", unsafe_allow_html=True)

# ΓöÇΓöÇ Session state ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
defaults = {
    "messages":      [],
    "source_name":   None,
    "ingested":      False,
    "all_sources":   [],
    "source_filter": None,
    "user_id":       "demo-user",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Sidebar
with st.sidebar:
    st.markdown('<div class="sidebar-mark">Document</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Load source</div>', unsafe_allow_html=True)

    tab_url, tab_pdf = st.tabs(["URL", "PDF"])

    with tab_url:
        url = st.text_input("URL", placeholder="https://...", label_visibility="collapsed")
        if st.button("Index URL", disabled=not url, key="btn_url"):
            with st.spinner("fetching ┬╖ chunking ┬╖ embedding"):
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
            with st.spinner("reading ┬╖ chunking ┬╖ embedding"):
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
            short = doc[:34] + "ΓÇª" if len(doc) > 34 else doc
            st.markdown(f'<div class="doc-pill">{short}</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">Scope</div>', unsafe_allow_html=True)
        selected = st.selectbox(
            "Scope",
            ["All documents"] + st.session_state.all_sources,
            label_visibility="collapsed",
        )
        st.session_state.source_filter = None if selected == "All documents" else selected

        # Display document summary if loaded
        if st.session_state.ingested and st.session_state.source_name:
            try:
                summary = get_summary("demo-user", st.session_state.source_name)
                if summary:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown('<div class="section-label">Summary</div>', unsafe_allow_html=True)
                    st.caption(summary)
            except Exception:
                # Silently skip summary on error (e.g., NVIDIA_API_KEY not set)
                pass

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="badge-row">
            <div class="badge"><span class="badge-dot"></span>LangGraph agents active</div>
            <div class="badge"><span class="badge-dot"></span>Semantic cache active</div>
            <div class="badge"><span class="badge-dot"></span>HyDE + hybrid search</div>
            <div class="badge"><span class="badge-dot"></span>Self-RAG evaluation</div>
            <div class="badge"><span class="badge-dot"></span>Query rewriting</div>
        </div>
        """, unsafe_allow_html=True)

        # Cache stats
        stats = get_cache_stats()
        if stats.get("enabled"):
            st.caption(f"Cache: {stats.get('cached_queries', 0)} queries stored")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Clear all", key="btn_clear"):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()

    st.markdown("<br>" * 3, unsafe_allow_html=True)
    st.markdown(
        '<div style="font-family:\'Noto Serif\',serif;font-size:10px;'
        'color:#ccc;letter-spacing:0.2em;font-style:italic;">AskMyDocs • 2026</div>',
        unsafe_allow_html=True,
    )

# ── Main ──
if not st.session_state.ingested:
    st.markdown("""
    <div class="hero">
        <div class="hero-eyebrow">RAG • Agentic Document Intelligence</div>
        <div class="hero-title">Ask anything.<br><em>Get cited answers.</em></div>
        <div class="hero-sub">
            Load any PDF or public URL from the sidebar.<br>
            Multi-agent system routes each query to the right specialist.
        </div>
        <div class="hero-pipeline">
            <strong>Classify</strong><span class="sep">•</span>
            <strong>Route</strong><span class="sep">•</span>
            <strong>Retrieve</strong><span class="sep">•</span>
            <strong>Evaluate</strong><span class="sep">•</span>
            <strong>Answer</strong>
        </div>
    </div>
    <div class="empty-state">
        <div class="empty-mark"></div>
        <div class="empty-text">No document loaded.</div>
        <div class="empty-hint">ℹ️ Load a source to begin</div>
    </div>
    """, unsafe_allow_html=True)

else:
    st.markdown('<div class="chat-area">', unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant":
                # Metadata row
                meta_parts = []
                if msg.get("agent_type"):
                    meta_parts.append(f'<span class="agent-tag">{msg["agent_type"]} agent</span>')
                if msg.get("cache_hit"):
                    meta_parts.append(f'<span class="cache-tag">cache {msg["cache_hit"]}</span>')
                if msg.get("routing"):
                    r = msg["routing"]
                    model_s = "70B" if "70b" in r.get("model","") else "8B"
                    meta_parts.append(f'<span class="agent-tag">{model_s} ┬╖ score {r.get("score",0):.2f}</span>')
                if msg.get("rewritten_query") and msg["rewritten_query"] != msg.get("original_query"):
                    # Extract just the first part before any OR operators for cleaner display
                    display_rewritten = msg["rewritten_query"].split(" OR ")[0].strip().strip('"')[:40]
                    if display_rewritten:
                        meta_parts.append(f'<span class="agent-tag">rewritten: "{display_rewritten}ΓÇª"</span>')

                if meta_parts:
                    st.markdown(
                        f'<div style="margin-top:8px;">{"".join(meta_parts)}</div>',
                        unsafe_allow_html=True,
                    )

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

    st.markdown("</div>", unsafe_allow_html=True)

    query = st.chat_input("Ask a question…")
    if query:
        st.session_state.messages.append({"role": "user", "content": query, "original_query": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("classifying ┬╖ routing ┬╖ retrieving ┬╖ generating"):
                scope   = st.session_state.source_filter or st.session_state.source_name
                history = [m for m in st.session_state.messages[:-1] if m["role"] in ("user","assistant")]

                # ── Step 1: Check guardrails ──────────────────────────────────────
                guardrail_result = check_guardrails(query, skip_llm=True)
                if not guardrail_result.get("allowed", True):
                    blocked_msg = f"🚫 **Query blocked:** {guardrail_result.get('message', 'Content policy violation')}"
                    st.error(blocked_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": blocked_msg,
                        "blocked": True,
                    })
                    st.stop()  # Exit early without returning

                # ── Step 2: Check cache ───────────────────────────────────────────
                query_vector = embed_query(query)
                cached = get_cached_answer(query, query_vector)

                if cached:
                    response    = cached["answer"]
                    srcs        = cached.get("sources", [])
                    routing     = cached.get("routing", {})
                    agent_type  = "cached"
                    quality     = 1.0
                    rewritten   = query
                    cache_hit   = cached.get("cache_hit", "hit")
                    blocked     = False
                else:
                    # ── Step 3: Run agent ────────────────────────────────────────
                    result      = run_agent(query, scope, history)
                    response    = result["answer"]
                    srcs        = result["sources"]
                    routing     = result["routing"]
                    agent_type  = result["agent_type"]
                    quality     = result["quality_score"]
                    rewritten   = result["rewritten_query"]
                    cache_hit   = ""
                    blocked     = result.get("blocked", False)
                    set_cached_answer(query, query_vector, response, srcs, routing)

            st.markdown(response)

            # ── Show metadata ─────────────────────────────────────────────────────
            meta_parts = []
            if agent_type:
                meta_parts.append(f'<span class="agent-tag">{agent_type} agent</span>')
            if cache_hit:
                meta_parts.append(f'<span class="cache-tag">cache {cache_hit}</span>')
            if quality and quality < 1.0:
                meta_parts.append(f'<span class="agent-tag">quality: {quality:.2f}</span>')
            if routing:
                model_s = "70B" if "70b" in routing.get("model","") else "8B"
                meta_parts.append(f'<span class="agent-tag">{model_s} ┬╖ score {routing.get("score",0):.2f}</span>')
            if rewritten and rewritten != query:
                # Extract just the first part before any OR operators for cleaner display
                display_rewritten = rewritten.split(" OR ")[0].strip().strip('"')[:40]
                if display_rewritten:
                    meta_parts.append(f'<span class="agent-tag">rewritten: "{display_rewritten}ΓÇª"</span>')

            if meta_parts:
                st.markdown(
                    f'<div style="margin-top:8px;">{"".join(meta_parts)}</div>',
                    unsafe_allow_html=True,
                )

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

            # ── Store in message history ──────────────────────────────────────────
            st.session_state.messages.append({
                "role": "assistant",
                "content": response,
                "agent_type": agent_type,
                "cache_hit": cache_hit,
                "rewritten_query": rewritten,
                "routing": routing,
                "quality_score": quality,
                "sources": srcs,
                "blocked": blocked,
            })

            log_query(query, scope, len(srcs), len(response))

        st.session_state.messages.append({
            "role":            "assistant",
            "content":         response,
            "sources":         srcs,
            "routing":         routing,
            "agent_type":      agent_type,
            "quality_score":   quality,
            "rewritten_query": rewritten,
            "original_query":  query,
            "cache_hit":       cache_hit,
        })
