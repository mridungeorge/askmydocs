"""AskMyDocs v6 dashboard: observability, RAGAS, A/B testing, and cache metrics."""

import streamlit as st

from backend.observability import get_metrics, get_recent_queries
from backend.cache import get_cache_stats, clear_cache
from backend.eval_framework import run_evaluation, save_eval_question, get_eval_set, get_ragas_history
from backend.ab_testing import (
    get_active_experiment,
    get_experiment_results,
    create_experiment,
    PROMPT_A,
    PROMPT_B,
)
from backend.summariser import get_all_summaries

st.set_page_config(page_title="AskMyDocs — Dashboard", page_icon="📊", layout="wide")

if "user_id" not in st.session_state:
    st.session_state.user_id = "local_user"

user_id = st.session_state.user_id
metrics = get_metrics(user_id, 14)
recent = get_recent_queries(user_id, 12)
summaries = get_all_summaries(user_id)
cache_stats = get_cache_stats()
active_exp = get_active_experiment()

def metric_card(label: str, value: str) -> None:
    st.metric(label, value)

st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] { background: #ffffff !important; color: #1c1e21 !important; }
    #MainMenu, footer, header, [data-testid="stToolbar"] { display: none !important; }
    .block-container { padding: 1rem 1.2rem 2rem !important; max-width: 100% !important; }
    [data-testid="stMetric"] { background: #f8f9fa !important; border: 1px solid #e0e2e6 !important; border-radius: 12px !important; padding: 1.2rem !important; }
    [data-testid="stMetricValue"] { color: #31a24c !important; font-weight:600; }
    [data-testid="stMetricLabel"] { color: #65676b !important; }
    [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea { background: #ffffff !important; color: #1c1e21 !important; border: 1px solid #e0e2e6 !important; border-radius:8px !important; }
    [data-testid="stExpander"] { background: white !important; border: 1px solid #e0e2e6 !important; border-radius: 12px !important; }
    [data-testid="stSelectbox"] > div > button { border: 1px solid #e0e2e6 !important; border-radius: 8px !important; background: white !important; }
    [data-testid="stButton"] button { border-radius: 8px !important; font-weight: 500; }
    h1, h2, h3, h4, h5, h6 { color: #1c1e21 !important; }
    .stCaption { color: #65676b !important; }
    @media (max-width:768px){
      .block-container { padding: 0.8rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("System Dashboard")
st.caption("Observability · RAGAS eval · A/B testing · cache · document summaries")

col_a, col_b = st.columns([1, 3])
with col_a:
    days = st.selectbox("Time range", [7, 14, 30], index=1, format_func=lambda x: f"Last {x} days")
    if st.button("Clear cache"):
        clear_cache()
        st.rerun()

metrics = get_metrics(user_id, days)
cache_stats = get_cache_stats()

st.divider()
cols = st.columns(5)
cols[0].metric("Queries", metrics.get("total_queries", 0))
cols[1].metric("Cache hit rate", f"{metrics.get('cache_hit_rate', 0)}%")
cols[2].metric("Avg quality", f"{metrics.get('avg_quality', 0):.2f}")
cols[3].metric("Avg latency", f"{metrics.get('avg_latency_ms', 0)}ms")
cols[4].metric("Guardrail blocks", f"{metrics.get('guardrail_rate', 0)}%")

left, right = st.columns(2)
with left:
    st.subheader("Daily volume")
    daily = metrics.get("daily_volume", {})
    if daily:
        for day in sorted(daily):
            count = daily[day]
            st.text(f"{day}  {'█' * min(count, 40)} {count}")
    else:
        st.caption("No data yet.")
with right:
    st.subheader("Agent distribution")
    agent_dist = metrics.get("agent_distribution", {})
    if agent_dist:
        total = sum(agent_dist.values()) or 1
        for agent, count in sorted(agent_dist.items(), key=lambda item: item[1], reverse=True):
            st.text(f"{agent:<14} {'█' * max(1, round((count / total) * 25))} {round((count / total) * 100)}%")
    else:
        st.caption("No data yet.")

st.divider()
st.subheader("RAGAS Evaluation")
ragas_tab, add_tab, hist_tab = st.tabs(["Run eval", "Add questions", "History"])

with ragas_tab:
    eval_set = get_eval_set(user_id)
    st.write(f"Eval set size: **{len(eval_set)} questions**")
    if not eval_set:
        st.info("Add at least a few evaluation questions first.")
    else:
        doc_options = ["All"] + sorted({item.get("doc_title") for item in eval_set if item.get("doc_title")})
        selected_doc = st.selectbox("Document", doc_options)
        if st.button("Run RAGAS evaluation"):
            with st.spinner("Running evaluation…"):
                scores = run_evaluation(user_id, "local", None if selected_doc == "All" else selected_doc)
            st.success("Evaluation complete.")
            score_cols = st.columns(4)
            score_cols[0].metric("Faithfulness", f"{scores.get('faithfulness', 0):.2%}")
            score_cols[1].metric("Answer relevancy", f"{scores.get('answer_relevancy', 0):.2%}")
            score_cols[2].metric("Context recall", f"{scores.get('context_recall', 0):.2%}")
            score_cols[3].metric("Context precision", f"{scores.get('context_precision', 0):.2%}")

with add_tab:
    with st.form("add_eval_question"):
        question = st.text_input("Question")
        answer = st.text_area("Ground truth answer", height=90)
        doc_title = st.text_input("Document title (optional)")
        submitted = st.form_submit_button("Add question")
    if submitted:
        if question and answer:
            save_eval_question(user_id, question, answer, doc_title or None)
            st.success("Question added.")
        else:
            st.error("Question and answer are required.")

    existing = get_eval_set(user_id)
    for item in existing[:5]:
        with st.expander(item.get("question", "Question")[:80]):
            st.write(item.get("ground_truth", ""))
            if item.get("doc_title"):
                st.caption(item["doc_title"])

with hist_tab:
    history = get_ragas_history(user_id)
    if history:
        for record in history:
            st.text(
                f"{record.get('week_start')}  F:{record.get('faithfulness', 0):.2f}  "
                f"R:{record.get('answer_relevancy', 0):.2f}  "
                f"CR:{record.get('context_recall', 0):.2f}  "
                f"CP:{record.get('context_precision', 0):.2f}  "
                f"({record.get('total_questions', 0)}q)"
            )
    else:
        st.caption("No RAGAS history yet.")

st.divider()
st.subheader("Prompt A/B Testing")
if active_exp:
    st.success(f"Active experiment: {active_exp.get('name', '')}")
    results = get_experiment_results(active_exp["id"])
    cols = st.columns(3)
    cols[0].metric("Variant A", results.get("A", {}).get("count", 0))
    cols[1].metric("Variant B", results.get("B", {}).get("count", 0))
    cols[2].metric("Winner", results.get("winner", "—"))
    with st.expander("Prompt A"):
        st.code(active_exp.get("prompt_a", PROMPT_A), language="text")
    with st.expander("Prompt B"):
        st.code(active_exp.get("prompt_b", PROMPT_B), language="text")
else:
    st.info("No active experiment.")

with st.form("create_experiment"):
    name = st.text_input("Experiment name")
    prompt_a = st.text_area("Prompt A", value=PROMPT_A, height=110)
    prompt_b = st.text_area("Prompt B", value=PROMPT_B, height=110)
    submitted = st.form_submit_button("Start experiment")
if submitted:
    if name and prompt_a and prompt_b:
        create_experiment(prompt_a, prompt_b, name)
        st.success("Experiment created.")
        st.rerun()
    else:
        st.error("All fields are required.")

st.divider()
st.subheader("Cache")
st.metric("Status", "Enabled" if cache_stats.get("enabled") else "Disabled")
st.metric("Cached queries", cache_stats.get("cached_queries", 0))
st.metric("TTL", f"{cache_stats.get('ttl_hours', 1)}h")

st.divider()
st.subheader("Recent queries")
for item in recent:
    with st.expander(item.get("query", "")[:80]):
        st.caption(f"Agent: {item.get('agent_type', '')}")
        st.caption(f"Model: {item.get('model_used', '')}")
        st.caption(f"Latency: {item.get('latency_ms', 0)}ms")
        st.caption(f"Quality: {item.get('quality_score', 0):.2f}")

st.divider()
st.subheader("Document summaries")
if summaries:
    for summary in summaries:
        with st.expander(summary.get("doc_title", "Untitled")):
            st.write(summary.get("summary", ""))
else:
    st.caption("No documents loaded yet.")
