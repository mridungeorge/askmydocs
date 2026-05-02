"""AskMyDocs v6 collaboration page: shared sessions and live conversation history."""

import streamlit as st

from backend.collaboration import create_session, get_session, add_session_message, get_session_messages
from backend.agents import run_agent

st.set_page_config(page_title="AskMyDocs — Collaboration", page_icon="👥", layout="wide")

if "user_id" not in st.session_state:
    st.session_state.user_id = "local_user"
if "user_name" not in st.session_state:
    st.session_state.user_name = "User"
if "collab_session" not in st.session_state:
    st.session_state.collab_session = None
if "collab_messages" not in st.session_state:
    st.session_state.collab_messages = []

st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] { background: #ffffff !important; color: #1c1e21 !important; }
    #MainMenu, footer, header, [data-testid="stToolbar"] { display: none !important; }
    .block-container { padding: 1rem 1.2rem 2rem !important; max-width: 960px !important; }
    .session-code { font-size: 1.8rem; font-weight: 700; letter-spacing: .15em; color: #0084ff; background: #f8f9fa; border: 1px solid #e0e2e6; padding: 1.2rem; text-align: center; border-radius: 12px; }
    .msg-user { background: #f0f2f6; border: 1px solid #e0e2e6; border-radius: 12px; padding: 1rem; margin: 0.8rem 0; }
    .msg-assistant { padding: 0.5rem 0 1rem; margin: 0.8rem 0; }
    .msg-meta { font-size: 0.8rem; color: #65676b; margin-bottom: 0.5rem; }
    [data-testid="stButton"] button { border-radius: 8px !important; font-weight: 500; }
    [data-testid="stTextInput"] input { border: 1px solid #e0e2e6 !important; border-radius: 8px !important; }
    h1, h2, h3, h4, h5, h6 { color: #1c1e21 !important; }
    .stCaption { color: #65676b !important; }
    @media (max-width:768px){
      .block-container { padding: 0.8rem !important; }
      .session-code { font-size: 1.4rem; padding: 1rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Collaboration")
st.caption("Share a document session with your team in real time.")

if not st.session_state.collab_session:
    st.subheader("Join or create a session")
    left, right = st.columns(2)
    with left:
        code = st.text_input("Session code", placeholder="XK7M2P")
        if st.button("Join session") and code:
            session = get_session(code)
            if session:
                st.session_state.collab_session = session
                st.session_state.collab_messages = get_session_messages(session["id"])
                st.rerun()
            else:
                st.error("Session not found or inactive.")
    with right:
        doc_title = st.text_input("Document name", placeholder="Q3 report")
        if st.button("Create session") and doc_title:
            session = create_session(st.session_state.user_id, doc_title)
            st.session_state.collab_session = session
            st.session_state.collab_messages = []
            st.rerun()
else:
    session = st.session_state.collab_session
    st.markdown(f'<div class="session-code">{session.get("session_code", "")}</div>', unsafe_allow_html=True)
    st.caption(f"Document: {session.get('doc_title', '')}")

    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("Refresh"):
            st.session_state.collab_messages = get_session_messages(session["id"])
    with col_b:
        if st.button("Leave session"):
            st.session_state.collab_session = None
            st.session_state.collab_messages = []
            st.rerun()

    for msg in st.session_state.collab_messages:
        if msg.get("role") == "user":
            st.markdown(
                f'<div class="msg-user"><div class="msg-meta">{msg.get("user_email") or msg.get("user_id", "User")}</div><div>{msg.get("content", "")}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="msg-assistant"><div class="msg-meta">Assistant</div><div>{msg.get("content", "")}</div></div>',
                unsafe_allow_html=True,
            )

    st.divider()
    with st.form("collab_message"):
        question = st.text_area("Ask a question", height=90)
        submitted = st.form_submit_button("Send")
    if submitted and question.strip():
        add_session_message(session["id"], st.session_state.user_id, st.session_state.user_name, "user", question)
        result = run_agent(question, session.get("doc_title"))
        add_session_message(session["id"], st.session_state.user_id, "Assistant", "assistant", result.get("answer", ""), result.get("sources", []))
        st.session_state.collab_messages = get_session_messages(session["id"])
        st.rerun()
