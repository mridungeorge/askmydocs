import streamlit as st
from backend.ingest import ingest, extract_from_url, extract_from_pdf
from backend.retrieval import retrieve
from backend.generation import answer
from backend.logger import log_query

st.set_page_config(page_title="AskMyDocs", page_icon="📄", layout="centered")
st.title("📄 AskMyDocs")
st.caption("Upload a PDF or paste a URL — then ask anything about it.")

# ── Session state ─────────────────────────────────────────────────────────────
if "messages"       not in st.session_state: st.session_state.messages       = []
if "source_name"    not in st.session_state: st.session_state.source_name    = None
if "ingested"       not in st.session_state: st.session_state.ingested       = False
if "all_sources"    not in st.session_state: st.session_state.all_sources    = []
if "source_filter"  not in st.session_state: st.session_state.source_filter  = None

# ── Sidebar — document loading ────────────────────────────────────────────────
with st.sidebar:
    st.header("Load a document")
    tab_url, tab_pdf = st.tabs(["URL", "PDF"])

    with tab_url:
        url = st.text_input("Paste a URL", placeholder="https://...")
        if st.button("Load URL", disabled=not url):
            with st.spinner("Fetching and indexing..."):
                try:
                    title, text = extract_from_url(url)
                    n = ingest(title, "url", text)
                    st.session_state.source_name = title
                    st.session_state.ingested    = True
                    st.session_state.messages    = []
                    if title not in st.session_state.all_sources:
                        st.session_state.all_sources.append(title)
                    st.success(f"Indexed {n} chunks from: {title}")
                except Exception as e:
                    st.error(f"Failed: {e}")

    with tab_pdf:
        pdf = st.file_uploader("Upload PDF", type=["pdf"])
        if st.button("Load PDF", disabled=not pdf):
            with st.spinner("Reading and indexing..."):
                try:
                    title, text = extract_from_pdf(pdf.read(), pdf.name)
                    n = ingest(title, "pdf", text)
                    st.session_state.source_name = title
                    st.session_state.ingested    = True
                    st.session_state.messages    = []
                    if title not in st.session_state.all_sources:
                        st.session_state.all_sources.append(title)
                    st.success(f"Indexed {n} chunks from: {pdf.name}")
                except Exception as e:
                    st.error(f"Failed: {e}")

    if st.session_state.ingested:
        st.divider()
        st.markdown("**Loaded documents:**")
        for doc in st.session_state.get("all_sources", []):
            st.caption(f"• {doc}")
        
        selected = st.selectbox(
            "Ask about:",
            ["All documents"] + st.session_state.get("all_sources", [])
        )
        st.session_state.source_filter = None if selected == "All documents" else selected
        
        if st.button("Clear all"):
            st.session_state.messages    = []
            st.session_state.source_name = None
            st.session_state.ingested    = False
            st.session_state.all_sources = []
            st.rerun()

# ── Chat area ─────────────────────────────────────────────────────────────────
if not st.session_state.ingested:
    st.info("Load a document from the sidebar to get started.")
else:
    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("Sources used"):
                    for i, s in enumerate(msg["sources"]):
                        score_text = f" — {s['score']}% match" if s.get('score') else ""
                        st.markdown(f"**[Source {i+1}] {s['name']}**{score_text}")
                        st.caption(s["snippet"])

    # New question
    query = st.chat_input("Ask a question about your document...")
    if query:
        # Show user message
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        # Generate answer
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                chunks         = retrieve(query, st.session_state.source_filter or st.session_state.source_name)
                response, srcs = answer(query, chunks)
            st.markdown(response)
            if srcs:
                with st.expander("Sources used"):
                    for i, s in enumerate(srcs):
                        score_text = f" — {s['score']}% match" if s.get('score') else ""
                        st.markdown(f"**[Source {i+1}] {s['name']}**{score_text}")
                        st.caption(s["snippet"])
            log_query(query, st.session_state.source_filter or st.session_state.source_name, len(chunks), len(response))

        st.session_state.messages.append({
            "role":    "assistant",
            "content": response,
            "sources": srcs,
        })