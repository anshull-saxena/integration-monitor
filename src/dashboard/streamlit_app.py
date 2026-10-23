import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Integration Monitor Dashboard", layout="wide", page_icon="🔍")

st.title("Integration Monitor Dashboard")
st.markdown("Real-time pipeline ingestion monitoring, data-quality violations, and LLM root-cause diagnosis.")

API_BASE = st.sidebar.text_input("Monitor API URL", "http://localhost:8000")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🚀 Trigger Ingestion Sync"):
        with st.spinner("Ingesting data..."):
            try:
                res = requests.post(f"{API_BASE}/pipeline/sync")
                st.success("Sync Complete!")
                st.json(res.json())
            except Exception as e:
                st.error(f"Sync failed: {e}")

with col2:
    if st.button("🛡️ Run Validation Rules"):
        with st.spinner("Evaluating integrity checks..."):
            try:
                res = requests.post(f"{API_BASE}/pipeline/validate")
                st.success("Validation Complete!")
                st.json(res.json())
            except Exception as e:
                st.error(f"Validation failed: {e}")

with col3:
    if st.button("📊 Run Evaluation Suite (/eval)"):
        with st.spinner("Running eval scenarios..."):
            try:
                res = requests.get(f"{API_BASE}/eval")
                st.success("Evaluation Done!")
                st.json(res.json())
            except Exception as e:
                st.error(f"Eval run failed: {e}")

st.divider()

# Incidents View
st.subheader("Active & Past Incidents")
try:
    inc_res = requests.get(f"{API_BASE}/incidents")
    if inc_res.status_code == 200:
        incidents = inc_res.json()
        if incidents:
            for inc in incidents:
                with st.expander(f"[{inc['severity']}] {inc['check_name']} - {inc['incident_id']} ({inc['status']})"):
                    st.write(f"**Category:** {inc['rule_category']}")
                    st.write(f"**Created At:** {inc['created_at']}")
                    st.info(f"💡 **LLM Root Cause Summary:**\n{inc['root_cause_summary']}")
                    st.success(f"🔧 **Suggested Remediation:**\n{inc['suggested_fix']}")
                    st.json(inc['details'])
        else:
            st.info("No incidents found.")
except Exception as e:
    st.warning(f"Could not load incidents: {e}")

st.divider()

# Dead Letter Queue View
st.subheader("Dead Letter Queue (Failed Records)")
try:
    dlq_res = requests.get(f"{API_BASE}/dead-letter-records")
    if dlq_res.status_code == 200:
        dlq_records = dlq_res.json()
        if dlq_records:
            st.dataframe(pd.DataFrame(dlq_records))
        else:
            st.success("DLQ is clean. No rejected records.")
except Exception as e:
    st.warning(f"Could not load DLQ: {e}")
