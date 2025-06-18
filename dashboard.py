import streamlit as st
import pandas as pd
import requests
import os
from dotenv import load_dotenv

load_dotenv()

if "refresh_flag" not in st.session_state:
    st.session_state.refresh_flag = False

# --- Supabase config ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

from supabase import create_client, Client
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

    entity_options = sorted(df["Entity"].dropna().unique().tolist())
    category_options = sorted(df["category"].dropna().unique().tolist())
    status_options = sorted(df["Status"].dropna().unique().tolist())
    classification_options = sorted(df["Classification"].dropna().unique().tolist())
    type_options = sorted(df["Type"].dropna().unique().tolist()) if "Type" in df.columns else []

    entity_filter = st.multiselect("Entity", entity_options, default=[])
    category_filter = st.multiselect("Category", category_options, default=[])
    status_filter = st.multiselect("Status", status_options, default=[])
    classification_filter = st.multiselect("Classification", classification_options, default=[])
    type_filter = st.multiselect("Type", type_options, default=[])

# --- Apply Filters ---
filtered_df = df.copy()

if entity_filter:
    filtered_df = filtered_df[filtered_df["Entity"].isin(entity_filter)]
if category_filter:
    filtered_df = filtered_df[filtered_df["category"].isin(category_filter)]
if status_filter:
    filtered_df = filtered_df[filtered_df["Status"].isin(status_filter)]
if classification_filter:
    filtered_df = filtered_df[filtered_df["Classification"].isin(classification_filter)]
if type_filter and "Type" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["Type"].isin(type_filter)]

# --- Metrics ---
col1, col2 = st.columns(2)
col1.metric(label="📊 Total Unapproved Records", value=len(df))
col2.metric(label="🔎 Filtered Records", value=len(filtered_df))

# --- Display Table ---
st.markdown("### 📄 Filtered Bidding Data")

# Drop unwanted columns
if "id" in filtered_df.columns:
    filtered_df = filtered_df.drop(columns=["id"])
if "created_at" in filtered_df.columns:
    filtered_df = filtered_df.drop(columns=["created_at"])

# Format ABC
if "ABC" in filtered_df.columns:
    filtered_df["ABC"] = filtered_df["ABC"].apply(
        lambda x: f"₱ {float(x):,.2f}" if pd.notnull(x) else "N/A"
    )

if "REQT_LIST" in filtered_df.columns:
    filtered_df["REQT_LIST"] = filtered_df["REQT_LIST"].astype(str)



# Column order
pinned_columns = ["ReferenceNo", "ABC", "category"]
if "Type" in filtered_df.columns:
    pinned_columns.append("Type")
if "REQT_LIST" in filtered_df.columns:
    pinned_columns.append("REQT_LIST")
other_columns = [col for col in filtered_df.columns if col not in pinned_columns]
ordered_columns = pinned_columns + other_columns
filtered_df = filtered_df[ordered_columns]

# Display with column config
st.data_editor(
    filtered_df,
    use_container_width=True,
    disabled=True,
    column_config={
        "ReferenceNo": st.column_config.Column(label="📌 Reference No.", pinned="left"),
        "ABC": st.column_config.Column(label="💰 ABC", pinned="left"),
        "category": st.column_config.Column(label="📂 Category", pinned="left"),
        "Type": st.column_config.Column(label="📑 Type"),
        "REQT_LIST": st.column_config.Column(label="📝 REQT LIST"),
    }
)

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

            # Monday.com button
            if st.button("📩 Approve Bidding (Monday)", key=f"monday_{record['ReferenceNo']}"):
                payload = {"reference_number": record['ReferenceNo']}
                response = requests.post(
                    "https://statement-kick-remaining-fire.trycloudflare.com/add-monday",
                    json=payload
                )
                if response.status_code == 200:
                    st.success(f"Bidding '{record['Title']}' sent to Monday.com.")
                else:
                    st.error(f"Failed to send to Monday.com. Status code: {response.status_code}")
    except IndexError:
        st.error("No record found with that ReferenceNo.")
