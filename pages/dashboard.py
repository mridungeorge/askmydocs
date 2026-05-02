"""
Observability dashboard — Streamlit page.

Why a separate page instead of the main app:
Keeps the main chat UI clean. Engineers/admins access
this page separately. Streamlit's multi-page routing
handles this with zero extra configuration.

What it shows:
- Query volume over time (line chart)
- Cache hit rate (metric card)
- Agent distribution (bar chart)
- Average quality and latency (metric cards)
- Recent query log (table)
- Document summaries
"""

import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="AskMyDocs — Dashboard", page_icon="📊", layout="wide")

# Note: In a real multi-page app you'd share auth state via st.session_state
# For simplicity this dashboard shows a note if not authenticated
if "user_id" not in st.session_state:
    st.warning("Please log in from the main app first.")
    st.stop()

from backend.observability import get_metrics, get_recent_queries
from backend.summariser import get_all_summaries
from backend.cache import get_cache_stats

user_id = st.session_state.get("user_id", "")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wght@0,300;1,300&family=Noto+Sans+JP:wght@300;400&display=swap');
html, body, [data-testid="stAppViewContainer"] { background: #ffffff !important; font-family: 'Noto Sans JP', sans-serif !important; font-weight: 300 !important; color: #1c1e21 !important; }
#MainMenu, footer, header, [data-testid="stToolbar"] { display: none !important; }
.block-container { padding: 1.5rem 1.2rem !important; max-width: 100% !important; }
h1, h2, h3 { font-family: 'Noto Serif', serif !important; font-weight: 300 !important; letter-spacing: -0.02em !important; color: #1c1e21 !important; }
[data-testid="stMetric"] { background: #f8f9fa !important; border: 1px solid #e0e2e6 !important; border-radius: 12px !important; }
[data-testid="stMetricValue"] { color: #31a24c !important; font-weight: 600; }
[data-testid="stSelectbox"] > div > button { border: 1px solid #e0e2e6 !important; border-radius: 8px !important; }
@media (max-width:768px){
  .block-container { padding: 0.8rem !important; }
}
@media (max-width:480px){
  .block-container { padding: 0.5rem !important; }
  h1 { font-size: 24px !important; }
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:40px;">
    <div style="font-size:10px;letter-spacing:0.4em;text-transform:uppercase;color:#aaa;margin-bottom:12px;">
        Observability
    </div>
    <h1 style="font-family:'Noto Serif',serif;font-size:36px;font-weight:300;margin:0;">
        System Dashboard
    </h1>
</div>
""", unsafe_allow_html=True)

# ── Controls ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 4])
with col1:
    days = st.selectbox("Time range", [7, 14, 30], format_func=lambda x: f"Last {x} days")

# ── Fetch metrics ─────────────────────────────────────────────────────────────
metrics     = get_metrics(user_id, days)
recent      = get_recent_queries(user_id, 20)
summaries   = get_all_summaries(user_id)
cache_stats = get_cache_stats()

# ── Top metric cards ──────────────────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric("Total queries", metrics["total_queries"])
with c2:
    st.metric("Cache hit rate", f"{metrics['cache_hit_rate']}%",
              help="% of queries served from cache — higher is better for cost")
with c3:
    st.metric("Avg quality", f"{metrics['avg_quality']:.2f}",
              help="Self-RAG quality score 0-1 — target > 0.7")
with c4:
    st.metric("Avg latency", f"{metrics['avg_latency_ms']}ms",
              help="End-to-end response time")
with c5:
    st.metric("Guardrail blocks", f"{metrics['guardrail_rate']}%",
              help="% of queries blocked — watch for sudden spikes")

st.markdown("---")

# ── Charts ────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("**Query volume — daily**")
    daily = metrics.get("daily_volume", {})
    if daily:
        # Sort by date
        dates  = sorted(daily.keys())
        counts = [daily[d] for d in dates]
        # Simple text chart since we don't want to import matplotlib
        for date, count in zip(dates, counts):
            bar = "█" * min(count, 50)
            st.text(f"{date}  {bar} {count}")
    else:
        st.caption("No data yet.")

with col_right:
    st.markdown("**Agent distribution**")
    agent_dist = metrics.get("agent_distribution", {})
    if agent_dist:
        total_agents = sum(agent_dist.values())
        for agent, count in sorted(agent_dist.items(), key=lambda x: x[1], reverse=True):
            pct = round(count / total_agents * 100)
            bar = "█" * (pct // 2)
            st.text(f"{agent:<12} {bar} {pct}%")
    else:
        st.caption("No data yet.")

st.markdown("---")

# ── Model usage ───────────────────────────────────────────────────────────────
col_m1, col_m2 = st.columns(2)

with col_m1:
    st.markdown("**Model distribution**")
    model_dist = metrics.get("model_distribution", {})
    if model_dist:
        for model, count in model_dist.items():
            st.text(f"{model}: {count} queries")
    else:
        st.caption("No data yet.")

with col_m2:
    st.markdown("**Cache**")
    if cache_stats.get("enabled"):
        st.text(f"Cached queries: {cache_stats.get('cached_queries', 0)}")
        st.text(f"TTL: {cache_stats.get('ttl_hours', 1)}h")
    else:
        st.caption("Cache not configured — add UPSTASH_REDIS_URL to enable.")

st.markdown("---")

# ── Recent queries table ──────────────────────────────────────────────────────
st.markdown("**Recent queries**")
if recent:
    for log in recent:
        with st.expander(f"{log.get('query', '')[:60]}… — {log.get('agent_type', '')} agent"):
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                model = log.get("model_used", "")
                st.caption(f"Model: {'70B' if '70b' in model.lower() else '8B'}")
            with col_b:
                st.caption(f"Latency: {log.get('latency_ms', 0)}ms")
            with col_c:
                st.caption(f"Quality: {log.get('quality_score', 0):.2f}")
            with col_d:
                cache = log.get("cache_hit", "")
                st.caption(f"Cache: {cache if cache else 'miss'}")
else:
    st.caption("No queries logged yet.")

st.markdown("---")

# ── Document summaries ────────────────────────────────────────────────────────
st.markdown("**Loaded documents**")
if summaries:
    for s in summaries:
        with st.expander(s.get("doc_title", "Unknown")):
            st.markdown(s.get("summary", "No summary available."))
            st.caption(f"{s.get('chunk_count', 0)} chunks · loaded {s.get('created_at', '')[:10]}")
else:
    st.caption("No documents loaded yet.")
