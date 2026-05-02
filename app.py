import streamlit as st
import os

# Load keys from Streamlit secrets when env vars are not present (Streamlit Cloud).
for _key in [
    "NVIDIA_API_KEY",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "UPSTASH_REDIS_URL",
    "UPSTASH_REDIS_TOKEN",
    "TAVILY_API_KEY",
]:
    if not os.getenv(_key):
        try:
            _value = st.secrets.get(_key)
            if _value:
                os.environ[_key] = str(_value)
        except Exception:
            pass

from datetime import datetime
import time

from backend.ingest import ingest, extract_from_url, extract_from_pdf, make_chunks
from backend.cache import get_cached_answer, set_cached_answer
from backend.retrieval import embed_query, retrieve
from backend.agents import run_agent
from backend.logger import log_query
from backend.observability import log_query_full
from backend.guardrails import check_guardrails
from backend.summariser import generate_summary, save_summary
from backend.graph_rag import build_graph_for_collection, graph_retrieve
from backend.raptor import build_raptor_tree, get_raptor_context, build_corpus_summary
from backend.structured_outputs import detect_output_type, generate_structured_answer
from backend.collaboration import create_session

st.set_page_config(page_title="AskMyDocs", page_icon="◻", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
:root { --bg:#ffffff; --panel:#f8f9fa; --border:#e0e2e6; --text:#1c1e21; --muted:#65676b; --accent:#0084ff; --accent2:#31a24c; }
*,*::before,*::after{box-sizing:border-box;}
html,body,[data-testid="stAppViewContainer"]{background:var(--bg)!important;color:var(--text)!important;font-family:'Inter',sans-serif!important;}
#MainMenu,footer,header,[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"]{display:none!important;}
[data-testid="stSidebar"]{background:var(--panel)!important;border-right:1px solid var(--border)!important;}
[data-testid="stSidebar"]>div{padding-top:1rem;}
.block-container{padding:1rem 1.2rem!important;max-width:100%!important;}
.hero{min-height:auto;display:grid;place-items:center;padding:2rem 1rem;}
.hero-card{width:min(920px,100%);background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:2rem 1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.08);}
.hero-kicker{color:var(--accent);text-transform:uppercase;letter-spacing:.18em;font-size:.72rem;margin-bottom:.8rem;font-weight:600;}
.hero-title{font-size:clamp(1.8rem,5vw,2.8rem);line-height:1.1;margin:0 0 1rem;font-weight:700;}
.hero-sub{color:var(--muted);font-size:.95rem;max-width:58ch;line-height:1.6;}
.feature-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:0.8rem;margin-top:1.5rem;}
.feature{background:white;border:1px solid var(--border);border-radius:12px;padding:1rem;text-align:center;}
.feature h4{margin:0 0 .4rem;font-size:.9rem;font-weight:600;color:var(--text);}.feature p{margin:0;color:var(--muted);font-size:.85rem;line-height:1.5;}
.chat-wrap{width:100%;max-width:960px;margin:0 auto;padding:1rem;padding-bottom:8rem;}
.chat-shell{background:white;border:1px solid var(--border);border-radius:12px;padding:1rem;}
.sidebar-section{color:var(--muted);text-transform:uppercase;letter-spacing:.12em;font-size:.7rem;margin:1.2rem 0 .6rem;font-weight:600;}
.summary-card{color:var(--muted);font-size:.85rem;line-height:1.5;padding:.75rem;background:var(--panel);border:1px solid var(--border);border-radius:8px;margin:.6rem 0;}
.doc-item{padding:.6rem .75rem;border-radius:8px;border:1px solid transparent;color:var(--text);font-size:.9rem;} .doc-item:hover{background:var(--panel);border-color:var(--border);}
.meta-row{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:0.8rem;}.meta-badge{background:var(--panel);border:1px solid var(--border);border-radius:999px;padding:.25rem .6rem;font-size:.75rem;color:var(--muted);font-weight:500;}
[data-testid="stChatMessage"]{background:transparent!important;border:none!important;max-width:100%;padding:0.5rem 0!important;}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"]{color:var(--text)!important;line-height:1.7!important;font-size:0.95rem;}
[data-testid="stChatInput"]{border:1px solid var(--border)!important;background:white!important;border-radius:12px!important;padding:0.75rem 1rem!important;}
[data-testid="stChatInput"] input{font-size:1rem!important;}
[data-testid="stButton"] button{border-radius:8px!important;font-weight:500;}
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea{border:1px solid var(--border)!important;border-radius:8px!important;padding:0.6rem 0.8rem!important;}
[data-testid="stSelectbox"] > div > button, [data-testid="stExpander"] {background:white!important;border-color:var(--border)!important;border-radius:8px!important;}
@media (max-width:768px){
  .block-container{padding:0.8rem!important;}
  .hero{padding:1.5rem 0.8rem;}
  .hero-card{padding:1.5rem 1rem;border-radius:12px;}
  .hero-title{font-size:1.6rem;}
  .feature-grid{grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:0.6rem;}
  .chat-wrap{padding:0.8rem;padding-bottom:6rem;}
  .chat-shell{padding:0.8rem;border-radius:10px;}
  [data-testid="stChatInput"]{margin:1rem 0.5rem!important;}
  [data-testid="stChatInput"] input{font-size:16px!important;}
}
@media (max-width:480px){
  .block-container{padding:0.5rem!important;}
  .feature-grid{grid-template-columns:1fr;}
  .hero-card{padding:1rem;}
  .hero-title{font-size:1.4rem;}
  .chat-wrap{padding:0.5rem;padding-bottom:5rem;}
}
</style>
""",
    unsafe_allow_html=True,
)

defaults = {
    "user_id": "local_user",
    "messages": [],
    "source_name": None,
    "all_sources": [],
    "source_filter": None,
    "summaries": {},
    "use_graph_rag": False,
    "use_structured": True,
    "collab_session": None,
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)


def _reset_chat() -> None:
    st.session_state.messages = []
    st.session_state.source_name = None
    st.session_state.source_filter = None


def _ingest_document(title: str, source_type: str, text: str) -> None:
    chunk_count = ingest(title, source_type, text)
    chunks = make_chunks(title, source_type, text)
    summary = generate_summary(title, chunks)
    save_summary(st.session_state.user_id, title, summary, chunk_count)
    st.session_state.source_name = title
    st.session_state.source_filter = title
    if title not in st.session_state.all_sources:
        st.session_state.all_sources.append(title)
    st.session_state.summaries[title] = summary
    try:
        build_graph_for_collection(st.session_state.user_id, st.session_state.user_id, chunks)
    except Exception:
        pass
    try:
        build_raptor_tree(st.session_state.user_id, title, chunks)
        build_corpus_summary(st.session_state.user_id)
    except Exception:
        pass
    st.session_state.messages = [{"role": "assistant", "content": f"Indexed {chunk_count} chunks from {title}."}]


with st.sidebar:
    st.markdown('<div class="sidebar-section">AskMyDocs</div>', unsafe_allow_html=True)
    if st.button("New chat", use_container_width=True):
        _reset_chat()
        st.rerun()

    st.markdown('<div class="sidebar-section">Load document</div>', unsafe_allow_html=True)
    tab_url, tab_pdf = st.tabs(["URL", "PDF"])
    with tab_url:
        url = st.text_input("URL", placeholder="https://…", label_visibility="collapsed")
        if st.button("Load URL", use_container_width=True, disabled=not url):
            with st.spinner("Loading document…"):
                title, text = extract_from_url(url)
                _ingest_document(title, "url", text)
                st.success(f"Loaded {title}")
    with tab_pdf:
        pdf = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
        if st.button("Load PDF", use_container_width=True, disabled=not pdf):
            with st.spinner("Reading PDF…"):
                title, text = extract_from_pdf(pdf.read(), pdf.name)
                _ingest_document(title, "pdf", text)
                st.success(f"Loaded {title}")

    if st.session_state.all_sources:
        st.markdown('<div class="sidebar-section">Documents</div>', unsafe_allow_html=True)
        selected = st.selectbox("Scope", ["All documents"] + st.session_state.all_sources, label_visibility="collapsed")
        st.session_state.source_filter = None if selected == "All documents" else selected
        for doc in st.session_state.all_sources:
            st.markdown(f'<div class="doc-item">{doc}</div>', unsafe_allow_html=True)
            if st.session_state.summaries.get(doc):
                st.markdown(f'<div class="summary-card">{st.session_state.summaries[doc]}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">Settings</div>', unsafe_allow_html=True)
    st.session_state.use_graph_rag = st.toggle("Graph RAG", value=st.session_state.use_graph_rag)
    st.session_state.use_structured = st.toggle("Structured outputs", value=st.session_state.use_structured)

    st.markdown('<div class="sidebar-section">Collaboration</div>', unsafe_allow_html=True)
    if st.button("Create session", use_container_width=True):
        try:
            session = create_session(st.session_state.user_id, st.session_state.source_name or "document")
            st.session_state.collab_session = session
            st.success(f"Code: {session['session_code']}")
        except Exception as exc:
            st.error(str(exc))


if not st.session_state.source_name and not st.session_state.messages:
    st.markdown(
        """
        <div class="hero">
          <div class="hero-card">
            <div class="hero-kicker">AskMyDocs v6</div>
            <h1 class="hero-title">Document Q&A, built for deep retrieval.</h1>
            <p class="hero-sub">Load a PDF or URL, then ask questions with Graph RAG, RAPTOR summaries, structured outputs, collaboration sessions, and observability in separate dashboard pages.</p>
            <div class="feature-grid">
              <div class="feature"><h4>Graph RAG</h4><p>Multi-hop reasoning across entities and relations.</p></div>
              <div class="feature"><h4>RAGAS</h4><p>Track faithfulness, relevancy, recall, and precision.</p></div>
              <div class="feature"><h4>Structured outputs</h4><p>Render comparisons, metrics, timelines, and lists.</p></div>
              <div class="feature"><h4>Collaboration</h4><p>Share a live session code with your team.</p></div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


