import streamlit as st
import pandas as pd
import requests
from supabase import create_client, Client

# --- Initialize refresh flag ---
if "refresh_flag" not in st.session_state:
    st.session_state.refresh_flag = False

# --- Supabase config ---
SUPABASE_URL = "https://vphtpzlbdcotorqpuonr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZwaHRwemxiZGNvdG9ycXB1b25yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDU1MDg0OTcsImV4cCI6MjA2MTA4NDQ5N30.XTP7clV__5ZVp9hZCJ2eGhL7HgEUeTcl2uINX0JC9WI"
SUPABASE_BUCKET = "bidding-projects"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Page Setup ---
st.set_page_config(page_title="Bidding Dashboard", layout="wide")
st.title("🕷️ Aiva Crawler | Dashboard")

# --- Custom CSS ---
st.markdown("""
<style>
.stDataFrame tbody tr:hover {
    background-color: #00C853 !important;
    color: white !important;
}
.stDataFrame thead tr th {
    background-color: #1f1f1f !important;
    color: white !important;
}
.stButton>button:hover {
    color: #00FF7F !important;
    border: 1px solid #00FF7F !important;
    background-color: #3a3d44 !important;
}
details:hover summary {
    color: #00FF7F !important;
}
</style>
""", unsafe_allow_html=True)

# --- Fetch all data with pagination ---
@st.cache_data
def fetch_all_data():
    all_rows = []
    page = 0
    page_size = 1000
    while True:
        response = (
            supabase.table("BiddingDB")
            .select("*")
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        rows = response.data
        if not rows:
            break
        all_rows.extend(rows)
        page += 1
    return pd.DataFrame(all_rows)

# --- Efficient count using count="exact" ---
def get_filtered_count(entity=None, category=None, status=None, classification=None):
    query = supabase.table("BiddingDB").select("*", count="exact", head=True)
    if entity and entity != "All":
        query = query.eq("Entity", entity)
    if category and category != "All":
        query = query.eq("category", category)
    if status and status != "All":
        query = query.eq("Status", status)
    if classification and classification != "All":
        query = query.eq("Classification", classification)
    query = query.eq("isApproved", False)
    return query.execute().count

# --- Manual Refresh ---
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()

df = fetch_all_data()
if "isApproved" in df.columns:
    df = df[df["isApproved"] != True]
else:
    st.warning("⚠️ No Data Recorded")


if df.empty:
    st.warning("⚠️ No Data Recorded")
    st.stop()

# --- Sidebar Filters ---
with st.sidebar:
    st.header("🔍 Filter Bids")
    entity_filter = st.selectbox("Entity", ["All"] + sorted(df["Entity"].dropna().unique().tolist()))
    category_filter = st.selectbox("Category", ["All"] + sorted(df["category"].dropna().unique().tolist()))
    status_filter = st.selectbox("Status", ["All"] + sorted(df["Status"].dropna().unique().tolist()))
    classification_filter = st.selectbox("Classification", ["All"] + sorted(df["Classification"].dropna().unique().tolist()))

# --- Apply Filters ---
filtered_df = df.copy()
if entity_filter != "All":
    filtered_df = filtered_df[filtered_df["Entity"] == entity_filter]
if category_filter != "All":
    filtered_df = filtered_df[filtered_df["category"] == category_filter]
if status_filter != "All":
    filtered_df = filtered_df[filtered_df["Status"] == status_filter]
if classification_filter != "All":
    filtered_df = filtered_df[filtered_df["Classification"] == classification_filter]

# --- Metrics ---
col1, col2 = st.columns(2)
col1.metric(label="📊 Total Unapproved Records", value=len(df))
col2.metric(label="🔎 Filtered Records", value=len(filtered_df))

# --- Display Table ---
st.markdown("### 📄 Filtered Bidding Data")
st.dataframe(filtered_df, use_container_width=True)

# --- Record Viewer ---
record_id = st.text_input("Enter record Reference No. to view", "")
if record_id:
    try:
        record = df[df["ReferenceNo"] == record_id].iloc[0]
        with st.expander("📌 Record Details", expanded=True):
            st.markdown(f"### 📝 {record['Title']}")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**📍 Entity:** {record['Entity']}")
                st.markdown(f"**📂 Category:** {record['category']}") 
                st.markdown(f"**🏷️ Classification:** {record['Classification']}")
                st.markdown(f"**📌 Status:** {record['Status']}")
                st.markdown(f"**💰 ABC:** {record['ABC']}")
            
            with col2:
                st.markdown(f"**📅 Publish Date:** {record['PublishDate']}")
                st.markdown(f"**⏳ Closing Date:** {record['ClosingDate']}")
                st.markdown(f"**🔗 Page URL:** [View Page]({record['PageURL']})")

            st.text_area(
                label="🧾 Summary",
                value=record["Summary"],
                height=300,
                disabled=True,
                key=f"summary_{record['ReferenceNo']}"
            )

            # Button to send to JIRA
            if st.button("✅ Approve Bidding (Jira)", key=f"jira_{record['ReferenceNo']}"):
                payload = {"reference_number": record['ReferenceNo']}
                response = requests.post(
                    "https://refine-rugs-studios-generation.trycloudflare.com/create-ticket",
                    json=payload
                )

                if response.status_code == 200:
                    supabase.table("BiddingDB").update({"isApproved": True}).eq("ReferenceNo", record['ReferenceNo']).execute()
                    st.success(f"Bidding '{record['Title']}' approved and ticket created in Jira.")
                    st.cache_data.clear()
                    st.session_state.refresh_flag = not st.session_state.refresh_flag
                else:
                    st.error(f"Failed to create Jira ticket. Status code: {response.status_code}")

            # New button to send to Monday.com
            if st.button("📩 Approve Bidding (Monday)", key=f"monday_{record['ReferenceNo']}"):
                payload = {"reference_number": record['ReferenceNo']}
                response = requests.post(
                    "https://aivadeus.onrender.com/add-monday",
                    json=payload
                )

                if response.status_code == 200:
                    st.success(f"Bidding '{record['Title']}' sent to Monday.com.")
                else:
                    st.error(f"Failed to send to Monday.com. Status code: {response.status_code}")
    except IndexError:
        st.error("No record found with that ReferenceNo.")

