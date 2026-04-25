"""
AskMyDocs Observability Dashboard
Streamlit entry point for Streamlit Cloud deployment
"""

import streamlit as st
import os

st.set_page_config(page_title="AskMyDocs — Dashboard", page_icon="📊", layout="wide")

st.title("📊 AskMyDocs Observability Dashboard")
st.markdown("---")

st.info("""
**Note for Streamlit Cloud:**
This dashboard displays query metrics from your Supabase database.
Make sure to set the following secrets in Streamlit Cloud settings:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `NVIDIA_API_KEY` (optional, only needed if dashboard tries to generate new queries)

The dashboard will automatically fetch metrics from your production backend.
""")

# Try to load metrics if credentials are available
try:
    from backend.observability import get_metrics
    
    # In Streamlit Cloud, use st.secrets to access environment variables
    if hasattr(st, 'secrets') and 'SUPABASE_URL' in st.secrets:
        # Streamlit Cloud mode
        os.environ['SUPABASE_URL'] = st.secrets.SUPABASE_URL
        os.environ['SUPABASE_SERVICE_KEY'] = st.secrets.SUPABASE_SERVICE_KEY
        
        user_id = st.text_input("Enter your user ID to view metrics:", key="user_id_input")
        
        if user_id:
            metrics = get_metrics(user_id, days=7)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Queries", metrics.get("total_queries", 0))
            with col2:
                st.metric("Cache Hit Rate", f"{metrics.get('cache_hit_rate', 0):.1f}%")
            with col3:
                st.metric("Avg Quality", f"{metrics.get('avg_quality_score', 0):.2f}")
            with col4:
                st.metric("Avg Latency", f"{metrics.get('avg_latency_ms', 0):.0f}ms")
            
            st.divider()
            st.subheader("Guardrail Activity")
            st.metric("Blocks", f"{metrics.get('guardrail_rate', 0):.1f}%")
            
            st.divider()
            st.subheader("Agent Distribution")
            if metrics.get("agent_distribution"):
                st.bar_chart(metrics["agent_distribution"])
            
            st.divider()
            st.subheader("Recent Queries")
            from backend.observability import get_recent_queries
            recent = get_recent_queries(user_id, limit=10)
            if recent:
                st.dataframe(recent, use_container_width=True)
            else:
                st.info("No queries yet")
    else:
        st.warning("Credentials not configured. Please add secrets in Streamlit Cloud settings.")
        
except ImportError:
    st.error("Could not import observability module. Check deployment logs.")
except Exception as e:
    st.error(f"Error loading metrics: {str(e)}")
    st.info("Check that SUPABASE_URL and SUPABASE_SERVICE_KEY are set in Streamlit Cloud secrets.")

