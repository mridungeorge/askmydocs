import streamlit as st
import requests
import json
from datetime import datetime
import os

# ============= CONFIG =============
BACKEND_URL = os.getenv("BACKEND_URL", "https://askmydocs-george.up.railway.app")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# ============= PAGE CONFIG =============
st.set_page_config(
    page_title="AskMyDocs",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============= STYLING =============
st.markdown("""
<style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .main { max-width: 900px; margin: 0 auto; }
    .chat-message { 
        padding: 12px; 
        margin: 10px 0; 
        border-radius: 8px;
        display: flex;
        gap: 10px;
    }
    .user-message { 
        background-color: #e3f2fd; 
        margin-left: 40px;
        justify-content: flex-end;
    }
    .assistant-message { 
        background-color: #f5f5f5; 
        margin-right: 40px;
    }
    .thinking-msg {
        color: #999;
        font-size: 0.9em;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# ============= SESSION STATE =============
if "messages" not in st.session_state:
    st.session_state.messages = []
if "jwt_token" not in st.session_state:
    st.session_state.jwt_token = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ============= HEADER =============
st.markdown("# 📚 AskMyDocs")
st.markdown("*Chat with your documents. Powered by NVIDIA LLMs.*")

# ============= AUTHENTICATION SECTION =============
if not st.session_state.authenticated:
    st.divider()
    st.subheader("🔐 Sign In")
    
    auth_method = st.radio("Choose authentication method:", ["Email/Password", "Demo Mode"])
    
    if auth_method == "Email/Password":
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sign In", key="signin_btn"):
                if email and password:
                    st.info("🔗 Supabase authentication coming soon! For now, use Demo Mode.")
                else:
                    st.warning("Please enter email and password")
        with col2:
            if st.button("Sign Up", key="signup_btn"):
                st.info("📝 Sign up at supabase.com or use Demo Mode for testing")
    
    else:  # Demo Mode
        demo_user = st.text_input("Enter a demo user ID", value="demo_user_001")
        
        if st.button("Enter Demo Mode", key="demo_btn"):
            st.session_state.authenticated = True
            st.session_state.user_id = demo_user
            st.session_state.jwt_token = f"demo_token_{demo_user}"
            st.success(f"✅ Logged in as {demo_user}")
            st.rerun()
    
    st.stop()

# ============= MAIN CHAT INTERFACE =============
st.divider()
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.write(f"**Logged in as:** {st.session_state.user_id}")
with col3:
    if st.button("🚪 Sign Out", key="signout_btn"):
        st.session_state.authenticated = False
        st.session_state.jwt_token = None
        st.session_state.user_id = None
        st.session_state.messages = []
        st.rerun()

st.divider()

# ============= CHAT DISPLAY =============
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"**You:** {msg['content']}")
        else:
            st.markdown(f"**Assistant:** {msg['content']}")
            if "model" in msg:
                st.caption(f"*Model: {msg['model']} | Score: {msg.get('complexity_score', 'N/A')}*")

# ============= INPUT =============
st.divider()
user_input = st.text_area(
    "Ask a question about your documents:",
    placeholder="e.g., What are the main topics covered?",
    height=100,
    key="user_input"
)

col1, col2 = st.columns([4, 1])

with col2:
    send_button = st.button("📤 Send", key="send_btn", use_container_width=True)

if send_button and user_input:
    # Add user message to chat
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    
    # Show loading state
    with st.spinner("⏳ Thinking..."):
        try:
            # Call FastAPI backend
            headers = {"Authorization": f"Bearer {st.session_state.jwt_token}"}
            payload = {
                "query": user_input,
                "top_k": 5
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/chat",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Add assistant response
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data.get("answer", "No response received"),
                    "model": data.get("model", "unknown"),
                    "complexity_score": data.get("complexity_score", None)
                })
                
                st.success("✅ Response received!")
                st.rerun()
            elif response.status_code == 401:
                st.error("🔐 Authentication failed. Please sign in again.")
                st.session_state.authenticated = False
                st.rerun()
            else:
                st.error(f"❌ Error: {response.status_code} - {response.text}")
                
        except requests.exceptions.ConnectionError:
            st.error(f"🔗 Cannot connect to backend at {BACKEND_URL}")
            st.info("Make sure the FastAPI server is running.")
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out. Try again.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# ============= SIDEBAR =============
with st.sidebar:
    st.header("⚙️ Settings")
    
    st.subheader("Backend Status")
    try:
        health = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
        if health.status_code == 200:
            st.success("✅ Backend Connected")
        else:
            st.warning("⚠️ Backend Error")
    except:
        st.error("❌ Backend Offline")
    
    st.markdown(f"**API URL:** `{BACKEND_URL}`")
    
    st.divider()
    
    st.subheader("Chat History")
    if st.button("🗑️ Clear Chat", key="clear_btn"):
        st.session_state.messages = []
        st.rerun()
    
    st.caption(f"Messages: {len(st.session_state.messages)}")
    
    st.divider()
    
    with st.expander("📖 Instructions"):
        st.markdown("""
        1. **Sign In** using Demo Mode or email
        2. **Upload Documents** (coming soon)
        3. **Ask Questions** about your documents
        4. Get **AI-powered answers** with model routing
        
        **Features:**
        - Smart complexity scoring
        - Automatic model selection (8B/70B)
        - Document embedding & retrieval
        - Multi-turn conversations
        """)