st.markdown('<div class="chat-wrap"><div class="chat-shell">', unsafe_allow_html=True)
if st.session_state.collab_session:
    st.caption(f"Live session: {st.session_state.collab_session.get('session_code', '')}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message.get("content", ""))

st.markdown('</div></div>', unsafe_allow_html=True)

query = st.chat_input("Ask anything about your document…")
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    guard = check_guardrails(query, st.session_state.source_name)
    if not guard.get("allowed", True):
        with st.chat_message("assistant"):
            st.warning(guard.get("message", "Blocked by guardrails."))
        st.session_state.messages.append({"role": "assistant", "content": guard.get("message", "Blocked by guardrails.")})
        st.stop()

    # Check if collection exists (i.e., documents have been uploaded)
    try:
        from backend.retrieval import get_qdrant_client
        from backend.config import COLLECTION_NAME
        client = get_qdrant_client()
        existing_collections = [c.name for c in client.get_collections().collections]
        
        # Use the same collection logic as in agents/retrieval
        collection_to_check = st.session_state.user_id if st.session_state.user_id != "local_user" else COLLECTION_NAME
        
        if collection_to_check not in existing_collections:
            with st.chat_message("assistant"):
                st.warning("📄 No documents uploaded yet. Please upload a PDF or provide a URL in the sidebar to get started.")
            st.session_state.messages.append({"role": "assistant", "content": "No documents uploaded yet. Please upload a PDF or provide a URL to get started."})
            st.stop()
    except Exception as e:
        st.warning(f"⚠️ Could not verify documents: {str(e)}")
    
    start = time.time()
    scope = st.session_state.source_filter or st.session_state.source_name
    history = st.session_state.messages[:-1]
    query_vector = embed_query(query)
    cached = get_cached_answer(query, query_vector)

    if cached:
        response = cached.get("answer", "")
        sources = cached.get("sources", [])
        routing = cached.get("routing", {})
        agent_type = "cached"
        rewritten_query = query
        quality_score = 1.0
    else:
        raptor_context = get_raptor_context(st.session_state.user_id, query, scope)
        result = run_agent(query, scope, history, collection=st.session_state.user_id, doc_context=raptor_context)
        response = result["answer"]
        sources = result["sources"]
        routing = result.get("routing", {})
        agent_type = result.get("agent_type", "unknown")
        rewritten_query = result.get("rewritten_query", query)
        quality_score = result.get("quality_score", 0.0)

        if st.session_state.use_graph_rag and sources:
            try:
                all_chunks = retrieve(query, scope, history, collection_name=st.session_state.user_id)
                for chunk in graph_retrieve(query, st.session_state.user_id, st.session_state.user_id, all_chunks)[:2]:
                    sources.append({"name": chunk.payload.get("source_name", scope or "document"), "snippet": chunk.payload.get("text", "")[:180], "type": "graph"})
            except Exception:
                pass

        output_type = detect_output_type(query) if st.session_state.use_structured else "standard"
        if output_type != "standard" and sources:
            context_text = "\n\n".join(f"[Source {i + 1}] {src.get('snippet', '')}" for i, src in enumerate(sources[:5]))
            structured = generate_structured_answer(query, context_text, output_type, history)
            response = structured.get("answer", response)

        set_cached_answer(query, query_vector, response, sources, routing)
        log_query(query, scope, len(sources), len(response))
        log_query_full(st.session_state.user_id, query, rewritten_query, agent_type, routing.get("model", ""), int((time.time() - start) * 1000), len(sources), quality_score, "", False, scope)

    with st.chat_message("assistant"):
        st.markdown(response)
        badges = [agent_type]
        if cached:
            badges.append("cache hit")
        if routing.get("model"):
            badges.append(routing.get("model"))
        if st.session_state.use_structured:
            badges.append(detect_output_type(query))
        st.markdown('<div class="meta-row">' + ''.join(f'<span class="meta-badge">{badge}</span>' for badge in badges) + '</div>', unsafe_allow_html=True)
        if sources:
            with st.expander(f"Sources ({len(sources)})"):
                for idx, source in enumerate(sources, start=1):
                    st.markdown(f"**[{idx}] {source.get('name', 'Source')}**")
                    st.caption(source.get("snippet", ""))

    st.session_state.messages.append({"role": "assistant", "content": response})

st.stop()

from backend.ingest import ingest, extract_from_url, extract_from_pdf
from backend.cache import get_cached_answer, set_cached_answer, get_cache_stats
from backend.retrieval import embed_query
from backend.agents import run_agent
from backend.logger import log_query
from backend.guardrails import check_guardrails
from backend.summariser import get_summary, generate_summary, save_summary

st.set_page_config(
    page_title="AskMyDocs",
    page_icon="📄",
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

# ── Session State ──
defaults = {
    "messages":      [],
    "source_name":   None,
    "ingested":      False,
    "all_sources":   [],
    "source_filter": None,
    "user_id":       "demo-user",
    "summaries":     {},  # Cache summaries in session: {doc_title: summary_text}
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
            with st.spinner("fetching • chunking • embedding"):
                try:
                    title, text = extract_from_url(url)
                    n = ingest(title, "url", text)
                    st.session_state.source_name = title
                    st.session_state.ingested = True
                    st.session_state.messages = []
                    if title not in st.session_state.all_sources:
                        st.session_state.all_sources.append(title)
                    st.success(f"{n} chunks indexed")
                    # Generate and cache summary in session state
                    try:
                        summary = generate_summary(title, text.split("\n\n")[:10])
                        st.session_state.summaries[title] = summary
                        # Also try to persist to Supabase for production
                        save_summary(st.session_state.user_id, title, summary, n)
                    except Exception:
                        pass
                except Exception as e:
                    st.error(str(e))

    with tab_pdf:
        pdf = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
        if st.button("Index PDF", disabled=not pdf, key="btn_pdf"):
            with st.spinner("reading • chunking • embedding"):
                try:
                    title, text = extract_from_pdf(pdf.read(), pdf.name)
                    n = ingest(title, "pdf", text)
                    st.session_state.source_name = title
                    st.session_state.ingested = True
                    st.session_state.messages = []
                    if title not in st.session_state.all_sources:
                        st.session_state.all_sources.append(title)
                    st.success(f"{n} chunks indexed")
                    # Generate and cache summary in session state
                    try:
                        summary = generate_summary(title, text.split("\n\n")[:10])
                        st.session_state.summaries[title] = summary
                        # Also try to persist to Supabase for production
                        save_summary(st.session_state.user_id, title, summary, n)
                    except Exception:
                        pass
                except Exception as e:
                    st.error(str(e))

    if st.session_state.ingested:
        st.markdown("---")
        st.markdown('<div class="section-label">Loaded</div>', unsafe_allow_html=True)
        for doc in st.session_state.all_sources:
            short = doc[:34] + "..." if len(doc) > 34 else doc
            st.markdown(f'<div class="doc-pill">{short}</div>', unsafe_allow_html=True)

        # Display document summary directly below Loaded, matching React layout.
        if st.session_state.ingested and st.session_state.source_name:
            # First check session state (in-memory cache)
            summary = st.session_state.summaries.get(st.session_state.source_name)
            
            # If not in session, try retrieving from Supabase
            if not summary:
                try:
                    summary = get_summary("demo-user", st.session_state.source_name)
                except Exception:
                    pass
            
            # Display if we have a summary
            if summary:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown('<div class="section-label">Summaries</div>', unsafe_allow_html=True)
                st.markdown(f"**{st.session_state.source_name}**")
                st.caption(summary)

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
                    meta_parts.append(f'<span class="agent-tag">{model_s} • score {r.get("score",0):.2f}</span>')
                if msg.get("rewritten_query") and msg["rewritten_query"] != msg.get("original_query"):
                    # Extract just the first part before any OR operators for cleaner display
                    display_rewritten = msg["rewritten_query"].split(" OR ")[0].strip().strip('"')[:40]
                    if display_rewritten:
                        meta_parts.append(f'<span class="agent-tag">rewritten: "{display_rewritten}..."</span>')

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
            with st.spinner("classifying • routing • retrieving • generating"):
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
                meta_parts.append(f'<span class="agent-tag">{model_s} • score {routing.get("score",0):.2f}</span>')
            if rewritten and rewritten != query:
                # Extract just the first part before any OR operators for cleaner display
                display_rewritten = rewritten.split(" OR ")[0].strip().strip('"')[:40]
                if display_rewritten:
                    meta_parts.append(f'<span class="agent-tag">rewritten: "{display_rewritten}..."</span>')

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
